import os
import requests
import asyncio
import httpx

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")

if not BOT_TOKEN or not GROUP_ID:
    raise ValueError("❌ متغیرهای محیطی BOT_TOKEN و GROUP_ID تنظیم نشده‌اند!")

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
bot_enabled = False

# دریافت پیام‌های قدیمی و پردازش آهنگ‌ها
async def process_existing_audios():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/getUpdates")
        data = response.json()

        if data.get("ok"):
            for update in data["result"]:
                if "message" in update:
                    message = update["message"]
                    if "audio" in message and str(message["chat"]["id"]) == GROUP_ID:
                        thread_id = message.get("message_thread_id")  # گرفتن تاپیک آیدی
                        await forward_music(message, thread_id)

# ارسال پیام جدید به تلگرام
async def send_message(text):
    async with httpx.AsyncClient() as client:
        await client.get(f"{BASE_URL}/sendMessage", params={"chat_id": GROUP_ID, "text": text})

# فوروارد کردن آهنگ‌ها به تاپیک خودش
async def forward_music(message, thread_id):
    message_id = message["message_id"]
    async with httpx.AsyncClient() as client:
        await client.get(f"{BASE_URL}/copyMessage", params={
            "chat_id": GROUP_ID,
            "from_chat_id": GROUP_ID,
            "message_id": message_id,
            "message_thread_id": thread_id  # ارسال در همان تاپیک
        })
        await client.get(f"{BASE_URL}/deleteMessage", params={
            "chat_id": GROUP_ID,
            "message_id": message_id
        })

# پردازش دستور `/enable`
async def enable_bot():
    global bot_enabled
    if not bot_enabled:
        bot_enabled = True
        await send_message("✅ ربات فعال شد و پردازش آهنگ‌های قدیمی آغاز شد!")
        await process_existing_audios()
    else:
        await send_message("⚡ ربات قبلاً فعال شده است!")

# دریافت پیام‌های جدید و بررسی آهنگ‌ها
async def check_new_messages():
    last_update_id = None

    while True:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/getUpdates", params={"offset": last_update_id})
            data = response.json()

            if data.get("ok"):
                for update in data["result"]:
                    last_update_id = update["update_id"] + 1
                    if "message" in update:
                        message = update["message"]
                        thread_id = message.get("message_thread_id")  # گرفتن آیدی تاپیک

                        if "text" in message and message["text"] == "/enable":
                            await enable_bot()
                        elif bot_enabled and "audio" in message and str(message["chat"]["id"]) == GROUP_ID:
                            await forward_music(message, thread_id)

        await asyncio.sleep(3)  # هر 3 ثانیه چک کن

# اجرای اصلی
async def main():
    await send_message("🔄 ربات راه‌اندازی شد، منتظر دستور `/enable` هستم...")
    await check_new_messages()

if __name__ == "__main__":
    asyncio.run(main())
