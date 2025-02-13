import asyncio
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.enums import ChatType
from aiogram.filters import Command

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")

if not BOT_TOKEN or not GROUP_ID:
    raise ValueError("❌ متغیرهای محیطی BOT_TOKEN و GROUP_ID تنظیم نشده‌اند!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# حالت فعال شدن ربات
bot_enabled = False

# دریافت پیام‌های قدیمی و فوروارد کردن آهنگ‌ها
async def process_existing_audios(chat_id):
    messages = await bot.get_chat_history(chat_id, limit=100)  # دریافت آخرین 100 پیام
    for message in messages:
        if message.audio:
            sent_message = await message.copy_to(chat_id, message_thread_id=message.message_thread_id)
            await message.delete()

@dp.message(Command("enable"))
async def enable_bot(message: Message):
    global bot_enabled
    if not bot_enabled:
        bot_enabled = True
        await message.reply("✅ ربات فعال شد و شروع به پردازش آهنگ‌های قدیمی کرد!")
        await process_existing_audios(GROUP_ID)
    else:
        await message.reply("⚡ ربات قبلاً فعال شده است!")

@dp.message(lambda msg: msg.audio and msg.chat.type in ["group", "supergroup"])
async def forward_music(message: Message):
    if bot_enabled:
        chat_id = message.chat.id
        topic_id = message.message_thread_id

        sent_message = await message.copy_to(chat_id, message_thread_id=topic_id)
        await message.delete()

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
