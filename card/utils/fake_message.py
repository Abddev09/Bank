# utils/telegram_utils.py
import asyncio
from telethon import TelegramClient

API_ID = 22770049
API_HASH = "cc85a0d423331635c0f6f9a8079605a2"
SESSION_NAME = "second_account"

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)


async def _send_messages_bulk(messages: list[tuple[str, str]]):
    """messages = [(phone, message), (phone, message), ...]"""
    async with client:
        for phone, msg in messages:
            try:
                await client.send_message(phone, msg)
                print(f"✅ Xabar yuborildi: {phone}")
            except Exception as e:
                print(f"❌ Xatolik: {phone} → {str(e)}")


def send_bulk(messages: list[tuple[str, str]]):
    """Sync wrapper — Django admin ichida chaqirish uchun"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_send_messages_bulk(messages))
    loop.close()
