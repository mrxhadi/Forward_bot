import os
import requests
import asyncio
import httpx

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")

if not BOT_TOKEN or not GROUP_ID:
    raise ValueError("❌ متغیرهای محیطی BOT_TOKEN و GROUP_ID تنظیم نشده‌اند!")

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
bot_enabled = True  # ربات همیشه فعال باشد
TIMEOUT = 20  # افزایش زمان تایم‌اوت به 20 ثانیه
startup_message_sent = False  # جلوگیری از ارسال پیام خوشامدگویی تکراری

# ارسال پیام جدید به تلگرام
async def send_message(text):
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            await client.get(f"{BASE_URL}/sendMessage", params={"chat_id": GROUP_ID, "text": text})
        except httpx.ReadTimeout:
            print("⏳ درخواست تایم‌اوت شد! تلاش مجدد...")
            await asyncio.sleep(5)
            await send_message(text)

# فوروارد کردن آهنگ‌ها بدون کپشن و بررسی قبل از حذف
async def forward_music(message, thread_id):
    message_id = message["message_id"]
    has_caption = "caption" in message
    forwarded_message = None  # ذخیره پیام فوروارد شده

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            # اگر آهنگ کپشن دارد، بدون کپشن فوروارد کنیم
            if has_caption:
                response = await client.get(f"{BASE_URL}/sendAudio", params={
                    "chat_id": GROUP_ID,
                    "audio": message["audio"]["file_id"],
                    "message_thread_id": thread_id
                })
                response_data = response.json()
                if response_data.get("ok"):
                    forwarded_message = response_data["result"]["message_id"]
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

            # بررسی اگر پیام فوروارد شد، پیام اصلی را حذف کنیم
            if forwarded_message:
                await asyncio.sleep(0.5)  # جلوگیری از Rate Limit
                delete_response = await client.get(f"{BASE_URL}/deleteMessage", params={
                    "chat_id": GROUP_ID,
                    "message_id": message_id
                })
                delete_data = delete_response.json()
                if not delete_data.get("ok"):
                    print(f"⚠️ پیام {message_id} حذف نشد: {delete_data['description']}")
            else:
                print(f"❌ پیام {message_id} فوروارد نشد، پس حذف نمی‌شود.")

        except httpx.ReadTimeout:
            print("⏳ درخواست تایم‌اوت شد! تلاش مجدد در 5 ثانیه...")
            await asyncio.sleep(5)
            await forward_music(message, thread_id)

# دریافت پیام‌های جدید و بررسی آهنگ‌ها
async def check_new_messages():
    last_update_id = None

    while True:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            try:
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
                                await asyncio.sleep(0.8)  # جلوگیری از بلاک شدن توسط تلگرام

            except httpx.ReadTimeout:
                print("⏳ تایم‌اوت در دریافت پیام‌های جدید! تلاش مجدد...")
                await asyncio.sleep(5)

        await asyncio.sleep(3)

# اجرای اصلی
async def main():
    global startup_message_sent
    if not startup_message_sent:
        await send_message("🔥 I'm Ready, brothers!")
        startup_message_sent = True
    await check_new_messages()

if __name__ == "__main__":
    asyncio.run(main())
