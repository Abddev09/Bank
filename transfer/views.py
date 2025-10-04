import hashlib
import json
import random
import time
import traceback
import uuid
from datetime import datetime
from django.db import transaction
from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from jsonrpcserver import method, Error, dispatch
from jsonrpcserver.result import Success
from django_ratelimit.decorators import ratelimit

from handlers import get_error_response
from transfer.models import Transfer
from .serializer import TransferCreateSerializer, TransferConfirmSerializer
from card.models import Card
from utils import send_otp, format_card_number, luhn_check
from utils.logging_decorator import log_request_response

# loggin elements
import re
from datetime import datetime, timedelta, time as dt_time
from django.utils import timezone
import logging

logger = logging.getLogger("unisoft")



"""  Transfer create  """

@ratelimit(key='ip', rate='5/m', block=True)
@method(name="transfer.create")
@log_request_response
def transfer_create(**params):
    """
    Create a new transfer between two cards with cache-based OTP management.
    """
    try:
        print("transfer_create called. params keys:", list(params.keys()))

        # Serializer bilan validatsiya
        serializer = TransferCreateSerializer(data=params)
        if not serializer.is_valid():
            error_info = get_error_response(32713)
            return Error(
                code=error_info["code"],
                message="Validation error",
                data=serializer.errors
            )

        validated_data = serializer.validated_data
        sender_card_number = validated_data["sender_card_number"]
        receiver_card_number = validated_data["receiver_card_number"]
        sender_card_expiry = validated_data["sender_card_expiry"]
        sending_amount = validated_data["sending_amount"]
        currency = str(validated_data["currency"])

        # Luhn algoritmi bilan karta raqamlarini tekshirish
        sender_clean = sender_card_number.replace(" ", "")
        receiver_clean = receiver_card_number.replace(" ", "")

        if not luhn_check(sender_clean):
            error_info = get_error_response(32701)
            return Error(code=error_info["code"], message="Invalid sender card number", data=error_info)

        if not luhn_check(receiver_clean):
            error_info = get_error_response(32701)
            return Error(code=error_info["code"], message="Invalid receiver card number", data=error_info)

        # --- Sender lookup
        try:
            sender_card = Card.objects.get(card_number=sender_clean)
        except Card.DoesNotExist:
            error_info = get_error_response(32701)
            return Error(code=error_info["code"], message="Sender card not found", data=error_info)

        if sender_card.status != "active":
            error_info = get_error_response(32705)
            return Error(code=error_info["code"], message="Sender card not active", data=error_info)

        # --- Receiver lookup
        try:
            receiver_card = Card.objects.get(card_number=receiver_clean)
        except Card.DoesNotExist:
            error_info = get_error_response(32701)
            return Error(code=error_info["code"], message="Receiver card not found", data=error_info)

        if receiver_card.status != "active":
            error_info = get_error_response(32705)
            return Error(code=error_info["code"], message="Receiver card not active", data=error_info)

        # --- Expiry check
        try:
            month, year = map(int, sender_card_expiry.split("/"))
            exp_date = datetime(year + 2000, month, 1)
        except Exception as e:
            error_info = get_error_response(32704)
            return Error(code=error_info["code"], message="Invalid expiry format", data=error_info)

        if exp_date < datetime.now():
            error_info = get_error_response(32704)
            return Error(code=error_info["code"], message="Card expired", data=error_info)

        if sender_card.expire != sender_card_expiry:
            error_info = get_error_response(32704)
            return Error(code=error_info["code"], message="Expiry mismatch", data=error_info)

        # --- Currency & amount checks
        currency_sum = 0.0
        rate_updated_at = None

        if currency in ["840", "643"]:
            cache_key = f"currency_rate_{currency}"
            cached = cache.get(cache_key)

            if cached:
                rate = cached["rate"]
                rate_updated_at = datetime.strptime(cached["updated_at"], "%Y-%m-%d %H:%M:%S")
            else:
                # fallback: default rate (agar cache bo'lmasa)
                rate = 12443.29 if currency == "840" else 153.08

            currency_sum = float(sending_amount) * rate
        elif currency == "860":
            rate = 1.0
            currency_sum = float(sending_amount)

        commission = currency_sum * 0.01
        total_amount = currency_sum + commission

        if total_amount > sender_card.balance:
            error_info = get_error_response(32702)
            return Error(code=error_info["code"], message="Balance not enough", data=error_info)

        # --- Create transfer
        ext_id = f"tr-{uuid.uuid4()}"
        otp = f"{random.randint(100000, 999999)}"
        otp_hash = hashlib.sha256(otp.encode()).hexdigest()

        try:
            transfer = Transfer.objects.create(
                ext_id=ext_id,
                sender_id=sender_card.pk,
                receiver_id=receiver_card.pk,
                sending_amount=float(sending_amount),
                currency=currency,
                exchange_rate=rate,
                rate_updated_at=rate_updated_at,
                receiving_amount=sending_amount,
                state=1,
            )

            # Cache ga OTP va try_count saqlash (5 daqiqa)
            cache_key_otp = f"transfer_otp_{ext_id}"
            cache_key_tries = f"transfer_tries_{ext_id}"

            cache.set(cache_key_otp, otp_hash, timeout=300)  # 5 daqiqa
            cache.set(cache_key_tries, 0, timeout=300)  # 5 daqiqa

        except Exception as e:
            tb = traceback.format_exc()
            print("ERROR creating Transfer:\n", tb)
            error_info = get_error_response(32706)
            return Error(code=error_info["code"], message=str(e), data=error_info)

        # --- Send OTP
        try:
            send_otp(chat_id=7166090807, otp=otp)
            otp_sent = True
        except Exception as e:
            tb = traceback.format_exc()
            print("ERROR sending OTP:\n", tb)
            otp_sent = False
            error_info = get_error_response(32703)
            return Error(code=error_info["code"], message=str(e), data=error_info)

        return Success({
            "ext_id": transfer.ext_id,
            "state": transfer.get_state_display(),
            "otp_sent": otp_sent,
        })

    except Exception as e:
        tb = traceback.format_exc()
        print("TOP-LEVEL Exception in transfer_create:\n", tb)
        error_info = get_error_response(32706)
        return Error(code=error_info["code"], message=str(e), data=error_info)


