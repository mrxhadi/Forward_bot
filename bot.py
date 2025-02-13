import os
import requests
import asyncio
import httpx
import random
from datetime import datetime
import pytz

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")

if not BOT_TOKEN or not GROUP_ID:
    raise ValueError("❌ متغیرهای محیطی BOT_TOKEN و GROUP_ID تنظیم نشده‌اند!")

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
bot_enabled = True  
TIMEOUT = 20  
MAX_RETRIES = 3  
RESTART_DELAY = 10  
GENERAL_TOPIC_NAME = "General"  

song_tracker = {}  

# ارسال پیام جدید به تلگرام
async def send_message(chat_id, text):
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        params = {"chat_id": chat_id, "text": text}
        try:
            await client.get(f"{BASE_URL}/sendMessage", params=params)
        except httpx.ReadTimeout:
            await asyncio.sleep(5)
            await send_message(chat_id, text)

# دریافت پیام‌های جدید و بررسی آهنگ‌های تکراری
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
                            thread_id = message.get("message_thread_id")

                            if bot_enabled and "audio" in message and str(chat_id) == GROUP_ID:
                                await forward_music(message, thread_id)
                                await asyncio.sleep(1)
        except Exception as e:
            print(f"⚠️ خطا در `check_new_messages()`: {e}")
            await asyncio.sleep(5)

        await asyncio.sleep(3)

# پردازش آهنگ‌های جدید و حذف آهنگ‌های تکراری
async def forward_music(message, thread_id):
    audio = message.get("audio", {})
    audio_name = audio.get("title", "Unknown")
    message_id = message["message_id"]

    if thread_id not in song_tracker:
        song_tracker[thread_id] = {}

    if audio_name in song_tracker[thread_id]:  # آهنگ تکراری پیدا شد
        old_message_id = song_tracker[thread_id][audio_name]

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            delete_response = await client.get(f"{BASE_URL}/deleteMessage", params={
                "chat_id": GROUP_ID,
                "message_id": old_message_id
            })
            delete_data = delete_response.json()
            if delete_data.get("ok"):
                general_topic_id = await get_general_topic()
                if general_topic_id:
                    await send_message(GROUP_ID, f"🔄 آهنگ **{audio_name}** در تاپیک `{thread_id}` جایگزین شد!")

    song_tracker[thread_id][audio_name] = message_id  # آهنگ جدید ثبت شد

# پیدا کردن تاپیک "General" برای ارسال گزارش
async def get_general_topic():
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.get(f"{BASE_URL}/getForumTopicList", params={"chat_id": GROUP_ID})
        data = response.json()
        if data.get("ok"):
            for topic in data["result"]["topics"]:
                if topic["name"].lower() == GENERAL_TOPIC_NAME.lower():
                    return topic["message_thread_id"]
    return None

# اجرای اصلی
async def main():
    global startup_message_sent
    if not startup_message_sent:
        await send_message(GROUP_ID, "🔥 I'm Ready, brothers!")
        startup_message_sent = True

    while True:
        try:
            await asyncio.gather(
                check_new_messages()
            )
        except Exception as e:
            print(f"⚠️ کرش غیرمنتظره: {e}")
            print(f"♻️ ری‌استارت در {RESTART_DELAY} ثانیه...")
            await asyncio.sleep(RESTART_DELAY)

if __name__ == "__main__":
    asyncio.run(main())
