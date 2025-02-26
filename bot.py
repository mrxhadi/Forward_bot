import os
import json
import random
import asyncio
import httpx
from datetime import datetime
import pytz
from difflib import get_close_matches

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
    params = {
        "chat_id": chat_id,
        "text": text
    }

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            response = await client.get(f"{BASE_URL}/sendMessage", params=params)
            response_data = response.json()
            if not response_data.get("ok"):
                print(f"⚠️ خطا در ارسال پیام: {response_data}")

        except Exception as e:
            print(f"⚠️ خطا در `send_message`: {e}")

# 📌 **ارسال ۳ آهنگ تصادفی در پیوی**
async def send_random_song(chat_id):
    if not song_database:
        await send_message(chat_id, "⚠️ دیتابیس خالی است!")
        return

    songs = random.sample(song_database, min(RANDOM_SONG_COUNT, len(song_database)))

    async with httpx.AsyncClient() as client:
        for song in songs:
            try:
                # چک کردن اینکه مقدار title و performer در آهنگ وجود دارد
                title = song.get("title", "نامشخص")
                performer = song.get("performer", "نامشخص")
                message_id = song.get("message_id")

                if not message_id:
                    print(f"⚠️ خطا: پیام ایدی در آهنگ '{title}' موجود نیست. از دیتابیس حذف شد.")
                    song_database.remove(song)
                    save_database(song_database)
                    continue  # آهنگ بعدی بررسی شود

                if title == "نامشخص":
                    print(f"⚠️ هشدار: مقدار `title` برای این آهنگ در دیتابیس موجود نیست → {song}")

                response = await client.get(f"{BASE_URL}/copyMessage", params={
                    "chat_id": chat_id,
                    "from_chat_id": GROUP_ID,
                    "message_id": message_id
                })
                
                response_data = response.json()
                if not response_data.get("ok"):
                    print(f"⚠️ خطا در ارسال آهنگ {title}: {response_data}")

                    # حذف از دیتابیس در صورتی که پیام اصلی وجود نداشته باشد
                    if response_data.get("error_code") == 400 and "message to copy not found" in response_data.get("description", ""):
                        song_database.remove(song)
                        save_database(song_database)

            except KeyError as e:
                print(f"❌ خطای KeyError: کلید {e} در این آهنگ موجود نیست → {song}")
            except Exception as e:
                print(f"⚠️ خطا در ارسال آهنگ تصادفی: {e}")

            await asyncio.sleep(1)  # جلوگیری از بلاک شدن توسط تلگرام

# 📌 **جستجو در دیتابیس**
import difflib

# 📌 **جستجو در دیتابیس و ارسال نتایج به کاربر**
async def search_song(chat_id, query):
    query = query.lower()
    
    # مقایسه شباهت
    results = [
        song for song in song_database 
        if query in song.get("title", "").lower()
    ]
    
    if not results:
        await send_message(chat_id, "❌ هیچ آهنگی در دیتابیس پیدا نشد!")
        return

    # 📌 محدود کردن نتایج به پنج تا
    results = results[:5]
    
    # محاسبه شباهت برای هر آهنگ و مرتب کردن بر اساس شباهت
    results_sorted = sorted(
        results, 
        key=lambda song: difflib.SequenceMatcher(None, query, song["title"].lower()).ratio(), 
        reverse=True
    )
    
    # ارسال نتایج به صورت جداگانه
    for song in results_sorted:
        title = song.get("title", "نامشخص")
        performer = song.get("performer", "نامشخص")
        await send_message(chat_id, f"{title} - {performer}")
        await asyncio.sleep(1)  # جلوگیری از ارسال سریع و محدودیت‌های API

    # بعد از ارسال همه نتایج
    await send_message(chat_id, "اسمو کپی کن و بفرست تا اهنگو برات بفرستم.")

