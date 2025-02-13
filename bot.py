import os
import requests
import asyncio
import httpx
import json
from datetime import datetime
import pytz
import random

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

# 📌 **ارسال پیام به تلگرام**
async def send_message(chat_id, text):
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            await client.get(f"{BASE_URL}/sendMessage", params={"chat_id": chat_id, "text": text})
        except httpx.ReadTimeout:
            await asyncio.sleep(5)
            await send_message(chat_id, text)

# 📌 **ذخیره آهنگ جدید در دیتابیس**
def store_song(message, thread_id):
    audio = message.get("audio", {})
    title = audio.get("title", "نامشخص").lower()
    performer = audio.get("performer", "نامشخص").lower()
    message_id = message["message_id"]

    # چک کن که این آهنگ قبلاً ذخیره نشده باشه
    for song in song_database:
        if song["message_id"] == message_id:
            return

    # اضافه کردن آهنگ جدید
    song_database.append({
        "title": title,
        "performer": performer,
        "message_id": message_id,
        "thread_id": thread_id
    })

    # ذخیره در JSON
    save_database(song_database)

# 📌 **دریافت پیام‌های جدید و پردازش دستورات**
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

                            # 📌 **اگر دستور `/list` فرستاده شد، فایل را به پیوی کاربر ارسال کند**
                            if text == "/list":
                                user_id = message["from"]["id"]
                                await send_message(chat_id, "📩 فایل به پیوی شما ارسال شد.")
                                await send_file_to_user(user_id)

                            # 📌 **اگر دستور `/random` فرستاده شد، آهنگ تصادفی به پیوی کاربر ارسال کند**
                            elif text == "/random":
                                user_id = message["from"]["id"]
                                await send_random_song(user_id)

                            # 📌 **اگر دستور `/help` فرستاده شد، لیست دستورات به پیوی ارسال شود**
                            elif text == "/help":
                                user_id = message["from"]["id"]
                                await send_help_message(user_id)

                            # 📌 **اگر آهنگ جدید در گروه ارسال شد، آن را ذخیره و فوروارد کند**
                            if bot_enabled and "audio" in message and str(chat_id) == GROUP_ID:
                                thread_id = message.get("message_thread_id")
                                store_song(message, thread_id)
                                await forward_music_without_caption(message, thread_id)
                                await asyncio.sleep(1)

        except Exception as e:
            print(f"⚠️ خطا در `check_new_messages()`: {e}")
            await asyncio.sleep(5)

        await asyncio.sleep(3)

# 📌 **فوروارد آهنگ‌های جدید بدون کپشن و حذف پیام اصلی**
async def forward_music_without_caption(message, thread_id):
    message_id = message["message_id"]
    audio_file_id = message["audio"]["file_id"]

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        forward_response = await client.get(f"{BASE_URL}/sendAudio", params={
            "chat_id": GROUP_ID,
            "audio": audio_file_id,
            "message_thread_id": thread_id
        })
        forward_data = forward_response.json()

        if forward_data.get("ok"):
            await asyncio.sleep(1)
            delete_response = await client.get(f"{BASE_URL}/deleteMessage", params={
                "chat_id": GROUP_ID,
                "message_id": message_id
            })
            delete_data = delete_response.json()
            if not delete_data.get("ok"):
                print(f"⚠️ پیام {message_id} حذف نشد: {delete_data['description']}")

# 📌 **ارسال آهنگ تصادفی به پیوی**
async def send_random_song(user_id):
    if song_database:
        song = random.choice(song_database)
        message_id = song["message_id"]
        thread_id = song["thread_id"]

        async with httpx.AsyncClient() as client:
            await client.get(f"{BASE_URL}/copyMessage", params={
                "chat_id": user_id,
                "from_chat_id": GROUP_ID,
                "message_id": message_id
            })
    else:
        await send_message(user_id, "⚠️ هنوز هیچ آهنگی ذخیره نشده!")

# 📌 **ارسال فایل `songs.json` به پیوی**
async def send_file_to_user(user_id):
    if os.path.exists(DATABASE_FILE):
        async with httpx.AsyncClient() as client:
            with open(DATABASE_FILE, "rb") as file:
                files = {"document": file}
                params = {"chat_id": user_id}
                await client.post(f"{BASE_URL}/sendDocument", params=params, files=files)
    else:
        await send_message(user_id, "⚠️ هنوز هیچ آهنگی ذخیره نشده!")

# 📌 **ارسال لیست دستورات به پیوی**
async def send_help_message(user_id):
    help_text = """📌 **دستورات ربات:**
🎵 `/random` → دریافت یک آهنگ تصادفی در پیوی  
📁 `/list` → دریافت فایل لیست آهنگ‌ها  
❓ `/help` → نمایش این راهنما  
"""
    await send_message(user_id, help_text)

# 📌 **اضافه کردن دستورات به منوی ربات**
async def set_bot_commands():
    async with httpx.AsyncClient() as client:
        await client.get(f"{BASE_URL}/setMyCommands", params={
            "commands": json.dumps([
                {"command": "random", "description": "دریافت آهنگ تصادفی"},
                {"command": "list", "description": "دریافت لیست آهنگ‌ها"},
                {"command": "help", "description": "نمایش راهنما"}
            ])
        })

# 📌 **اجرای اصلی**
async def main():
    await set_bot_commands()
    await send_message(GROUP_ID, "🔥 I'm Ready, brothers!")

    while True:
        try:
            await asyncio.gather(check_new_messages())
        except Exception as e:
            print(f"⚠️ کرش غیرمنتظره: {e}")
            await asyncio.sleep(RESTART_DELAY)

if __name__ == "__main__":
    asyncio.run(main())
