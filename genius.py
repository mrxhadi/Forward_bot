import os
import httpx

GENIUS_API_KEY = os.getenv("GENIUS_API_KEY")  # 📌 متغیر محیطی برای API Key
BASE_URL = "https://api.genius.com"

# 📌 **دریافت اطلاعات آهنگ از Genius**
async def search_song_lyrics(query):
    headers = {"Authorization": f"Bearer {GENIUS_API_KEY}"}
    
    async with httpx.AsyncClient() as client:
        search_response = await client.get(f"{BASE_URL}/search", params={"q": query}, headers=headers)
        search_data = search_response.json()

        if not search_data.get("response", {}).get("hits"):
            return "❌ متن آهنگ یافت نشد!"

        song_info = search_data["response"]["hits"][0]["result"]
        song_title = song_info["full_title"]
        song_url = song_info["url"]

        return f"🎵 **{song_title}**\n🔗 [متن کامل آهنگ]({song_url})"
