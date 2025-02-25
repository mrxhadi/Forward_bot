import os
import json
import random
import asyncio
import httpx
from datetime import datetime
import pytz
import difflib

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")
DATABASE_FILE = "songs.json"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
TIMEOUT = 20  
RESTART_DELAY = 10  
RANDOM_SONG_COUNT = 3  

IRAN_TZ = pytz.timezone("Asia/Tehran")
EXCLUDED_TOPICS_RANDOM = ["G(old)", "gym"]
TOPIC_11_11_ID = 2463  # 📌 تاپیک `11:11`

# 📌 **لود و ذخیره دیتابیس**
def load_database():
    if os.path.exists(DATABASE_FILE):
        with open(DATABASE_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    return []

def save_database(data):
    with open(DATABASE_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)

song_database = load_database()

# 📌 **ارسال پیام به تلگرام**
async def send_message(chat_id, text):
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        await client.get(f"{BASE_URL}/sendMessage", params={
            "chat_id": chat_id,
            "text": text
        })

# 📌 **دریافت و پردازش فایل `songs.json`**
async def handle_document(document, chat_id):
    file_name = document["file_name"]
    
    if file_name != "songs.json":
        await send_message(chat_id, "⚠️ لطفاً `songs.json` ارسال کنید.")
        return

    file_id = document["file_id"]
    async with httpx.AsyncClient() as client:
        file_info = await client.get(f"{BASE_URL}/getFile", params={"file_id": file_id})
        file_path = file_info.json()["result"]["file_path"]
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        response = await client.get(file_url)

        with open(DATABASE_FILE, "wb") as file:
            file.write(response.content)

    song_database[:] = load_database()
    await send_message(chat_id, f"✅ دیتابیس آپدیت شد! تعداد آهنگ‌ها: {len(song_database)}")

# 📌 **ارسال دیتابیس در پاسخ به `/list`**
async def send_file_to_user(chat_id):
    if os.path.exists(DATABASE_FILE):
        async with httpx.AsyncClient() as client:
            with open(DATABASE_FILE, "rb") as file:
                await client.post(f"{BASE_URL}/sendDocument", params={"chat_id": chat_id}, files={"document": file})
    else:
        await send_message(chat_id, "⚠️ هنوز هیچ آهنگی ذخیره نشده!")

# 📌 **ارسال ۳ آهنگ تصادفی در پیوی**
async def send_random_song(chat_id):
    if not song_database:
        await send_message(chat_id, "⚠️ دیتابیس خالی است!")
        return

    songs = random.sample(song_database, min(RANDOM_SONG_COUNT, len(song_database)))
    async with httpx.AsyncClient() as client:
        for song in songs:
            response = await client.get(f"{BASE_URL}/copyMessage", params={
                "chat_id": chat_id,
                "from_chat_id": GROUP_ID,
                "message_id": song["message_id"]
            })

            if not response.json().get("ok"):
                song_database.remove(song)
                save_database(song_database)

# 📌 **جستجو در دیتابیس و ارسال نتایج به کاربر**
async def search_song(chat_id, query):
    query = query.lower().strip()
    
    # 📌 دریافت عناوین آهنگ‌ها برای مقایسه
    title_map = {song.get("title", "").lower(): song for song in song_database}
    titles = list(title_map.keys())

    # 📌 پیدا کردن ۵ نتیجه با بیشترین شباهت
    closest_matches = difflib.get_close_matches(query, titles, n=5, cutoff=0.4)

    results = [title_map[title] for title in closest_matches]

    if not results:
        await send_message(chat_id, "❌ هیچ آهنگی در دیتابیس پیدا نشد!")
        return

    # 📌 ایجاد لیست نتایج به همراه فضای ویژه برای کپی کردن
    song_list = "\n".join([f"‎{song['title']} - {song['performer']}" for song in results])

    response_text = "🎵 **نتایج جستجو:**\n" + song_list + "\n\n✏️ **روی یکی از نام‌ها کلیک کرده و ارسال کنید تا آهنگ فوروارد شود.**"

    await send_message(chat_id, response_text)
    
# 📌 **فوروارد آهنگ‌های جدید بدون کپشن و حذف پیام اصلی**
async def forward_music_without_caption(message, thread_id):
    message_id = message["message_id"]
    audio = message["audio"]

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        forward_response = await client.get(f"{BASE_URL}/sendAudio", params={
            "chat_id": GROUP_ID,
            "audio": audio["file_id"],
            "message_thread_id": thread_id,
            "caption": ""  
        })

        forward_data = forward_response.json()
        if forward_data.get("ok"):
            new_message_id = forward_data["result"]["message_id"]
            song_database.append({
                "message_id": new_message_id,
                "thread_id": thread_id
            })
            save_database(song_database)

            await asyncio.sleep(1)
            await client.get(f"{BASE_URL}/deleteMessage", params={
                "chat_id": GROUP_ID,
                "message_id": message_id
            })

# 📌 **ارسال ۳ آهنگ تصادفی به `11:11` هر شب**
async def send_random_songs_to_11_11():
    if not song_database:
        print("⚠️ خطا: دیتابیس آهنگ‌ها خالی است.")
        return

    # 📌 لیست جدید تاپیک‌هایی که نباید در انتخاب تصادفی باشند
    EXCLUDED_TOPICS_RANDOM = ["G(old)", "gym"]  # 🔹 نام‌های جدید جایگزین شوند

    # 🎯 فیلتر کردن آهنگ‌ها برای حذف آهنگ‌های تاپیک‌های ممنوعه
    filtered_songs = [song for song in song_database if song.get("thread_id") not in EXCLUDED_TOPICS_RANDOM]

    if not filtered_songs:
        print("⚠️ خطا: بعد از فیلتر کردن، هیچ آهنگی برای ارسال باقی نماند!")
        return

    songs = random.sample(filtered_songs, min(RANDOM_SONG_COUNT, len(filtered_songs)))

    async with httpx.AsyncClient() as client:
        for song in songs:
            try:
                response = await client.get(f"{BASE_URL}/copyMessage", params={
                    "chat_id": GROUP_ID,
                    "from_chat_id": GROUP_ID,
                    "message_id": song["message_id"],
                    "message_thread_id": TOPIC_11_11_ID  
                })
                response_data = response.json()

                if not response_data.get("ok"):
                    print(f"⚠️ خطا در ارسال آهنگ {song['message_id']}: {response_data}")
            except Exception as e:
                print(f"⚠️ خطا در ارسال آهنگ {song['message_id']}: {e}")
            await asyncio.sleep(1)
            
# 📌 **بررسی زمان و اجرای وظایف شبانه**
async def check_time_for_scheduled_task():
    while True:
        now = datetime.now(IRAN_TZ)
        if now.hour == 23 and now.minute == 11:
            print("🕚 ارسال آهنگ‌های `11:11` شروع شد...")
            try:
                await send_random_songs_to_11_11()
                print("✅ آهنگ‌های `11:11` ارسال شدند.")
            except Exception as e:
                print(f"⚠️ خطا در اجرای `11:11`: {e}")
            await asyncio.sleep(70)  
        await asyncio.sleep(30)

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
                        message = update.get("message", {})
                        chat_id = message.get("chat", {}).get("id")
                        text = message.get("text", "").strip()

                        if text == "/start":
                            await send_message(chat_id, " /help از منوی دستورات استفاده کن")
                        elif "document" in message:
                            await handle_document(message["document"], chat_id)
                        elif text.startswith("/search "):
                            query = text.replace("/search ", "").strip()
                            await search_song(chat_id, query)
                        elif any(f"{song.get('title', 'بدون عنوان')} - {song.get('performer', 'ناشناخته')}" == text for song in song_database):
                            selected_song = next((song for song in song_database if f"{song.get('title', 'بدون عنوان')} - {song.get('performer', 'ناشناخته')}" == text), None)
    
                            if selected_song:
                                await send_selected_song(chat_id, selected_song)
                            else:
                                await send_message(chat_id, "❌ خطا: آهنگ موردنظر در دیتابیس یافت نشد!")
                        elif text == "/random":
                            await send_random_song(chat_id)
                        elif text == "/list":
                            await send_file_to_user(chat_id)
                        elif text == "/help":
                            await send_message(chat_id, " **دستورات ربات:**\n"
                                " `/random` - سه تا آهنگ رندوم بگیر\n"
                                " `/search` - جلوی این دستور اسم آهنگو بنویس تا دنبالش بگردم\n"
                                " **مثال:**\n"
                                "`/search wanted`")
                        elif "audio" in message and str(chat_id) == GROUP_ID:
                            await forward_music_without_caption(message, message.get("message_thread_id"))

        except Exception as e:
            print(f"⚠️ خطا: {e}")
            await asyncio.sleep(5)

        await asyncio.sleep(3)

# 📌 ارسال آهنگ انتخاب‌شده توسط کاربر
async def send_selected_song(chat_id, song):
    async with httpx.AsyncClient() as client:
        await client.get(f"{BASE_URL}/copyMessage", params={
            "chat_id": chat_id,
            "from_chat_id": GROUP_ID,
            "message_id": song["message_id"]
        })

# 📌 **اجرای اصلی**
async def main():
    await send_message(GROUP_ID, "🔥 I'm Ready, brothers!")
    asyncio.create_task(check_time_for_scheduled_task())
    await check_new_messages()

if __name__ == "__main__":
    asyncio.run(main())
    
