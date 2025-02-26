import os
import httpx
from bs4 import BeautifulSoup

# گرفتن توکن از متغیر محیطی
GENIUS_ACCESS_TOKEN = os.getenv("GENIUS_ACCESS_TOKEN")
BASE_URL = "https://api.genius.com"

# 📌 جستجوی آهنگ در Genius
async def search_song_lyrics(song_name):
    if not GENIUS_ACCESS_TOKEN:
        return "⚠️ خطا: توکن Genius تنظیم نشده!"

    async with httpx.AsyncClient() as client:
        # جستجو در API
        headers = {"Authorization": f"Bearer {GENIUS_ACCESS_TOKEN}"}
        search_url = f"{BASE_URL}/search"
        response = await client.get(search_url, headers=headers, params={"q": song_name})

        if response.status_code != 200:
            return f"⚠️ خطا در درخواست: {response.status_code}"

        data = response.json()
        if not data["response"]["hits"]:
            return "❌ متن این آهنگ در دیتابیس Genius پیدا نشد."

        # دریافت اولین نتیجه مرتبط
        song_info = data["response"]["hits"][0]["result"]
        song_title = song_info["title"]
        song_artist = song_info["primary_artist"]["name"]
        lyrics_url = song_info["url"]

        # دریافت متن آهنگ از صفحه وب
        lyrics = await fetch_lyrics_from_url(lyrics_url)
        return f"🎵 **{song_title} - {song_artist}**\n\n{lyrics}"

# 📌 دریافت متن آهنگ از URL صفحه
async def fetch_lyrics_from_url(url):
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        if response.status_code != 200:
            return "⚠️ خطا در دریافت متن آهنگ!"

        # پردازش HTML برای استخراج متن آهنگ
        soup = BeautifulSoup(response.text, "html.parser")
        lyrics_div = soup.find("div", class_="lyrics")  # بعضی صفحات این کلاس رو دارند

        if lyrics_div:
            return lyrics_div.get_text(strip=True)

        # تلاش دوم برای پیدا کردن متن
        lyrics_containers = soup.find_all("div", class_="Lyrics__Container")
        if lyrics_containers:
            return "\n".join([container.get_text(strip=True) for container in lyrics_containers])

        return "❌ متن این آهنگ قابل دریافت نیست."