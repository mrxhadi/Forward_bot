import os
import httpx
from bs4 import BeautifulSoup

# گرفتن توکن از متغیر محیطی
GENIUS_ACCESS_TOKEN = os.getenv("GENIUS_ACCESS_TOKEN")
BASE_URL = "https://api.genius.com"

# 📌 جستجوی آهنگ در Genius
async def search_song_lyrics(query):
    headers = {"Authorization": f"Bearer {GENIUS_ACCESS_TOKEN}"}
    search_url = f"https://api.genius.com/search?q={query}"

    async with httpx.AsyncClient() as client:
        response = await client.get(search_url, headers=headers)
        data = response.json()

        if "response" in data and "hits" in data["response"] and len(data["response"]["hits"]) > 0:
            song_info = data["response"]["hits"][0]["result"]
            song_title = song_info.get("title", "نامشخص")
            song_artist = song_info.get("primary_artist", {}).get("name", "نامشخص")
            song_url = song_info.get("url", "")

            return f"🎵 **{song_title}** - {song_artist}\n🔗 [متن آهنگ در جینیس]({song_url})"
        else:
            return "❌ متن آهنگ پیدا نشد!"

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
