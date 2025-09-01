import random
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.utils import timezone
from jsonrpcserver import method, serve, Error as JSONRPCError, dispatch, Result

from handlers import get_error_response
from transfer.models import Transfer
from .serializer import TransferSerializer
from utils import send_otp, format_card_number


@method(name="transfer.create")
def transfer_create(**params):
    """Transfer yaratish - transfer.create"""

    serializer = TransferSerializer(data=params)
    if not serializer.is_valid():
        error_info = get_error_response(32713)
        return JSONRPCError(code=error_info["code"], message=error_info["message"], data=error_info)

    try:
        transfer = serializer.save()
        print("Created transfer ext_id:", transfer.ext_id)
        transfer.state = 1
        transfer.try_count = 0
        transfer.otp = f"{random.randint(100000, 999999)}"
        transfer.save()


        otp_sent = False
        try:
            send_otp(chat_id=7166090807, otp=transfer.otp)
            otp_sent = True
        except Exception as e:
            print("OTP yuborilmadi:", e)
            error_info = get_error_response(32703)
            return JSONRPCError(code=error_info["code"], message=error_info["message"], data=error_info)

        return Result({
            "ext_id": transfer.ext_id,
            "state": transfer.get_state_display(),
            "otp_sent": otp_sent,
        })

    except Exception as e:
        if "unique" in str(e).lower():
            error_info = get_error_response(32700)
            return JSONRPCError(code=error_info["code"], message=error_info["message"], data=error_info)

        error_info = get_error_response(32706)
        return JSONRPCError(code=error_info["code"], message=error_info["message"], data=error_info)


@method(name="transfer.confirm")
def transfer_confirm(ext_id: str, otp: str):
    """Transfer tasdiqlash - transfer.confirm"""
    try:
        transfer = Transfer.objects.get(ext_id=ext_id)
    except Transfer.DoesNotExist:
        error_info = get_error_response(32716)
        return JSONRPCError(code=error_info["code"], message=error_info["message"], data=error_info)

    if transfer.cancelled_at:
        error_info = get_error_response(32719)
        return JSONRPCError(code=error_info["code"], message=error_info["message"], data=error_info)

    if transfer.otp != otp:
        transfer.try_count += 1

        if transfer.try_count >= 3:
            transfer.state = 3
            transfer.cancelled_at = timezone.now()
            transfer.save()
            error_info = get_error_response(32712)
            return JSONRPCError(code=error_info["code"], message=error_info["message"], data=error_info)
        elif transfer.try_count == 2:
            transfer.save()
            error_info = get_error_response(32712)
            return JSONRPCError(code=error_info["code"], message=error_info["message"], data=error_info)
        elif transfer.try_count == 1:
            transfer.save()
            error_info = get_error_response(32718)
            return JSONRPCError(code=error_info["code"], message=error_info["message"], data=error_info)

    if transfer.state == 1 and transfer.state < 3:
        transfer.state = 2
        transfer.confirmed_at = timezone.now()
        transfer.save()

    return {
        "ext_id": transfer.ext_id,
        "state": transfer.get_state_display(),
    }


@method(name="transfer.cancel")
def transfer_cancel(ext_id: str):
    """Transfer bekor qilish - transfer.cancel"""
    try:
        transfer = Transfer.objects.get(ext_id=ext_id)
    except Transfer.DoesNotExist:
        error_info = get_error_response(32716)
        return JSONRPCError(code=error_info["code"], message=error_info["message"], data=error_info)

    if transfer.state == 3 and transfer.cancelled_at:
        error_info = get_error_response(32719)
        return JSONRPCError(code=error_info["code"], message=error_info["message"], data=error_info)

    transfer.state = 3
    transfer.cancelled_at = timezone.now()
    transfer.save()

    return {"state": transfer.get_state_display()}


@method(name="transfer.state")
def transfer_state(ext_id: str):
    try:
        transfer = Transfer.objects.get(ext_id=ext_id)
    except Transfer.DoesNotExist:
        error_info = get_error_response(32716)
        return JSONRPCError(code=error_info["code"], message=error_info["message"], data=error_info)

    return {
        "ext_id": transfer.ext_id,
        "state": transfer.get_state_display(),
    }


@method(name="transfer.history")
def transfer_history(card_number: str, start_date: str, end_date: str, status: str = None):
    """Transfer tarixi - transfer.history"""
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

        return [
            {
                "ext_id": t.ext_id,
                "sending_amount": t.sending_amount,
                "state": t.get_state_display(),
                "created_at": t.created_at.isoformat(),
            }
            for t in transfers
        ]
    except Exception as e:
        error_info = get_error_response(32706)
        return JSONRPCError(code=error_info["code"], message=error_info["message"], data=error_info)


@method_decorator(csrf_exempt, name='dispatch')
class JSONRPCView(View):
    def post(self, request):
        request_body = request.body.decode('utf-8')
        response = dispatch(request_body)
        return JsonResponse(json.loads(str(response)), safe=False)

    def get(self, request):
        error_info = get_error_response(32713)  # Method is not allowed
        return JsonResponse({
            "jsonrpc": "2.0",
            "error": error_info,
            "id": None
        })