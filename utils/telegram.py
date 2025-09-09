from django.conf import settings
import requests
def send_otp(chat_id, otp):
    message = f"Sizning tasdiqlash kodingiz: {otp}"
    url = f"https://api.telegram.org/bot{settings.TG_TOKEN}/sendMessage?chat_id={chat_id}&text={message}&parse_mode=HTML"
    requests.get(url)
    print("Otp jo'natildi")
    return True
