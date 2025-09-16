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


"""  Card Import from exel  """
@method(name="card.import")
def card_import(file_path: str):
    """
       Import cards from a CSV or Excel file and insert/update them in the database.

       Args:
           file_path (str): The path to the CSV or Excel file containing card data.

       Returns:
           Success: On success, returns a JSON-RPC success response containing:
               {
                   "message": "Import successful",
                   "created": int,  # number of new cards created
                   "updated": int   # number of existing cards updated
               }
           Error: On failure, returns a JSON-RPC error response with error code and details.

       Notes:
           - The function supports `.csv` and `.xlsx` (Excel) formats.
           - Each row must contain: `card_number`, `expire`, `phone`, `status`, `balance`.
           - Cache is cleared after import because DB state has changed.
           - The result is cached for 30 seconds to prevent duplicate imports.

       Example:
           >>> card_import("cards.xlsx")
           {
               "message": "Import successful",
               "created": 100,
               "updated": 25
           }
       """
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



"""  Card Add  """
@method(name="card.add")
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



"""  Card Info  """
@method(name="card.info")
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



"""  Card JSONRPC Dispatcher  """
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
