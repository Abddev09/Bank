import json
import traceback
import pandas as pd
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from jsonrpcserver import method, Error, Success, dispatch
from card.models import Card
from card.serializers import CardSerializer
from utils import format_card_number, format_phone_number, format_expire, format_balance, card_mask
from handlers import get_error_response


# ======================
# Card Import
# ======================
@method(name="card.import")
def card_import(file_path: str):
    cache_key = f"card_import_{hash(file_path)}"
    cached_response = cache.get(cache_key)
    if cached_response:
        return cached_response

    try:
        if file_path.endswith(".csv"):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path, engine="openpyxl")

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

        response = Success({
            "message": "Import successful",
            "created": created_count,
            "updated": updated_count,
        })

        # ✅ Import tugaganidan keyin cache tozalanadi (chunki DB o‘zgardi)
        cache.clear()

    except Exception as e:
        tb = traceback.format_exc()
        print("ERROR in card_import:\n", tb)
        error_info = get_error_response(32706)
        response = Error(code=error_info["code"], message=str(e), data=error_info)

    cache.set(cache_key, response, timeout=30)
    return response


# ======================
# Card Add
# ======================
@method(name="card.add")
def card_add(**params):
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
            # ✅ Yangi karta qo‘shilganda eski cache’lar tozalanadi
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


# ======================
# Card Info
# ======================
@method(name="card.info")
def card_info(**params):
    cache_key = f"card_info_{hash(frozenset(params.items()))}"
    cached_response = cache.get(cache_key)
    if cached_response:
        return cached_response

    try:
        card_number = format_card_number(params.get("card_number"))
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

    cache.set(cache_key, response, timeout=30)
    return response


# ======================
# JSON-RPC Dispatcher
# ======================
@csrf_exempt
def jsonrpc(request):
    if request.method == 'POST':
        try:
            request_body = request.body.decode()
            result = dispatch(request_body)
            if isinstance(result, str):
                result = json.loads(result)
            return JsonResponse(result, safe=False)
        except Exception as e:
            error_info = get_error_response(32713)
            return JsonResponse({
                "jsonrpc": "2.0",
                "error": error_info,
                "id": None
            })
    return JsonResponse({'message': 'error'})
