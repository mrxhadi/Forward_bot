import os
import requests
import asyncio
import httpx
import json

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")
DATABASE_FILE = "songs.json"

if not BOT_TOKEN or not GROUP_ID:
    raise ValueError("❌ متغیرهای محیطی BOT_TOKEN و GROUP_ID تنظیم نشده‌اند!")

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
bot_enabled = True  
TIMEOUT = 20  
RESTART_DELAY = 10  

# 📌 **ارسال فایل `songs.json` به پیوی ارسال‌کننده دستور `/list`**
async def send_file_to_user(user_id):
    if os.path.exists(DATABASE_FILE):
        async with httpx.AsyncClient() as client:
            with open(DATABASE_FILE, "rb") as file:
                files = {"document": file}
                params = {"chat_id": user_id}
                await client.post(f"{BASE_URL}/sendDocument", params=params, files=files)
    else:
        await send_message(user_id, "⚠️ هنوز هیچ آهنگی ذخیره نشده!")

# 📌 **ارسال پیام متنی به چت موردنظر**
async def send_message(chat_id, text):
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            await client.get(f"{BASE_URL}/sendMessage", params={"chat_id": chat_id, "text": text})
        except httpx.ReadTimeout:
            await asyncio.sleep(5)
            await send_message(chat_id, text)

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
                            text = message.get("text", "")

                            # 📌 **اگر دستور `/list` در گروه فرستاده شد، فایل را به پیوی کاربر ارسال کند**
                            if text.strip() == "/list":
                                user_id = message["from"]["id"]  # استخراج آی‌دی فرستنده دستور
                                if str(chat_id) == GROUP_ID:  # اگر پیام در گروه باشه
                                    await send_message(chat_id, "📩 فایل به پیوی شما ارسال شد.")
                                    await send_file_to_user(user_id)
                                else:  # اگر پیام در پیوی باشه، مستقیم فایل رو بفرسته
                                    await send_file_to_user(chat_id)

        except Exception as e:
            print(f"⚠️ خطا در `check_new_messages()`: {e}")
            await asyncio.sleep(5)

        await asyncio.sleep(3)

# 📌 **اجرای اصلی ربات**
async def main():
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
