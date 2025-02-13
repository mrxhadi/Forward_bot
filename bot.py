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
startup_message_sent = False  
MAX_RETRIES = 3  
RANDOM_SONG_COUNT = 3  
RESTART_DELAY = 10  
GENERAL_TOPIC_NAME = "General"  

EXCLUDED_TOPICS_RANDOM = ["Nostalgic", "Golchin-e Shad-e Irooni"]

IRAN_TZ = pytz.timezone("Asia/Tehran")

song_tracker = {}  

# ارسال پیام به تلگرام
async def send_message(chat_id, text):
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        params = {"chat_id": chat_id, "text": text}
        try:
            await client.get(f"{BASE_URL}/sendMessage", params=params)
        except httpx.ReadTimeout:
            await asyncio.sleep(5)
            await send_message(chat_id, text)

# دریافت لیست تاپیک‌ها
async def get_forum_topics():
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.get(f"{BASE_URL}/getChat", params={"chat_id": GROUP_ID})
        data = response.json()
        if data.get("ok") and "message_thread_id" in data["result"]:
            return {thread["message_thread_id"]: thread["name"] for thread in data["result"]["message_threads"]}
        return {}

# دریافت پیام‌های یک تاپیک خاص
async def get_topic_messages(thread_id):
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.get(f"{BASE_URL}/getChatHistory", params={"chat_id": GROUP_ID, "message_thread_id": thread_id, "limit": 100})
        data = response.json()
        if data.get("ok"):
            messages = [msg for msg in data["result"]["messages"] if "audio" in msg]
            print(f"📥 دریافت {len(messages)} آهنگ از تاپیک {thread_id}")
            return messages
        print(f"⚠️ هیچ آهنگی در تاپیک {thread_id} یافت نشد.")
        return []

# دریافت آهنگ‌های تصادفی برای چت خصوصی
async def send_random_songs(chat_id):
    print(f"🎲 دریافت دستور /random از {chat_id}")

    topics = await get_forum_topics()
    selected_messages = []

    for thread_id, name in topics.items():
        if name not in EXCLUDED_TOPICS_RANDOM:
            messages = await get_topic_messages(thread_id)
            selected_messages.extend(messages)

    print(f"🎶 تعداد کل آهنگ‌های دریافت‌شده: {len(selected_messages)}")

    if len(selected_messages) >= RANDOM_SONG_COUNT:
        random_messages = random.sample(selected_messages, RANDOM_SONG_COUNT)
    else:
        random_messages = selected_messages  

    if not random_messages:
        await send_message(chat_id, "⚠️ متأسفم، هیچ آهنگی برای ارسال پیدا نشد!")
        return

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for message in random_messages:
            message_id = message["message_id"]
            await client.get(f"{BASE_URL}/copyMessage", params={
                "chat_id": chat_id,
                "from_chat_id": GROUP_ID,
                "message_id": message_id
            })
            await asyncio.sleep(1)

    print(f"✅ سه آهنگ تصادفی برای {chat_id} ارسال شد.")

# بررسی پیام‌های جدید و دستورات
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
                            chat_type = message["chat"]["type"]  
                            text = message.get("text", "")

                            if text == "/random" and chat_type == "private":
                                await send_random_songs(chat_id)  

        except Exception as e:
            print(f"⚠️ خطا در `check_new_messages()`: {e}")
            await asyncio.sleep(5)

        await asyncio.sleep(3)

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
