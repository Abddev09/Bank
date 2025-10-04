import logging
import time
import functools
import traceback
from django.http import JsonResponse
from django.conf import settings
from utils.formats import card_mask

# 📘 Logger sozlash
logger = logging.getLogger("unisoft")
if not logger.handlers:  # oldingi handlerlar takrorlanmasligi uchun
    handler = logging.FileHandler("unisoft.log", encoding="utf-8")
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def mask_otp(otp: str) -> str:
    """OTP ni mask qilish (faqat oxirgi raqam ko‘rinadi)"""
    if not otp:
        return "****"
    return "*" * (len(otp) - 1) + otp[-1]


def log_request_response(func):
    """Har bir request va javobni logga yozadi, xatolikda traceback qaytaradi."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()

        try:
            # 🔹 IP aniqlash (bor bo‘lmasa unknown)
            request_ip = kwargs.get("request_ip", "unknown")

            # 🔹 Maxfiy ma’lumotlarni mask qilish
            masked_kwargs = kwargs.copy()
            if "sender_card_number" in masked_kwargs:
                masked_kwargs["sender_card_number"] = card_mask(masked_kwargs["sender_card_number"])
            if "receiver_card_number" in masked_kwargs:
                masked_kwargs["receiver_card_number"] = card_mask(masked_kwargs["receiver_card_number"])
            if "otp" in masked_kwargs:
                masked_kwargs["otp"] = mask_otp(masked_kwargs["otp"])

            logger.info(f"[START] {func.__name__} | IP={request_ip} | args={args} kwargs={masked_kwargs}")

            # 🔹 Asosiy funksiyani chaqirish
            response = func(*args, **kwargs)

            process_time = round(time.time() - start_time, 4)
            logger.info(f"[END] {func.__name__} | Time={process_time}s | Response={repr(response)}")

            return response

        except Exception as e:
            process_time = round(time.time() - start_time, 4)
            tb = traceback.format_exc()
            logger.error(
                f"[ERROR] {func.__name__} | Time={process_time}s | Exception={str(e)} | Traceback:\n{tb}"
            )

            # 🔹 DEBUG=True bo‘lsa — batafsil traceback Postman’ga qaytadi
            if getattr(settings, "DEBUG", False):
                return JsonResponse(
                    {
                        "error": str(e),
                        "traceback": tb,
                        "func": func.__name__,
                        "args": str(args),
                        "kwargs": str(kwargs),
                    },
                    status=500
                )

            # 🔹 DEBUG=False (production) bo‘lsa — faqat umumiy xabar
            return JsonResponse(
                {"error": "Internal Server Error. Please contact support."},
                status=500
            )

    return wrapper
