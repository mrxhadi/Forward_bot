import os
import json
import random
import asyncio
import httpx
from datetime import datetime
import pytz
import difflib
from genius import search_song_lyrics

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
async def send_message(chat_id, text, reply_markup=None):
    params = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        params["reply_markup"] = json.dumps(reply_markup)

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        await client.get(f"{BASE_URL}/sendMessage", params=params)

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

# 📌 ارسال ۳ آهنگ تصادفی در پیوی
async def send_random_song(chat_id):
    if not song_database:
        await send_message(chat_id, "⚠️ دیتابیس خالی است!")
        return

    songs = random.sample(song_database, min(RANDOM_SONG_COUNT, len(song_database)))
    async with httpx.AsyncClient() as client:
        for song in songs:
            try:
                # استفاده از `.get()` برای جلوگیری از خطای `title`
                title = song.get("title", "نامشخص")
                performer = song.get("performer", "نامشخص")

                if "message_id" not in song:
                    print(f"⚠️ خطا: پیام ایدی در آهنگ '{title}' موجود نیست.")
                    continue  # این آهنگ را رد کن

                response = await client.get(f"{BASE_URL}/copyMessage", params={
                    "chat_id": chat_id,
                    "from_chat_id": GROUP_ID,
                    "message_id": song["message_id"]
                })
                
                response_data = response.json()
                if not response_data.get("ok"):
                    print(f"⚠️ خطا در ارسال آهنگ {title}: {response_data}")
                    
                    # اگر پیام پیدا نشد، از دیتابیس حذف شود
                    if response_data.get("error_code") == 400 and "message to copy not found" in response_data.get("description", ""):
                        song_database.remove(song)
                        save_database(song_database)

            except Exception as e:
                print(f"⚠️ خطا در ارسال آهنگ تصادفی: {e}")

            await asyncio.sleep(1)  # جلوگیری از محدودیت API
            
# 📌 **ارسال پیام**
async def send_message(chat_id, text, reply_markup=None):
    params = {
        "chat_id": chat_id,
        "text": text,
    }
    if reply_markup:
        params["reply_markup"] = json.dumps(reply_markup)

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        await client.get(f"{BASE_URL}/sendMessage", params=params)

# 📌 **جستجو در دیتابیس و ارسال نتایج به کاربر**
async def search_song(chat_id, query):
    query = query.lower()
    
    # دریافت لیست عنوان‌های آهنگ‌ها از دیتابیس
    song_matches = []
    for song in song_database:
        title = song.get("title", "").lower()
        performer = song.get("performer", "").lower()
        similarity = difflib.SequenceMatcher(None, query, title).ratio()  # محاسبه میزان شباهت
        
        if similarity > 0.4:  # فقط آهنگ‌های با ۴۰٪ شباهت یا بیشتر نمایش داده شوند
            song_matches.append((similarity, song))

    # مرتب‌سازی آهنگ‌ها بر اساس شباهت (بیشترین شباهت اول)
    song_matches.sort(reverse=True, key=lambda x: x[0])

    # محدود کردن به ۵ نتیجه برتر
    top_results = song_matches[:5]

    # اگر هیچ آهنگی پیدا نشد
    if not top_results:
        await send_message(chat_id, "نتیجه‌ای یافت نشد.")
        return

    # ارسال هر نتیجه در یک پیام جداگانه
    for _, song in top_results:
        await send_message(chat_id, f"{song['title']} - {song['performer']}")
        await asyncio.sleep(0.5)  # جلوگیری از محدودیت API

    # ارسال پیام نهایی بعد از همه نتایج
    await send_message(chat_id, "اسمو کپی کن و بهم بده تا آهنگو برات بفرستم.")      
    
