import json
import os
import httpx
import asyncio

INLINE_DATABASE_FILE = "inline_songs.json"
INLINE_CHANNEL_ID = os.getenv("INLINE_CHANNEL_ID")
BASE_URL = f"https://api.telegram.org/bot{os.getenv('BOT_TOKEN')}"
TIMEOUT = 20

def load_inline_database():
    if os.path.exists(INLINE_DATABASE_FILE):
        with open(INLINE_DATABASE_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    return []

def save_inline_database(data):
    with open(INLINE_DATABASE_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)

async def save_inline_song(title, performer, file_id):
    database = load_inline_database()
    song = {
        "title": title,
        "performer": performer,
        "file_id": file_id
    }
    database.append(song)
    save_inline_database(database)

async def forward_to_inline_channel(file_id, title, performer):
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        await client.get(f"{BASE_URL}/sendAudio", params={
            "chat_id": INLINE_CHANNEL_ID,
            "audio": file_id,
            "title": title,
            "performer": performer
        })
        await save_inline_song(title, performer, file_id)
        await asyncio.sleep(1)

async def handle_document(document, chat_id):
    file_name = document.get("file_name", "")
    if file_name == "songs.json":
        document_name = "songs"
    elif file_name == "inline_songs.json":
        document_name = "inline"
    else:
        await send_message(chat_id, "❌ فایل نامعتبر است.")
        return

    file_id = document["file_id"]
    async with httpx.AsyncClient() as client:
        file_info = await client.get(f"{BASE_URL}/getFile", params={"file_id": file_id})
        file_path = file_info.json()["result"]["file_path"]
        file_url = f"https://api.telegram.org/file/bot{os.getenv('BOT_TOKEN')}/{file_path}"
        response = await client.get(file_url)

        with open(INLINE_DATABASE_FILE, "wb") as file:
            file.write(response.content)

    await send_message(chat_id, f"✅ دیتابیس اینلاین آپدیت شد! تعداد آهنگ‌ها: {len(load_inline_database())}")