"""  Transfer confirm  """

@ratelimit(key='ip', rate='5/m', block=True)
@method(name="transfer.confirm")
@log_request_response
def transfer_confirm(ext_id: str, otp: str):
    try:
        # Serializer bilan validatsiya
        serializer = TransferConfirmSerializer(data={"ext_id": ext_id, "otp": otp})
        if not serializer.is_valid():
            error_info = get_error_response(32713)
            return Error(
                code=error_info["code"],
                message="Validation error",
                data=serializer.errors
            )

        try:
            transfer = Transfer.objects.filter(ext_id=ext_id).first()
        except Transfer.DoesNotExist:
            error_info = get_error_response(32716)
            return Error(code=error_info["code"], message=error_info["message"], data=error_info)

        # Bekor qilingan transferni tekshirish
        if transfer.cancelled_at:
            error_info = get_error_response(32719)
            return Error(code=error_info["code"], message=error_info["message"], data=error_info)

        # Cache dan OTP va try_count olish
        cache_key_otp = f"transfer_otp_{ext_id}"
        cache_key_tries = f"transfer_tries_{ext_id}"

        cached_otp_hash = cache.get(cache_key_otp)
        try_count = cache.get(cache_key_tries, 0)

        if not cached_otp_hash:
            error_info = get_error_response(32718)  # OTP expired
            return Error(code=error_info["code"], message="OTP expired", data=error_info)

        # OTP ni tekshirish
        otp_hash = hashlib.sha256(otp.encode()).hexdigest()
        if otp_hash != cached_otp_hash:
            try_count += 1
            cache.set(cache_key_tries, try_count, timeout=300)

            if try_count >= 3:
                transfer.state = 3
                transfer.cancelled_at = timezone.now()
                transfer.save(update_fields=["state", "cancelled_at"])

                # Cache dan tozalash
                cache.delete(cache_key_otp)
                cache.delete(cache_key_tries)

                error_info = get_error_response(32712)  # max attempts
                return Error(code=error_info["code"], message=error_info["message"], data=error_info)

            error_info = get_error_response(32718)  # invalid otp
            return Error(code=error_info["code"], message=error_info["message"], data=error_info)

        # To'g'ri OTP kiritilgan bo'lsa
        if transfer.state != 1:
            error_info = get_error_response(32719)  # already confirmed or cancelled
            return Error(code=error_info["code"], message=error_info["message"], data=error_info)

        # Pul o'tkazish
        currency_sum = 0.0
        rate_updated_at = None
        rate = 1.0  # default

        if transfer.currency in ["840", "643"]:
            cache_key = f"currency_rate_{transfer.currency}"
            cached = cache.get(cache_key)

            if cached:
                rate = float(cached.get("rate", 1.0))
                rate_updated_at_str = cached.get("updated_at")
                if rate_updated_at_str:
                    rate_updated_at = datetime.strptime(rate_updated_at_str, "%Y-%m-%d %H:%M:%S")
            else:
                # fallback qiymat (agar cache bo‘lmasa)
                if transfer.currency == "840":
                    rate = 12443.29
                elif transfer.currency == "643":
                    rate = 153.08

            currency_sum = float(transfer.sending_amount) * rate
        elif transfer.currency == "860":
            rate = 1.0
            currency_sum = float(transfer.sending_amount)

        commission = currency_sum * 0.01
        total_amount = currency_sum + commission

        with transaction.atomic():
            sender_card = Card.objects.get(id=transfer.sender_id)
            receiver_card = Card.objects.get(id=transfer.receiver_id)

            if sender_card.balance < total_amount:
                error_info = get_error_response(32702)
                return Error(code=error_info["code"], message=error_info["message"], data=error_info)

            sender_card.balance = float(sender_card.balance) - total_amount
            receiver_card.balance = float(receiver_card.balance) + currency_sum

            transfer.state = 2
            transfer.confirmed_at = timezone.now()

            sender_card.save(update_fields=["balance"])
            receiver_card.save(update_fields=["balance"])
            transfer.save(update_fields=["state", "confirmed_at"])

        # Cache dan tozalash
        cache.delete(cache_key_otp)
        cache.delete(cache_key_tries)

        return Success({
            "ext_id": transfer.ext_id,
            "state": transfer.get_state_display(),
        })

    except Exception as e:
        tb = traceback.format_exc()
        print("ERROR in transfer_confirm:\n", tb)
        error_info = get_error_response(32706)
        return Error(code=error_info["code"], message=str(e), data=error_info)


