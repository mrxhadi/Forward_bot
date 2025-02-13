import os
import requests
import asyncio
import httpx
from datetime import datetime
import pytz

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")

if not BOT_TOKEN or not GROUP_ID:
    raise ValueError("❌ متغیرهای محیطی BOT_TOKEN و GROUP_ID تنظیم نشده‌اند!")

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
bot_enabled = True  
TIMEOUT = 20  
RESTART_DELAY = 10  
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

                            # اگر آهنگ جدید در گروه ارسال شد، آن را فوروارد و حذف کند
                            if bot_enabled and "audio" in message and str(chat_id) == GROUP_ID:
                                thread_id = message.get("message_thread_id")
                                await forward_music_without_caption(message, thread_id)
                                await asyncio.sleep(1)

        except Exception as e:
            print(f"⚠️ خطا در `check_new_messages()`: {e}")
            await asyncio.sleep(5)

        await asyncio.sleep(3)

# فوروارد آهنگ‌های جدید بدون کپشن و حذف پیام اصلی
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
