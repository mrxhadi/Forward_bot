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

# ارسال پیام جدید به تلگرام
async def send_message(text):
    async with httpx.AsyncClient() as client:
        await client.get(f"{BASE_URL}/sendMessage", params={"chat_id": GROUP_ID, "text": text})

# فوروارد کردن آهنگ‌ها بدون کپشن و بررسی قبل از حذف
async def forward_music(message, thread_id):
    message_id = message["message_id"]
    has_caption = "caption" in message  # بررسی وجود کپشن
    forwarded_message = None  # ذخیره پیام فوروارد شده

    async with httpx.AsyncClient() as client:
        # اگر آهنگ کپشن دارد، بدون کپشن فوروارد کنیم
        if has_caption:
            response = await client.get(f"{BASE_URL}/sendAudio", params={
                "chat_id": GROUP_ID,
                "audio": message["audio"]["file_id"],  # ارسال فقط فایل آهنگ
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
            delete_response = await client.get(f"{BASE_URL}/deleteMessage", params={
                "chat_id": GROUP_ID,
                "message_id": message_id
            })
            delete_data = delete_response.json()
            if not delete_data.get("ok"):  # اگر حذف پیام ناموفق بود، نمایش دلیل
                print(f"⚠️ پیام {message_id} حذف نشد: {delete_data['description']}")
        else:
            print(f"❌ پیام {message_id} فوروارد نشد، پس حذف نمی‌شود.")

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
                        thread_id = message.get("message_thread_id")

                        if bot_enabled and "audio" in message and str(message["chat"]["id"]) == GROUP_ID:
                            await forward_music(message, thread_id)

        await asyncio.sleep(3)  # هر 3 ثانیه چک کن

# اجرای اصلی
async def main():
    await send_message("I'm Ready brothers!")
    await check_new_messages()

if __name__ == "__main__":
    asyncio.run(main())
