import os
import json
import random
import asyncio
import httpx
from datetime import datetime
import pytz

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")
DATABASE_FILE = "songs.json"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
TIMEOUT = 20
RESTART_DELAY = 10
RANDOM_SONG_COUNT = 3

IRAN_TZ = pytz.timezone("Asia/Tehran")
TOPIC_11_11_ID = 2463

def load_database():
    if os.path.exists(DATABASE_FILE):
        with open(DATABASE_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    return []

def save_database(data):
    with open(DATABASE_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)

song_database = load_database()

async def send_message(chat_id, text):
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        await client.get(f"{BASE_URL}/sendMessage", params={"chat_id": chat_id, "text": text})

async def handle_document(document, chat_id):
    file_name = document["file_name"]

    if file_name != "songs.json":
        await send_message(chat_id, "⚠️ لطفاً فایل songs.json ارسال کنید.")
        return

    file_id = document["file_id"]
    async with httpx.AsyncClient() as client:
        file_info = await client.get(f"{BASE_URL}/getFile", params={"file_id": file_id})
        file_path = file_info.json()["result"]["file_path"]
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        response = await client.get(file_url)

        with open(DATABASE_FILE, "wb") as file:
            file.write(response.content)

    song_database[:] = load_database()
    await send_message(chat_id, f"✅ دیتابیس آپدیت شد! تعداد آهنگ‌ها: {len(song_database)}")

async def send_file_to_user(chat_id):
    if os.path.exists(DATABASE_FILE):
        async with httpx.AsyncClient() as client:
            with open(DATABASE_FILE, "rb") as file:
                await client.post(f"{BASE_URL}/sendDocument", params={"chat_id": chat_id}, files={"document": file})
    else:
        await send_message(chat_id, "⚠️ هنوز هیچ آهنگی ذخیره نشده!")

async def send_random_song(chat_id):
    if not song_database:
        await send_message(chat_id, "⚠️ دیتابیس خالی است!")
        return

    songs = random.sample(song_database, min(RANDOM_SONG_COUNT, len(song_database)))
    async with httpx.AsyncClient() as client:
        for song in songs:
            response = await client.get(f"{BASE_URL}/copyMessage", params={
                "chat_id": chat_id,
                "from_chat_id": GROUP_ID,
                "message_id": song["message_id"]
            })

            if not response.json().get("ok"):
                song_database.remove(song)
                save_database(song_database)

async def forward_music_without_caption(message, thread_id):
    message_id = message["message_id"]
    audio = message["audio"]

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        forward_response = await client.get(f"{BASE_URL}/sendAudio", params={
            "chat_id": GROUP_ID,
            "audio": audio["file_id"],
            "message_thread_id": thread_id,
            "caption": ""
        })

        forward_data = forward_response.json()
        if forward_data.get("ok"):
            new_message_id = forward_data["result"]["message_id"]
            song_database.append({
                "message_id": new_message_id,
                "thread_id": thread_id
            })
            save_database(song_database)

            await asyncio.sleep(1)
            await client.get(f"{BASE_URL}/deleteMessage", params={
                "chat_id": GROUP_ID,
                "message_id": message_id
            })

async def send_random_songs_to_11_11():
    if not song_database:
        print("⚠️ دیتابیس آهنگ‌ها خالی است.")
        return

    songs = random.sample(song_database, min(RANDOM_SONG_COUNT, len(song_database)))

    async with httpx.AsyncClient() as client:
        for song in songs:
            try:
                response = await client.get(f"{BASE_URL}/copyMessage", params={
                    "chat_id": GROUP_ID,
                    "from_chat_id": GROUP_ID,
                    "message_id": song["message_id"],
                    "message_thread_id": TOPIC_11_11_ID
                })
                response_data = response.json()

                if not response_data.get("ok"):
                    print(f"⚠️ خطا در ارسال آهنگ {song['message_id']}: {response_data}")
            except Exception as e:
                print(f"⚠️ خطا در ارسال آهنگ {song['message_id']}: {e}")
            await asyncio.sleep(1)

async def check_time_for_scheduled_task():
    while True:
        now = datetime.now(IRAN_TZ)
        if now.hour == 23 and now.minute == 11:
            print("🕚 ارسال آهنگ‌های 11:11 شروع شد...")
            try:
                await send_random_songs_to_11_11()
                print("✅ آهنگ‌های 11:11 ارسال شدند.")
            except Exception as e:
                print(f"⚠️ خطا در اجرای 11:11: {e}")
            await asyncio.sleep(70)
        await asyncio.sleep(30)

async def check_new_messages():
    last_update_id = None
    while True:
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.get(f"{BASE_URL}/getUpdates", params={"offset": last_update_id})
                data = response.json()

                if data.get("ok"):
                    for update in data["result"]:
                        last_update_id = update["update_id"] + 1
                        message = update.get("message", {})
                        chat_id = message.get("chat", {}).get("id")
                        text = message.get("text", "").strip()

                        if text == "/start":
                            await send_message(chat_id, "/random - سه تا آهنگ رندوم بگیر\nآپشن دیگه‌ای هم نداره شوخوش.")
                        elif text == "/help":
                            await send_message(chat_id, "راهنمایی میخوای چیکار!؟")
                        elif "document" in message:
                            await handle_document(message["document"], chat_id)
                        elif text == "/random":
                            await send_random_song(chat_id)
                        elif text == "/list":
                            await send_file_to_user(chat_id)
                        elif "audio" in message and str(chat_id) == GROUP_ID:
                            await forward_music_without_caption(message, message.get("message_thread_id"))

        except Exception as e:
            print(f"⚠️ خطا: {e}")
            await asyncio.sleep(5)

        await asyncio.sleep(3)

async def main():
    await send_message(GROUP_ID, "🔥 I'm Ready, brothers!")
    asyncio.create_task(check_time_for_scheduled_task())
    await check_new_messages()

if __name__ == "__main__":
    asyncio.run(main())