"""  Transfer cancel  """

@ratelimit(key='ip', rate='5/m', block=True)
@method(name="transfer.cancel")
@log_request_response
def transfer_cancel(ext_id: str):
    try:
        transfer = Transfer.objects.get(ext_id=ext_id)
    except Transfer.DoesNotExist:
        error_info = get_error_response(32716)
        return Error(code=error_info["code"], message=error_info["message"], data=error_info)

    if transfer.state == 3 and transfer.cancelled_at:
        error_info = get_error_response(32719)
        return Error(code=error_info["code"], message=error_info["message"], data=error_info)

    transfer.state = 3
    transfer.cancelled_at = timezone.now()
    transfer.save()

    # Cache dan tozalash
    cache_key_otp = f"transfer_otp_{ext_id}"
    cache_key_tries = f"transfer_tries_{ext_id}"
    cache.delete(cache_key_otp)
    cache.delete(cache_key_tries)

    return Success({"state": transfer.get_state_display()})


"""  Transfer state  """

@ratelimit(key='ip', rate='5/m', block=True)
@method(name="transfer.state")
@log_request_response
def transfer_state(ext_id: str):
    try:
        transfer = Transfer.objects.get(ext_id=ext_id)
    except Transfer.DoesNotExist:
        error_info = get_error_response(32716)
        return Error(code=error_info["code"], message=error_info["message"], data=error_info)

    return Success({
        "ext_id": transfer.ext_id,
        "state": transfer.state
    })


"""  Transfer history  """

