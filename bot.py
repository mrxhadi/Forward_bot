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
EXCLUDED_TOPICS_RANDOM = ["Nostalgic", "Golchin-e Shad-e Irooni"]
TOPIC_11_11 = "11:11"  

# 📌 **لود کردن دیتابیس از JSON**
def load_database():
    if os.path.exists(DATABASE_FILE):
        with open(DATABASE_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    return []

# 📌 **ذخیره دیتابیس در JSON**
def save_database(data):
    with open(DATABASE_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)

song_database = load_database()

# 📌 **ارسال پیام به تلگرام**
async def send_message(chat_id, text):
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        await client.get(f"{BASE_URL}/sendMessage", params={"chat_id": chat_id, "text": text})

# 📌 **ارسال فایل `songs.json` به پیوی (دستور `/list` کار می‌کند ولی در منو نمایش داده نمی‌شود)**
async def send_file_to_user(chat_id):
    if os.path.exists(DATABASE_FILE):
        async with httpx.AsyncClient() as client:
            with open(DATABASE_FILE, "rb") as file:
                await client.post(f"{BASE_URL}/sendDocument", params={"chat_id": chat_id}, files={"document": file})
    else:
        await send_message(chat_id, "⚠️ هنوز هیچ آهنگی ذخیره نشده!")

# 📌 **دریافت و ذخیره `songs.json` از پیوی**
async def handle_document(document, chat_id):
    global song_database  
    file_name = document["file_name"]
    
    if file_name != "songs.json":
        await send_message(chat_id, "⚠️ این فایل پشتیبانی نمی‌شود! لطفاً `songs.json` ارسال کنید.")
        return

    file_id = document["file_id"]
    print(f"📥 دریافت فایل `{file_name}` از {chat_id}")

    async with httpx.AsyncClient() as client:
        file_info = await client.get(f"{BASE_URL}/getFile", params={"file_id": file_id})
        file_info_data = file_info.json()

        if not file_info_data.get("ok"):
            await send_message(chat_id, "❌ خطا در دریافت فایل از سرور تلگرام!")
            return

        file_path = file_info_data["result"]["file_path"]
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

        response = await client.get(file_url)
        with open(DATABASE_FILE, "wb") as file:
            file.write(response.content)

    song_database = load_database()  
    print(f"✅ دیتابیس آپدیت شد! تعداد آهنگ‌ها: {len(song_database)}")
    await send_message(chat_id, f"✅ دیتابیس آپدیت شد! تعداد آهنگ‌ها: {len(song_database)}")

# 📌 **ارسال ۳ آهنگ تصادفی به پیوی**
async def send_random_song(chat_id):
    global song_database

    if not song_database:
        await send_message(chat_id, "⚠️ هنوز هیچ آهنگی ذخیره نشده!")
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
                print(f"⚠️ پیام {song['message_id']} دیگر در گروه وجود ندارد. حذف از دیتابیس...")
                song_database.remove(song)
                save_database(song_database)

# 📌 **دریافت و پردازش پیام‌های جدید**
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
                        if "message" in update:
                            message = update["message"]
                            chat_id = message["chat"]["id"]
                            text = message.get("text", "").strip()

                            # 📌 **دریافت و ذخیره `songs.json`**
                            if "document" in message:
                                await handle_document(message["document"], chat_id)

                            # 📌 **دستورات ربات**
                            elif text == "/start":
                                await send_message(chat_id, "🎵 خوش آمدید! این ربات به آرشیو کانال @HTG_music متصل است.\n\nاز منوی دستورات استفاده کنید:\n✅ `/random` → دریافت ۳ آهنگ تصادفی\n❓ `/help` → نمایش راهنما")
                            elif text == "/list":
                                await send_file_to_user(chat_id)  # این کار می‌کند ولی در راهنما نیست
                            elif text == "/random":
                                await send_random_song(chat_id)
                            elif text == "/help":
                                await send_message(chat_id, "📌 **دستورات:**\n🎵 `/random` → دریافت ۳ آهنگ تصادفی\n❓ `/help` → نمایش راهنما\n\n📌 این ربات به آرشیو کانال @HTG_music متصل است.")

        except Exception as e:
            print(f"⚠️ خطا: {e}")
            await asyncio.sleep(5)

        await asyncio.sleep(3)

# 📌 **اجرای اصلی**
async def main():
    await send_message(GROUP_ID, "🔥 I'm Ready, brothers!")

    while True:
        try:
            await asyncio.gather(
                check_new_messages()
            )
        except Exception as e:
            print(f"⚠️ کرش غیرمنتظره: {e}")
            await asyncio.sleep(RESTART_DELAY)

if __name__ == "__main__":
    asyncio.run(main())
