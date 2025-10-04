import json
import time
import traceback
import pandas as pd
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit
from jsonrpcserver import method, Error, Success, dispatch
from card.models import Card
from card.serializers import CardSerializer
from utils import format_card_number, format_phone_number, format_expire, format_balance, card_mask, luhn_check
from handlers import get_error_response
from utils.logging_decorator import log_request_response

@csrf_exempt
@ratelimit(key='ip', rate='5/m', block=True)
@require_POST
def card_import_rest(request):
    """
    POST /api/cards/import/
    Upload and import card data from a CSV or Excel file.

    Request:
        Content-Type: multipart/form-data
        file: (required) CSV or Excel file containing:
              card_number, expire, phone, status, balance

    Response (200 OK):
    {
        "message": "Import successful",
        "created": 10,
        "updated": 5
    }

    Response (400/500):
    {
        "error": {
            "code": 32706,
            "message": "File not provided",
            "data": {...}
        }
    }
    """

    try:
        file = request.FILES.get("file")
        if not file:
            error_info = get_error_response(32713)
            return JsonResponse({
                "error": {
                    "code": error_info["code"],
                    "message": "File not provided",
                    "data": error_info
                }
            }, status=400)

        # Fayl turi bo‘yicha aniqlash
        if file.name.endswith(".csv"):
            df = pd.read_csv(file)
        elif file.name.endswith((".xls", ".xlsx")):
            df = pd.read_excel(file, engine="openpyxl")
        else:
            error_info = get_error_response(32713)
            return JsonResponse({
                "error": {
                    "code": error_info["code"],
                    "message": "Unsupported file format (use .csv or .xlsx)",
                    "data": error_info
                }
            }, status=400)

        created_count, updated_count = 0, 0

        for _, row in df.iterrows():
            card_number = format_card_number(row.get("card_number"))
            expire = format_expire(row.get("expire"))
            phone = format_phone_number(row.get("phone"))
            status_value = row.get("status", "inactive")
            balance = format_balance(row.get("balance"))

            if not card_number:
                continue

            card, created = Card.objects.update_or_create(
                card_number=card_number,
                defaults={
                    "expire": expire,
                    "phone": phone,
                    "status": status_value,
                    "balance": balance,
                },
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

        # DB o‘zgargan — cache’ni tozalaymiz
        cache.clear()

        return JsonResponse({
            "message": "Import successful",
            "created": created_count,
            "updated": updated_count,
        }, status=200)

    except Exception as e:
        tb = traceback.format_exc()
        print("ERROR in card_import_rest:\n", tb)
        error_info = get_error_response(32706)
        return JsonResponse({
            "error": {
                "code": error_info["code"],
                "message": str(e),
                "data": error_info
            }
        }, status=500)



"""  Card Add  """
@ratelimit(key='ip', rate='5/m', block=True)
@method(name="card.add")
@log_request_response
def card_add(**params):
    """
        Add a new card to the database via JSON-RPC.

        Args:
            **params: Arbitrary keyword arguments containing:
                - card_number (str): 16-digit unique card number.
                - expire (str): Expiry date in MM/YY format.
                - phone (str): Phone number associated with the card (must start with 998).
                - status (str): Card status ("active" or "inactive").
                - balance (float): Initial balance.

        Returns:
            Success: On success, returns:
                {
                    "message": "Card added",
                    "card_number": str,  # masked card number
                    "expire": str,
                    "phone": str,
                    "status": str,
                    "balance": float
                }
            Error: On validation or server error, returns JSON-RPC error object.

        Notes:
            - Uses `CardSerializer` for validation before saving to DB.
            - If card data is invalid, returns validation errors.
            - Cache is cleared after adding a new card.
            - Response is cached for 30 seconds.

        Example:
            >>> card_add(
                    card_number="8600123412341234",
                    expire="12/26",
                    phone="998901234567",
                    status="active",
                    balance=100000
                )
            {
                "message": "Card added",
                "card_number": "8600 **** **** 1234",
                "expire": "12/26",
                "phone": "998901234567",
                "status": "active",
                "balance": 100000.0
            }
        """
    cache_key = f"card_add_{hash(frozenset(params.items()))}"
    cached_response = cache.get(cache_key)
    if cached_response:
        return cached_response

    try:
        serializer = CardSerializer(data=params)
        if serializer.is_valid():
            card = serializer.save()
            data = CardSerializer(card).data
            response = Success({
                "message": "Card added",
                "card_number": card_mask(data.get("card_number")),
                "expire": data.get("expire"),
                "phone": data.get("phone"),
                "status": data.get("status"),
                "balance": data.get("balance"),
            })

            cache.clear()
        else:
            error_info = get_error_response(32713)
            response = Error(
                code=error_info["code"],
                message="Validation error",
                data=serializer.errors,
            )

    except Exception as e:
        tb = traceback.format_exc()
        print("ERROR in card_add:\n", tb)
        error_info = get_error_response(32706)
        response = Error(
            code=error_info["code"],
            message=str(e),
            data=error_info,
        )

    cache.set(cache_key, response, timeout=30)
    return response



"""  Card Info  """
@ratelimit(key='ip', rate='5/m', block=True)
@method(name="card.info")
@log_request_response
def card_info(**params):
    """
        Retrieve information about a specific card.

        Args:
            **params: Arbitrary keyword arguments containing:
                - card_number (str): The unique card number.
                - expire (str): The expiry date of the card.

        Returns:
            Success: If the card exists, returns:
                {
                    "card_status": str,       # "active" or "inactive"
                    "balance": float,         # rounded to 2 decimals
                    "phone": str,             # associated phone number
                    "masked_card": str        # masked card number
                }
            Error: If the card is not found, returns an error object with details.

        Notes:
            - Looks up the card by card number + expiry date.
            - Uses caching for 30 seconds to reduce DB queries.

        Example:
            >>> card_info(card_number="8600123412341234", expire="12/26")
            {
                "card_status": "active",
                "balance": 150000.0,
                "phone": "998901234567",
                "masked_card": "8600 **** **** 1234"
            }
        """


    try:
        card_number = format_card_number(params.get("card_number"))
        card_number = card_number.replace(" ", "")
        expire = format_expire(params.get("expire"))
        card = Card.objects.filter(card_number=card_number, expire=expire).first()
        if not card:
            error_info = get_error_response(32714)
            response = Error(
                code=error_info["code"],
                message="Card not found",
                data={"card_number": card_number, "expire": expire},
            )
        else:
            response = Success({
                "card_status": card.status,
                "balance": format_balance(round(card.balance, 2)),
                "phone": card.phone,
                "masked_card": card_mask(card.card_number),
            })

    except Exception as e:
        tb = traceback.format_exc()
        print("ERROR in card_info:\n", tb)
        error_info = get_error_response(32706)
        response = Error(code=error_info["code"], message=str(e), data=error_info)

    return response



"""  Card JSONRPC Dispatcher  """
RATE_LIMIT_COUNT = 5   # misol uchun 5 ta so‘rov
RATE_LIMIT_WINDOW = 60 # soniyada — 1 daqiqa

def _get_client_ip(request):
    # Reverse proxy ishlatilsa X-Forwarded-For ni ham tekshirish mumkin
    return request.META.get('REMOTE_ADDR', 'unknown')


@csrf_exempt
def jsonrpc(request):
    if request.method == 'POST':
        payload = {}  # ✅ oldindan aniqlaymiz, har holda mavjud bo‘ladi

        try:
            body = request.body.decode()
            payload = json.loads(body)
            method_name = payload.get("method", "")
        except Exception:
            method_name = ""

        # --- Rate limit: kalit IP + method bo‘yicha
        ip = _get_client_ip(request)
        rl_key = f"rl:{ip}:{method_name}"
        now = int(time.time())

        data = cache.get(rl_key)
        if not data:
            # birinchi urinish
            cache.set(rl_key, (1, now), timeout=RATE_LIMIT_WINDOW)
        else:
            count, start = data
            if now - start < RATE_LIMIT_WINDOW:
                count += 1
                cache.set(rl_key, (count, start), timeout=RATE_LIMIT_WINDOW - (now - start))
                if count > RATE_LIMIT_COUNT:
                    # 🚫 Rate limit blok
                    return JsonResponse({
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32000,
                            "message": "Too many requests (rate limit)"
                        },
                        "id": payload.get("id")  # ✅ endi mavjud bo‘ladi
                    }, status=429)
            else:
                # yangi oynani boshlaymiz
                cache.set(rl_key, (1, now), timeout=RATE_LIMIT_WINDOW)

        # --- End rate limit, endi JSON-RPC metodni ishlatamiz
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
                "id": payload.get("id", None)
            }, status=500)

    return JsonResponse({'message': 'Only POST allowed'}, status=405)
