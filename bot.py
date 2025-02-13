import os
import requests
import asyncio
import httpx
import json
import random
from datetime import datetime
import pytz

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")
DATABASE_FILE = "songs.json"

if not BOT_TOKEN or not GROUP_ID:
    raise ValueError("❌ متغیرهای محیطی BOT_TOKEN و GROUP_ID تنظیم نشده‌اند!")

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
bot_enabled = True  
TIMEOUT = 20  
RESTART_DELAY = 10  
IRAN_TZ = pytz.timezone("Asia/Tehran")
EXCLUDED_TOPICS_RANDOM = ["Nostalgic", "Golchin-e Shad-e Irooni"]
RANDOM_SONG_COUNT = 3  

startup_message_sent = False  

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

# **📌 لیست آهنگ‌ها در دیتابیس**
song_database = load_database()

# 📌 **بررسی آهنگ‌های تکراری**
def is_duplicate_song(audio, thread_id):
    title = audio.get("title", "نامشخص").lower()
    performer = audio.get("performer", "نامشخص").lower()
    
    for song in song_database:
        if song["title"] == title and song["performer"] == performer and song["thread_id"] == thread_id:
            return True
    return False

# 📌 **ارسال پیام به تلگرام**
async def send_message(chat_id, text):
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            await client.get(f"{BASE_URL}/sendMessage", params={"chat_id": chat_id, "text": text})
        except httpx.ReadTimeout:
            await asyncio.sleep(5)
            await send_message(chat_id, text)

# 📌 **فوروارد آهنگ‌های جدید بدون کپشن و حذف پیام اصلی (اگر تکراری نباشد)**
async def forward_music_without_caption(message, thread_id):
    message_id = message["message_id"]
    audio = message["audio"]

    if is_duplicate_song(audio, thread_id):
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            await client.get(f"{BASE_URL}/deleteMessage", params={
                "chat_id": GROUP_ID,
                "message_id": message_id
            })
        return  # پیام جدید رو فقط حذف کن و ادامه نده

    audio_file_id = audio["file_id"]
    audio_title = audio.get("title", "نامشخص").lower()
    audio_performer = audio.get("performer", "نامشخص").lower()

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        forward_response = await client.get(f"{BASE_URL}/sendAudio", params={
            "chat_id": GROUP_ID,
            "audio": audio_file_id,
            "message_thread_id": thread_id,
            "caption": ""  # حذف کپشن از آهنگ
        })
        forward_data = forward_response.json()

        if forward_data.get("ok"):
            new_message_id = forward_data["result"]["message_id"]

            # ذخیره پیام جدید در دیتابیس
            song_database.append({
                "title": audio_title,
                "performer": audio_performer,
                "message_id": new_message_id,
                "thread_id": thread_id
            })
            save_database(song_database)

            # حذف پیام اصلی
            await asyncio.sleep(1)
            delete_response = await client.get(f"{BASE_URL}/deleteMessage", params={
                "chat_id": GROUP_ID,
                "message_id": message_id
            })
            delete_data = delete_response.json()
            if not delete_data.get("ok"):
                print(f"⚠️ پیام {message_id} حذف نشد: {delete_data['description']}")

# 📌 **دریافت پیام‌های جدید**
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

                            # فقط پیام‌های گروه بررسی بشن
                            if bot_enabled and "audio" in message and str(chat_id) == GROUP_ID:
                                thread_id = message.get("message_thread_id")
                                await forward_music_without_caption(message, thread_id)
                                await asyncio.sleep(1)

        except Exception as e:
            print(f"⚠️ خطا در `check_new_messages()`: {e}")
            await asyncio.sleep(5)

        await asyncio.sleep(3)

# 📌 **ارسال سه آهنگ تصادفی به تاپیک `11:11` هر شب ساعت 11:11**
async def send_nightly_random_songs():
    while True:
        now = datetime.now(IRAN_TZ)
        if now.hour == 23 and now.minute == 11:  # 11:11 PM به وقت ایران
            valid_songs = [song for song in song_database if song["thread_id"] not in EXCLUDED_TOPICS_RANDOM]
            if not valid_songs:
                return

            topic_11_11 = "11:11"  # اینو با آی‌دی واقعی جایگزین کن
            selected_songs = random.sample(valid_songs, min(RANDOM_SONG_COUNT, len(valid_songs)))

            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                for song in selected_songs:
                    await client.get(f"{BASE_URL}/copyMessage", params={
                        "chat_id": GROUP_ID,
                        "from_chat_id": GROUP_ID,
                        "message_id": song["message_id"],
                        "message_thread_id": topic_11_11
                    })
            await asyncio.sleep(60)

        await asyncio.sleep(10)

# 📌 **اجرای اصلی**
async def main():
    await send_message(GROUP_ID, "🔥 I'm Ready, brothers!")

    while True:
        try:
            await asyncio.gather(
                check_new_messages(),
                send_nightly_random_songs()
            )
        except Exception as e:
            print(f"⚠️ کرش غیرمنتظره: {e}")
            await asyncio.sleep(RESTART_DELAY)

if __name__ == "__main__":
    asyncio.run(main())
