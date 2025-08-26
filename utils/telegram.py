import asyncio

from telegram import Bot

bot = Bot(token="7589714957:AAGC0TUiYwHqiSXuNVT5Xr7CVZGb4w1ZZRg")

def send_otp(chat_id, otp):
    async def _send():
        await bot.send_message(chat_id=chat_id, text=f"Sizning OTP: {otp}")

    # Blocking tarzda async-ni ishga tushiramiz
    try:
        asyncio.run(_send())
    except RuntimeError:  # Event loop allaqachon ochiq bo‘lsa
        loop = asyncio.get_event_loop()
        loop.run_until_complete(_send())





