import datetime

import requests
from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from transfer.models import Transfer
from card.models import Card

TELEGRAM_TOKEN = settings.TG_TOKEN
CHAT_ID = "@reports_unisoft"

@shared_task
def send_report():
    print("Report yuborildi ✅")
    total_cards = Card.objects.count()
    total_transfers = Transfer.objects.count()

    message = f"""
🕒 {timezone.now().strftime('%Y-%m-%d %H:%M')}
📇 Umumiy kartalar soni: {total_cards}
💸 Umumiy transferlar: {total_transfers}
"""

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": message})



@shared_task
def update_currency_rates():
    """
    CBU API dan USD (840) va RUB (643) kurslarini olib, cache ga saqlaydi.
    Har 12 soatda ishga tushadi.
    """
    url = "https://cbu.uz/uz/arkhiv-kursov-valyut/json/"
    currencies = {"840": "USD", "643": "RUB"}
    now_str = timezone.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"[update_currency_rates] ❌ API fetch error: {e}")
        return

    for code, name in currencies.items():
        match = next((c for c in data if c["Code"] == code), None)
        if not match:
            print(f"[update_currency_rates] ⚠️ {code} topilmadi API dan.")
            continue

        try:
            rate = float(match["Rate"])
            cache_key = f"currency_rate_{code}"
            cache.set(
                cache_key,
                {"rate": rate, "updated_at": now_str},
                timeout=60 * 60 * 24 * 30  # 30 kun
            )

            print(f"[update_currency_rates] ✅ {name} ({code}) = {rate} so'm | {now_str}")



            if TELEGRAM_TOKEN and CHAT_ID:
                message = (
                    f"💱 *Valyuta kursi yangilandi!*\n\n"
                    f"🕒 {timezone.now().strftime('%Y-%m-%d %H:%M')}\n"
                    f"{name} ({code}) → `{rate}` so'm\n"
                )
                try:
                    requests.post(
                        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                        data={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"},
                        timeout=10
                    )
                    print(f"[update_currency_rates] 📤 Telegramga yuborildi: {name}")
                except Exception as e:
                    print(f"[update_currency_rates] ⚠️ Telegram error: {e}")

        except Exception as e:
            print(f"[update_currency_rates] ❌ Error processing {code}: {e}")