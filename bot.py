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
bot_enabled = True  # ربات همیشه فعال باشد
TIMEOUT = 20  # افزایش زمان تایم‌اوت به 20 ثانیه
startup_message_sent = False  # جلوگیری از ارسال پیام خوشامدگویی تکراری
MAX_RETRIES = 3  # تعداد تلاش‌های مجدد برای ارسال پیام
RANDOM_SONG_COUNT = 3  # تعداد آهنگ‌های تصادفی برای ارسال به 11:11
RESTART_DELAY = 10  # اگر ربات کرش کند، بعد از ۱۰ ثانیه دوباره راه‌اندازی می‌شود

# لیست تاپیک‌هایی که **فقط برای ارسال تصادفی** نادیده گرفته شوند
EXCLUDED_TOPICS_RANDOM = ["Nostalgic", "Golchin-e Shad-e Irooni"]

# تنظیم منطقه زمانی ایران
IRAN_TZ = pytz.timezone("Asia/Tehran")

# ارسال پیام جدید به تلگرام
async def send_message(text):
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            await client.get(f"{BASE_URL}/sendMessage", params={"chat_id": GROUP_ID, "text": text})
        except httpx.ReadTimeout:
            await asyncio.sleep(5)
            await send_message(text)

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
        response = await client.get(f"{BASE_URL}/getForumTopicMessages", params={"chat_id": GROUP_ID, "message_thread_id": thread_id})
        data = response.json()
        if data.get("ok"):
            return [msg for msg in data["result"]["messages"] if "audio" in msg]
        return []

# پیدا کردن تاپیک "11:11"
async def get_11_11_topic():
    topics = await get_forum_topics()
    for thread_id, name in topics.items():
        if name == "11:11":
            return thread_id
    return None

# فوروارد کردن آهنگ‌های جدید
async def forward_music(message, thread_id):
    message_id = message["message_id"]
    has_caption = "caption" in message
    forwarded_message = None  

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for attempt in range(MAX_RETRIES):
            try:
                if has_caption:
                    response = await client.get(f"{BASE_URL}/sendAudio", params={
                        "chat_id": GROUP_ID,
                        "audio": message["audio"]["file_id"],
                        "message_thread_id": thread_id
                    })
                else:
                    response = await client.get(f"{BASE_URL}/copyMessage", params={
                        "chat_id": GROUP_ID,
                        "from_chat_id": GROUP_ID,
                        "message_id": message_id,
                        "message_thread_id": thread_id
                    })

                response_data = response.json()
                if response_data.get("ok"):
                    forwarded_message = response_data["result"]["message_id"]
                    break  
                else:
                    await asyncio.sleep(2)  
            except httpx.ReadTimeout:
                await asyncio.sleep(5)

        if forwarded_message:
            await asyncio.sleep(1)  
            delete_response = await client.get(f"{BASE_URL}/deleteMessage", params={
                "chat_id": GROUP_ID,
                "message_id": message_id
            })
            delete_data = delete_response.json()
            if not delete_data.get("ok"):  
                print(f"⚠️ پیام {message_id} حذف نشد: {delete_data['description']}")

# انتخاب و ارسال ۳ آهنگ شانسی به تاپیک "11:11"
async def forward_random_music():
    try:
        topics = await get_forum_topics()
        selected_messages = []

        for thread_id, name in topics.items():
            if name not in EXCLUDED_TOPICS_RANDOM:  
                messages = await get_topic_messages(thread_id)
                selected_messages.extend(messages)

        if len(selected_messages) >= RANDOM_SONG_COUNT:
            random_messages = random.sample(selected_messages, RANDOM_SONG_COUNT)
        else:
            random_messages = selected_messages  

        topic_11_11 = await get_11_11_topic()
        if not topic_11_11:
            return  

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            for message in random_messages:
                message_id = message["message_id"]
                await client.get(f"{BASE_URL}/copyMessage", params={
                    "chat_id": GROUP_ID,
                    "from_chat_id": GROUP_ID,
                    "message_id": message_id,
                    "message_thread_id": topic_11_11
                })
                await asyncio.sleep(1)  
    except Exception as e:
        print(f"⚠️ خطا در `forward_random_music()`: {e}")

# بررسی زمان و اجرای وظایف شبانه
async def check_time_for_scheduled_task():
    while True:
        now = datetime.now(IRAN_TZ)
        if now.hour == 23 and now.minute == 11:  
            await forward_random_music()
            await asyncio.sleep(60)  
        await asyncio.sleep(10)  

# دریافت پیام‌های جدید و بررسی آهنگ‌ها
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
                            thread_id = message.get("message_thread_id")

                            if bot_enabled and "audio" in message and str(message["chat"]["id"]) == GROUP_ID:
                                await forward_music(message, thread_id)
                                await asyncio.sleep(1)
        except Exception as e:
            print(f"⚠️ خطا در `check_new_messages()`: {e}")
            await asyncio.sleep(5)

        await asyncio.sleep(3)

# اجرای اصلی با مکانیسم Restart خودکار
async def main():
    global startup_message_sent
    if not startup_message_sent:
        await send_message("🔥 I'm Ready, brothers!")
        startup_message_sent = True

    while True:
        try:
            await asyncio.gather(
                check_new_messages(),
                check_time_for_scheduled_task()
            )
        except Exception as e:
            print(f"⚠️ کرش غیرمنتظره: {e}")
            print(f"♻️ ری‌استارت در {RESTART_DELAY} ثانیه...")
            await asyncio.sleep(RESTART_DELAY)

if __name__ == "__main__":
    asyncio.run(main())