@ratelimit(key='ip', rate='5/m', block=True)
@method(name="transfer.history")
@log_request_response
def transfer_history(card_number: str, start_date: str, end_date: str, status: str = None):
    try:
        clean_number = re.sub(r"\D", "", card_number or "")
        if not clean_number:
            error_info = get_error_response(32713)
            return Error(code=error_info["code"], message="Card number required", data=error_info)

        if not luhn_check(clean_number):
            error_info = get_error_response(32701)
            return Error(code=error_info["code"], message="Invalid card number", data=error_info)

        # 1️⃣ Sana tekshirish
        try:
            start_dt_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_dt_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        except Exception:
            error_info = get_error_response(32713)
            return Error(code=error_info["code"], message="Invalid date format (expected YYYY-MM-DD)", data=error_info)

        if start_dt_date > end_dt_date:
            error_info = get_error_response(32713)
            return Error(code=error_info["code"], message="start_date must be <= end_date", data=error_info)

        start_dt = datetime.combine(start_dt_date, dt_time.min)
        end_next_day = datetime.combine(end_dt_date, dt_time.min) + timedelta(days=1)

        # 2️⃣ Karta bo‘yicha Card pk sini topamiz
        try:
            sender_card = Card.objects.get(card_number=clean_number)
        except Card.DoesNotExist:
            error_info = get_error_response(32714)
            return Error(code=error_info["code"], message="Card not found", data=error_info)

        # 3️⃣ Endi Transferlar sender_id orqali filtrlanadi
        transfers_qs = Transfer.objects.filter(
            sender_id=str(sender_card.pk),
            created_at__gte=start_dt,
            created_at__lt=end_next_day,
        ).order_by("-created_at")

        # 4️⃣ status filtr
        if status:
            status_map = {"created": 1, "confirmed": 2, "cancelled": 3}
            state = status_map.get(status.lower())
            if state is None:
                error_info = get_error_response(32713)
                return Error(code=error_info["code"], message="Invalid status parameter", data=error_info)
            transfers_qs = transfers_qs.filter(state=state)

        # 5️⃣ Natija tayyorlash
        result = []
        for t in transfers_qs:
            result.append({
                "ext_id": t.ext_id,
                "sending_amount": float(t.sending_amount) if t.sending_amount is not None else None,
                "state": t.get_state_display(),
                "created_at": t.created_at.isoformat(),
            })

        return Success(result)

    except Exception as e:
        logger.exception("Error in transfer_history: %s", str(e))
        error_info = get_error_response(32706)
        return Error(code=error_info["code"], message=error_info["message"], data=error_info)






"""  Transfer JSONRPC Dispatcher  """
RATE_LIMIT_COUNT = 5   # misol uchun 5 so'rov
RATE_LIMIT_WINDOW = 60 # soniya — 1 daqiqa

def _get_client_ip(request):
    # agar reverse proxy ishlatsa X-Forwarded-For ni ham tekshiring
    return request.META.get('REMOTE_ADDR')

@csrf_exempt
def jsonrpc(request):
    if request.method == 'POST':
        try:
            body = request.body.decode()
            payload = json.loads(body)
            method_name = payload.get("method", "")
        except Exception:
            method_name = ""

        # --- Rate limit: kalitni IP + method bo'yicha qilamiz
        ip = _get_client_ip(request)
        rl_key = f"rl:{ip}:{method_name}"
        now = int(time.time())

        data = cache.get(rl_key)
        if not data:
            # saqlaymiz: (count, window_start)
            cache.set(rl_key, (1, now), timeout=RATE_LIMIT_WINDOW)
        else:
            count, start = data
            if now - start < RATE_LIMIT_WINDOW:
                count += 1
                cache.set(rl_key, (count, start), timeout=RATE_LIMIT_WINDOW - (now - start))
                if count > RATE_LIMIT_COUNT:
                    # block qilish
                    return JsonResponse({
                        "jsonrpc": "2.0",
                        "error": {"code": -32000, "message": "Too many requests (rate limit)"},
                        "id": payload.get("id")
                    }, status=429)
            else:
                # oynani yangilash
                cache.set(rl_key, (1, now), timeout=RATE_LIMIT_WINDOW)

        # --- End rate limit, endi asl dispatch qilamiz
        try:
            result = dispatch(body)
            if isinstance(result, str):
                result = json.loads(result)
            return JsonResponse(result, safe=False)
        except Exception:
            error_info = get_error_response(32713)
            return JsonResponse({
                "jsonrpc": "2.0",
                "error": error_info,
                "id": None
            })
    return JsonResponse({'message': 'error'})
