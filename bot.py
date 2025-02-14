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

# 📌 **فوروارد آهنگ بدون کپشن و حذف پیام اصلی**
async def forward_music_without_caption(message, thread_id):
    message_id = message["message_id"]
    audio = message["audio"]

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        forward_response = await client.get(f"{BASE_URL}/sendAudio", params={
            "chat_id": GROUP_ID,
            "audio": audio["file_id"],
            "message_thread_id": thread_id,
            "caption": ""  # حذف کپشن
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

                            # 📌 **دریافت آهنگ و حذف کپشن**
                            if "audio" in message and str(chat_id) == GROUP_ID:
                                await forward_music_without_caption(message, message.get("message_thread_id"))

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
