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

# 📌 **ارسال پیام به تلگرام**
async def send_message(chat_id, text):
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            await client.get(f"{BASE_URL}/sendMessage", params={"chat_id": chat_id, "text": text})
        except httpx.ReadTimeout:
            await asyncio.sleep(5)
            await send_message(chat_id, text)

# 📌 **ارسال سه آهنگ تصادفی به پیوی**
async def send_random_song(user_id):
    if not song_database:
        await send_message(user_id, "⚠️ هنوز هیچ آهنگی ذخیره نشده!")
        return

    songs = random.sample(song_database, min(RANDOM_SONG_COUNT, len(song_database)))

    async with httpx.AsyncClient() as client:
        for song in songs:
            response = await client.get(f"{BASE_URL}/copyMessage", params={
                "chat_id": user_id,
                "from_chat_id": GROUP_ID,
                "message_id": song["message_id"]
            })
            data = response.json()
            if not data.get("ok"):
                await send_message(user_id, f"⚠️ خطا در ارسال آهنگ: {data['description']}")

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
                                help_text = """📌 **دستورات ربات:**
🎵 `/random` → دریافت سه آهنگ تصادفی در پیوی  
📁 `/list` → دریافت فایل لیست آهنگ‌ها  
❓ `/help` → نمایش این راهنما  
"""
                                await send_message(user_id, help_text)

        except Exception as e:
            print(f"⚠️ خطا در `check_new_messages()`: {e}")
            await asyncio.sleep(5)

        await asyncio.sleep(3)

# 📌 **اضافه کردن دستورات به منوی ربات**
async def set_bot_commands():
    async with httpx.AsyncClient() as client:
        await client.get(f"{BASE_URL}/setMyCommands", params={
            "commands": json.dumps([
                {"command": "random", "description": "دریافت سه آهنگ تصادفی"},
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
            await asyncio.gather(
                check_new_messages()
            )
        except Exception as e:
            print(f"⚠️ کرش غیرمنتظره: {e}")
            await asyncio.sleep(RESTART_DELAY)

if __name__ == "__main__":
    asyncio.run(main())
