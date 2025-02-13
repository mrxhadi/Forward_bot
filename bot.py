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

# دریافت پیام‌های قبلی و فوروارد کردن آهنگ‌ها
async def process_existing_audios(chat_id):
    await bot.send_chat_action(chat_id, "typing")  # اطمینان از دسترسی به گروه
    updates = await bot.get_updates()  # دریافت آخرین پیام‌های گروه

    for update in updates:
        if update.message and update.message.chat.id == int(chat_id) and update.message.audio:
            sent_message = await update.message.copy_to(chat_id, message_thread_id=update.message.message_thread_id)
            await update.message.delete()

@dp.message(lambda msg: msg.audio and msg.chat.type in ["group", "supergroup"])
async def forward_music(message: Message):
    chat_id = message.chat.id
    topic_id = message.message_thread_id

    sent_message = await message.copy_to(chat_id, message_thread_id=topic_id)
    await message.delete()

async def main():
    await bot.delete_webhook(drop_pending_updates=True)

    # دریافت و پردازش پیام‌های قدیمی
    await process_existing_audios(GROUP_ID)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
