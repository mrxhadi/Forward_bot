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
RANDOM_SONG_COUNT = 3  
RESTART_DELAY = 10  
GENERAL_TOPIC_NAME = "General"  
EXCLUDED_TOPICS_RANDOM = ["Nostalgic", "Golchin-e Shad-e Irooni"]
IRAN_TZ = pytz.timezone("Asia/Tehran")

startup_message_sent = False  

# ارسال پیام به تلگرام
async def send_message(chat_id, text):
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            await client.get(f"{BASE_URL}/sendMessage", params={"chat_id": chat_id, "text": text})
        except httpx.ReadTimeout:
            await asyncio.sleep(5)
            await send_message(chat_id, text)

# دریافت لیست تاپیک‌ها
async def get_forum_topics():
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.get(f"{BASE_URL}/getForumTopicList", params={"chat_id": GROUP_ID})
        data = response.json()
        if data.get("ok"):
            return {topic["message_thread_id"]: topic["name"] for topic in data["result"]["topics"]}
        return {}

# دریافت پیام‌های یک تاپیک خاص
async def get_topic_messages(thread_id):
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.get(f"{BASE_URL}/getUpdates")
        data = response.json()
        if data.get("ok"):
            messages = []
            for update in data["result"]:
                if "message" in update and update["message"].get("message_thread_id") == thread_id:
                    if "audio" in update["message"]:
                        messages.append(update["message"])
            return messages
        return []

# جستجوی آهنگ بر اساس نام و ارسال نتیجه (بدون حذف پیام اصلی)
async def search_and_forward_song(chat_id, query):
    print(f"🔍 جستجو برای: {query}")

    topics = await get_forum_topics()
    found_messages = []

    for thread_id, name in topics.items():
        messages = await get_topic_messages(thread_id)
        for msg in messages:
            audio = msg.get("audio", {})
            title = audio.get("title", "").lower()
            performer = audio.get("performer", "").lower()
            query_lower = query.lower()

            if query_lower in title or query_lower in performer:
                found_messages.append(msg)

    if not found_messages:
        await send_message(chat_id, "⚠️ متأسفم، هیچ آهنگی با این نام پیدا نشد.")
        return

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for msg in found_messages:
            await client.get(f"{BASE_URL}/copyMessage", params={
                "chat_id": chat_id,
                "from_chat_id": GROUP_ID,
                "message_id": msg["message_id"]
            })
            await asyncio.sleep(1)

    print(f"✅ {len(found_messages)} آهنگ ارسال شد.")

# دریافت پیام‌های جدید و پردازش دستورات
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

                            # اگر در چت خصوصی نام آهنگی ارسال شد، جستجو انجام شود
                            if chat_type == "private" and text:
                                await search_and_forward_song(chat_id, text)

                            # اگر آهنگ جدید در گروه ارسال شد، آن را فوروارد و حذف کند
                            elif bot_enabled and "audio" in message and str(message["chat"]["id"]) == GROUP_ID:
                                thread_id = message.get("message_thread_id")
                                await forward_and_delete_music(message, thread_id)
                                await asyncio.sleep(1)

        except Exception as e:
            print(f"⚠️ خطا در `check_new_messages()`: {e}")
            await asyncio.sleep(5)

        await asyncio.sleep(3)

# فوروارد آهنگ‌های جدید و حذف پیام اصلی (برای تاپیک‌ها، نه جستجو)
async def forward_and_delete_music(message, thread_id):
    message_id = message["message_id"]
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        forward_response = await client.get(f"{BASE_URL}/copyMessage", params={
            "chat_id": GROUP_ID,
            "from_chat_id": GROUP_ID,
            "message_id": message_id,
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

# اجرای اصلی
async def main():
    global startup_message_sent
    if not startup_message_sent:
        await send_message(GROUP_ID, "🔥 I'm Ready, brothers!")
        startup_message_sent = True

    while True:
        try:
            await asyncio.gather(
                check_new_messages(),
            )
        except Exception as e:
            print(f"⚠️ کرش غیرمنتظره: {e}")
            print(f"♻️ ری‌استارت در {RESTART_DELAY} ثانیه...")
            await asyncio.sleep(RESTART_DELAY)

if __name__ == "__main__":
    asyncio.run(main())
