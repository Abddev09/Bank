import logging
import time
import functools
import traceback
from django.http import JsonResponse

# logger sozlash
logger = logging.getLogger("unisoft")
handler = logging.FileHandler("unisoft.log")  # shu yerda log fayl nomi
formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(message)s"
)
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


def log_request_response(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()

        try:
            request_ip = kwargs.get("request_ip", "unknown")
            logger.info(
                f"[START] {func.__name__} | IP={request_ip} | args={args} kwargs={kwargs}"
            )

            response = func(*args, **kwargs)

            process_time = round(time.time() - start_time, 4)
            # ✅ response ni string ko‘rinishga majburlaymiz
            safe_response = repr(response)

            logger.info(
                f"[END] {func.__name__} | Time={process_time}s | Response={safe_response}"
            )

            return response

        except Exception as e:
            process_time = round(time.time() - start_time, 4)
            tb = traceback.format_exc()
            logger.error(
                f"[ERROR] {func.__name__} | Time={process_time}s | Exception={str(e)} | Traceback={tb}"
            )
            return JsonResponse({"error": str(e)}, status=500)

    return wrapper