# 📌 **فوروارد آهنگ‌های جدید بدون کپشن و حذف پیام اصلی**
async def forward_music_without_caption(message, thread_id):
    message_id = message["message_id"]
    audio = message["audio"]

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            forward_response = await client.get(f"{BASE_URL}/sendAudio", params={
                "chat_id": GROUP_ID,
                "audio": audio["file_id"],
                "message_thread_id": thread_id,
                "caption": ""  
            })

            forward_data = forward_response.json()
            if forward_data.get("ok"):
                new_message_id = forward_data["result"]["message_id"]

                # ذخیره در دیتابیس با استفاده از `.get()` برای جلوگیری از خطای `title`
                song_database.append({
                    "title": audio.get("title", "نامشخص"),
                    "performer": audio.get("performer", "نامشخص"),
                    "message_id": new_message_id,
                    "thread_id": thread_id
                })
                save_database(song_database)

                # حذف پیام اصلی
                await asyncio.sleep(1)
                await client.get(f"{BASE_URL}/deleteMessage", params={
                    "chat_id": GROUP_ID,
                    "message_id": message_id
                })

        except Exception as e:
            print(f"⚠️ خطا در فوروارد آهنگ: {e}")
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

                        # ✅ بررسی دستور `/start`
                        if text == "/start":
                            await send_message(chat_id, " /help از منوی دستورات استفاده کن")

                        # ✅ دریافت فایل دیتابیس
                        elif "document" in message:
                            await handle_document(message["document"], chat_id)

                        # ✅ جستجو در دیتابیس
                        elif text.startswith("/search "):
                            query = text.replace("/search ", "").strip()
                            await search_song(chat_id, query)

                        # ✅ ارسال آهنگ موردنظر در صورت موجود بودن در دیتابیس
                        elif any(text.lower() == f"{song['title']} - {song['performer']}".lower() for song in song_database):
                            print(f"🔍 تشخیص داده شد که کاربر درخواست ارسال آهنگ دارد: {text}")
                            await send_selected_song(chat_id, text)

                        # ✅ ارسال آهنگ رندوم
                        elif text == "/random":
                            await send_random_song(chat_id)

                        # ✅ ارسال فایل دیتابیس
                        elif text == "/list":
                            await send_file_to_user(chat_id)

                        # ✅ نمایش راهنما
                        elif text == "/help":
                             help_text = (
                                 "دستورات ربات:\n"
                                 "/random - سه تا آهنگ رندوم بگیر\n"
                                 "/search [اسم آهنگ] - جستجوی آهنگ\n"
                                 "/lyrics [اسم آهنگ] - دریافت متن آهنگ\n\n"
                                 "مثال:\n"
                                 "/search wanted"
               )
                             await send_message(chat_id, help_text)
                        
                        # ✅ بررسی ارسال آهنگ جدید و فوروارد آن در گروه
                        elif "audio" in message and str(chat_id) == GROUP_ID:
                            await forward_music_without_caption(message, message.get("message_thread_id"))

        except Exception as e:
            print(f"⚠️ خطا: {e}")
            await asyncio.sleep(5)

        await asyncio.sleep(3)

# 📌 ارسال آهنگ انتخاب‌شده توسط کاربر
async def send_selected_song(chat_id, song_name):
    print(f"🎵 دریافت درخواست ارسال آهنگ: {song_name}")

    # **بررسی آهنگ موردنظر در دیتابیس**
    selected_song = next(
        (song for song in song_database if "title" in song and "performer" in song and f"{song['title']} - {song['performer']}".strip().lower() == song_name.strip().lower()),
        None
    )

    if not selected_song:
        await send_message(chat_id, "⚠️ آهنگ موردنظر یافت نشد!")
        print(f"⚠️ خطا: آهنگ پیدا نشد! مقدار دریافت‌شده: {song_name}")
        return

    if "message_id" not in selected_song:
        await send_message(chat_id, "⚠️ خطا در یافتن آهنگ!")
        print(f"⚠️ خطا: message_id در آهنگ موجود نیست! داده‌های آهنگ: {selected_song}")
        return

    print(f"✅ آهنگ پیدا شد: {selected_song['title']} - {selected_song['performer']}")

    async with httpx.AsyncClient() as client:
        await client.get(f"{BASE_URL}/copyMessage", params={
            "chat_id": chat_id,
            "from_chat_id": GROUP_ID,
            "message_id": selected_song["message_id"]
        })
        
# 📌 **اجرای اصلی**
async def main():
    await send_message(GROUP_ID, "🔥 I'm Ready, brothers!")
    asyncio.create_task(check_time_for_scheduled_task())
    await check_new_messages()

if __name__ == "__main__":
    asyncio.run(main())

    
