import requests
from celery import shared_task
from django.conf import settings
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
