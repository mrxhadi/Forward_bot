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

# 📌 **ارسال ۳ آهنگ تصادفی به پیوی**
async def send_random_song(chat_id):
    global song_database

    if not song_database:
        await send_message(chat_id, "⚠️ هنوز هیچ آهنگی ذخیره نشده!")
        return

    songs = random.sample(song_database, min(RANDOM_SONG_COUNT, len(song_database)))

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for song in songs:
            response = await client.get(f"{BASE_URL}/copyMessage", params={
                "chat_id": chat_id,
                "from_chat_id": GROUP_ID,
                "message_id": song["message_id"]
            })

            if not response.json().get("ok"):  
                print(f"⚠️ پیام {song['message_id']} دیگر در گروه وجود ندارد. حذف از دیتابیس...")
                song_database.remove(song)
                save_database(song_database)

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

                            # 📌 **دستورات ربات**
                            if text == "/start":
                                await send_message(chat_id, "🎵 خوش آمدید! از منوی دستورات استفاده کنید: `/random`, `/list`, `/help`")
                            elif text == "/list":
                                await send_file_to_user(chat_id)
                            elif text == "/random":
                                await send_random_song(chat_id)
                            elif text == "/help":
                                await send_message(chat_id, "📌 **دستورات:**\n🎵 `/random` → دریافت ۳ آهنگ تصادفی\n📁 `/list` → دریافت لیست آهنگ‌ها\n❓ `/help` → نمایش راهنما")

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
