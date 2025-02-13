import asyncio
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.enums import ChatType

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")

if not BOT_TOKEN or not GROUP_ID:
    raise ValueError("❌ متغیرهای محیطی BOT_TOKEN و GROUP_ID تنظیم نشده‌اند!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# تابع برای پردازش آهنگ‌های یک تاپیک خاص
async def process_existing_audios(chat_id, topic_id):
    async for message in bot.get_chat_history(chat_id, message_thread_id=topic_id):
        if message.audio:
            sent_message = await message.copy_to(chat_id, message_thread_id=topic_id)
            await message.delete()

# دریافت و پردازش تمام آهنگ‌های قدیمی در تمام تاپیک‌ها
async def process_all_topics(chat_id):
    chat = await bot.get_chat(chat_id)
    
    if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP] and chat.is_forum:
        topics = await bot.get_forum_topics(chat_id)
        
        for topic in topics:
            await process_existing_audios(chat_id, topic.message_thread_id)

@dp.message(lambda msg: msg.audio and msg.chat.type in ["group", "supergroup"])
async def forward_music(message: Message):
    chat_id = message.chat.id
    topic_id = message.message_thread_id

    sent_message = await message.copy_to(chat_id, message_thread_id=topic_id)
    await message.delete()

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    
    # پردازش آهنگ‌های قبلی هنگام اجرای اولیه
    await process_all_topics(GROUP_ID)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
