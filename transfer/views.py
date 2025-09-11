import hashlib
import json
import random
import traceback
import uuid
from datetime import datetime
from django.db import transaction
from decimal import Decimal

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from jsonrpcserver import method, Error, dispatch
from jsonrpcserver.result import Success
from handlers import get_error_response
from transfer.models import Transfer
from card.models import Card
from utils import send_otp, format_card_number
from utils.logging_decorator import log_request_response


@method(name="transfer.create")
@log_request_response
def transfer_create(**params):
    try:
        print("transfer_create called. params keys:", list(params.keys()))

        required_fields = ["sender_card_number", "receiver_card_number", "sender_card_expiry", "sending_amount", "currency"]
        for field in required_fields:
            if field not in params:
                error_info = get_error_response(32713)
                return Error(code=error_info["code"], message=f"Missing field: {field}", data=error_info)

        sender_card_number = params["sender_card_number"]
        receiver_card_number = params["receiver_card_number"]
        sender_card_expiry = params["sender_card_expiry"]
        sending_amount = params["sending_amount"]
        currency = str(params["currency"])

        # --- Sender lookup
        try:
            print("format_card_number sender:", sender_card_number)
            sender_card_num = format_card_number(sender_card_number)
            print("formatted sender:", sender_card_num)
            sender_card = Card.objects.get(card_number=sender_card_num)
            print("found sender_card id:", getattr(sender_card, "id", None))
        except Exception as e:
            tb = traceback.format_exc()
            print("ERROR during sender lookup:\n", tb)
            error_info = get_error_response(32701)
            return Error(code=error_info["code"], message=str(e), data=error_info)

        if sender_card.status != "active":
            error_info = get_error_response(32705)
            return Error(code=error_info["code"], message="Sender card not active", data=error_info)

        # --- Receiver lookup
        try:
            print("format_card_number receiver:", receiver_card_number)
            receiver_card_num = format_card_number(receiver_card_number)
            print("formatted receiver:", receiver_card_num)
            receiver_card = Card.objects.get(card_number=receiver_card_num)
            print("found receiver_card id:", getattr(receiver_card, "id", None))
        except Exception as e:
            tb = traceback.format_exc()
            print("ERROR during receiver lookup:\n", tb)
            error_info = get_error_response(32701)
            return Error(code=error_info["code"], message=str(e), data=error_info)

        if receiver_card.status != "active":
            error_info = get_error_response(32705)
            return Error(code=error_info["code"], message="Receiver card not active", data=error_info)

        # --- Expiry check
        try:
            month, year = map(int, sender_card_expiry.split("/"))
            exp_date = datetime(year + 2000, month, 1)
        except Exception as e:
            tb = traceback.format_exc()
            print("ERROR parsing expiry:\n", tb)
            error_info = get_error_response(32704)
            return Error(code=error_info["code"], message=str(e), data=error_info)

        if exp_date < datetime.now():
            error_info = get_error_response(32704)
            return Error(code=error_info["code"], message="Card expired", data=error_info)

        if sender_card.expire != sender_card_expiry:
            error_info = get_error_response(32704)
            return Error(code=error_info["code"], message="Expiry mismatch", data=error_info)

        # --- Currency & amount checks
        allowed = ["643", "840", "860"]
        if currency not in allowed:
            error_info = get_error_response(32707)
            return Error(code=error_info["code"], message="Currency not allowed", data=error_info)

        if sending_amount <= 0:
            error_info = get_error_response(32709)
            return Error(code=error_info["code"], message="Amount too small", data=error_info)

        if sending_amount > sender_card.balance:
            error_info = get_error_response(32702)
            return Error(code=error_info["code"], message="Balance not enough", data=error_info)

        # --- Create transfer
        otp = f"{random.randint(100000, 999999)}"

        try:
            print("Creating Transfer object...")
            transfer = Transfer.objects.create(
                ext_id=f"tr-{uuid.uuid4()}",
                sender_card_number=sender_card_num,
                receiver_card_number=receiver_card_num,
                sender_card_expiry=sender_card_expiry,
                sending_amount=sending_amount,
                currency=currency,
                sender_phone=sender_card.phone,
                receiver_phone=receiver_card.phone,
                state=1,
                otp= hashlib.sha256(otp.encode()).hexdigest(),
                try_count=0,
            )
            print("Transfer created:", transfer.ext_id)

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


@method(name="transfer.confirm")
@log_request_response
def transfer_confirm(ext_id: str, otp: str):

    try:
        transfer = Transfer.objects.get(ext_id=ext_id)
        sender_card = Card.objects.filter(card_number=transfer.sender_card_number).first()
        receiver_card = Card.objects.filter(card_number=transfer.receiver_card_number).first()
    except Transfer.DoesNotExist:
        error_info = get_error_response(32716)
        return Error(code=error_info["code"], message=error_info["message"], data=error_info)

    if transfer.cancelled_at:
        error_info = get_error_response(32719)
        return Error(code=error_info["code"], message=error_info["message"], data=error_info)

    if hashlib.sha256(transfer.otp.encode()).hexdigest() == otp:
        transfer.try_count += 1

        if transfer.try_count >= 3:
            transfer.state = 3
            transfer.cancelled_at = timezone.now()
            transfer.save()
            error_info = get_error_response(32712)
            return Error(code=error_info["code"], message=error_info["message"], data=error_info)
        elif transfer.try_count == 2:
            transfer.save()
            error_info = get_error_response(32712)
            return Error(code=error_info["code"], message=error_info["message"], data=error_info)
        elif transfer.try_count == 1:
            transfer.save()
            error_info = get_error_response(32718)
            return Error(code=error_info["code"], message=error_info["message"], data=error_info)

    if transfer.state == 1:
        currency_sum = 0.0

        if transfer.currency == "840":
            currency_sum = float(transfer.sending_amount) * 12443.29
        elif transfer.currency == "643":
            currency_sum = float(transfer.sending_amount) * 153.08
        elif transfer.currency == "860":
            currency_sum = float(transfer.sending_amount)

        commission = currency_sum * 0.01

        with transaction.atomic():
            sender_card.balance = float(sender_card.balance) - (currency_sum + commission)
            receiver_card.balance = float(receiver_card.balance) + currency_sum

            transfer.state = 2
            transfer.confirmed_at = timezone.now()

            sender_card.save(update_fields=["balance"])
            receiver_card.save(update_fields=["balance"])
            transfer.save(update_fields=["state", "confirmed_at"])

    return Success({
        "ext_id": transfer.ext_id,
        "state": transfer.get_state_display(),
    })


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

    return Success({"state": transfer.state})


@method(name="transfer.state")
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


@method(name="transfer.history")
def transfer_history(card_number: str, start_date: str, end_date: str, status: str = None):
    try:
        card_number = format_card_number(card_number)
        transfers = Transfer.objects.filter(sender_card_number=card_number)
        transfers = transfers.filter(created_at__range=[start_date, end_date])

        if status:
            status_map = {
                "created": 1,
                "confirmed": 2,
                "cancelled": 3,
            }
            state = status_map.get(status.lower())
            if state:
                transfers = transfers.filter(state=state)

        return Success([
            {
                "ext_id": t.ext_id,
                "sending_amount": t.sending_amount,
                "state": t.get_state_display(),
                "created_at": t.created_at.isoformat(),
            }
            for t in transfers
        ])
    except Exception as e:
        print(str(e))
        error_info = get_error_response(32706)
        return Error(code=error_info["code"], message=error_info["message"], data=error_info)


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