# 📌 ارسال آهنگ انتخابی توسط کاربر
async def send_selected_song(chat_id, song):
    try:
        # اطمینان از صحت message_id
        message_id = song.get("message_id")
        if not message_id:
            print(f"⚠️ خطا: `message_id` برای آهنگ {song['title']} یافت نشد.")
            return
        
        print(f"ارسال آهنگ: {song['title']} - {song['performer']}")  # نمایش نام آهنگ

        # ارسال آهنگ به کاربر
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/copyMessage", params={
                "chat_id": chat_id,
                "from_chat_id": GROUP_ID,
                "message_id": message_id
            })
        
        response_data = response.json()

        if response_data.get("ok"):
            print(f"آهنگ {song['title']} با موفقیت ارسال شد!")
        else:
            print(f"⚠️ خطا در ارسال آهنگ {song['title']}: {response_data}")
    except Exception as e:
        print(f"⚠️ خطا در ارسال آهنگ: {e}")
        
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
                "title": audio.get("title", "نامشخص"),
                "performer": audio.get("performer", "نامشخص"),
                "message_id": new_message_id,
                "thread_id": thread_id
            })
            save_database(song_database)

            await asyncio.sleep(1)
            await client.get(f"{BASE_URL}/deleteMessage", params={
                "chat_id": GROUP_ID,
                "message_id": message_id
            })

# 📌 تابع چک کردن پیام‌های جدید
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

                        # لاگ پیام دریافتی
                        print(f"پیام دریافت شده: {text}")

                        # اگر پیام جستجو باشد، جستجو را انجام بده
                        if text.startswith("/search "):
                            query = text.replace("/search ", "").strip()
                            print(f"جستجو با عبارت: {query}")  # لاگ عبارت جستجو
                            await search_song(chat_id, query)

                        # بررسی اینکه آیا نام آهنگ انتخابی درست است
                        elif text in [f"{song['title']} - {song['performer']}" for song in song_database]:
                            selected_song = next(song for song in song_database if f"{song['title']} - {song['performer']}" == text)
                            print(f"آهنگ انتخاب‌شده: {selected_song['title']} - {selected_song['performer']}")  # لاگ آهنگ انتخاب‌شده
                            await send_selected_song(chat_id, selected_song)
                        
                        # سایر دستورات
                        elif text == "/random":
                            await send_random_song(chat_id)
                        elif text == "/list":
                            await send_file_to_user(chat_id)
                        elif text == "/help":
                            await send_message(chat_id, "دستورات ربات:\n/random - سه تا آهنگ رندوم بگیر\n/search - جلوی این دستور اسم آهنگو بنویس تا دنبالش بگردم\n/help - نمایش دستورات")

        except Exception as e:
            print(f"⚠️ خطا در پردازش پیام‌ها: {e}")
            await asyncio.sleep(5)

        await asyncio.sleep(3)
        
# 📌 **ارسال ۳ آهنگ تصادفی به `11:11` هر شب**
async def send_random_songs_to_11_11():
    if not song_database:
        return

    filtered_songs = [song for song in song_database if song.get("thread_id") not in EXCLUDED_TOPICS_RANDOM]

    if not filtered_songs:
        return

    songs = random.sample(filtered_songs, min(RANDOM_SONG_COUNT, len(filtered_songs)))

    async with httpx.AsyncClient() as client:
        for song in songs:
            await client.get(f"{BASE_URL}/copyMessage", params={
                "chat_id": GROUP_ID,
                "from_chat_id": GROUP_ID,
                "message_id": song["message_id"],
                "message_thread_id": TOPIC_11_11_ID  
            })
            await asyncio.sleep(1)

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

    # 🚀 دیتابیس را مجدد بارگذاری کن
    global song_database
    song_database = load_database()
    
    await send_message(chat_id, f"✅ دیتابیس آپدیت شد! تعداد آهنگ‌ها: {len(song_database)}")
# 📌 **اجرای اصلی**
async def main():
    await send_message(GROUP_ID, "🔥 I'm Ready, brothers!")
    await check_new_messages()

if __name__ == "__main__":
    asyncio.run(main())
