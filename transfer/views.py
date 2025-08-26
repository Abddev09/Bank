from django.utils import timezone
from utils import send_otp,format_card_number
from handlers import error_response
import random

from .serializer import TransferSerializer
from transfer.models import Transfer

from rest_framework import viewsets, parsers, status
from rest_framework.request import Request
from rest_framework.response import Response




class TransfersAPIViewsSet(viewsets.ViewSet):
    parser_classes = [parsers.JSONParser, parsers.FormParser]

    def create(self, request: Request):
        try:
            method = request.data.get("methods")
            params = request.data.get("params", {})

            # 1) CREATE ======================================
            if method == "transfer.create":
                serializer = TransferSerializer(data=params)
                if serializer.is_valid():
                    transfer = serializer.save()
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

                    return Response({
                        "id": transfer.id,
                        "result": {
                            "ext_id": transfer.ext_id,
                            "state": transfer.get_state_display(),
                            "otp_sent": otp_sent
                        }
                    }, status=status.HTTP_201_CREATED)
                else:
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


            # 2) CONFIRM =====================================
            elif method == "transfer.confirm":
                ext_id = params.get("ext_id")
                otp = params.get("otp")

                if None in [ext_id, otp]:
                    return error_response(32715, status.HTTP_400_BAD_REQUEST)

                try:
                    transfer = Transfer.objects.get(ext_id=ext_id)
                except Transfer.DoesNotExist:
                    return error_response(32716, status.HTTP_404_NOT_FOUND)

                if transfer.cancelled_at is None:
                    if transfer.otp != otp:
                        if transfer.try_count == 2:
                            transfer.try_count += 1
                            transfer.save()
                            return error_response(32718, status.HTTP_403_FORBIDDEN)

                        if transfer.try_count == 3:
                            transfer.cancelled_at = timezone.now()
                            transfer.state = 3
                            transfer.save()
                            return error_response(32711, status.HTTP_403_FORBIDDEN)

                        transfer.try_count += 1
                        transfer.save()
                        return error_response(32712, status.HTTP_404_NOT_FOUND)

                    if transfer.state == 1 and transfer.state < 3:
                        transfer.state = 2
                        transfer.confirmed_at = timezone.now()
                        transfer.save()
                        return Response({
                            "id": transfer.id,
                            "result": {
                                "ext_id": transfer.ext_id,
                                "state": transfer.get_state_display()
                            }
                        }, status=status.HTTP_200_OK)

                return error_response(32710, status.HTTP_404_NOT_FOUND)


            # 3) CANCEL ======================================
            elif method == "transfer.cancel":
                ext_id = params.get("ext_id")
                if not ext_id:
                    return error_response(32715, status.HTTP_400_BAD_REQUEST)

                try:
                    transfer = Transfer.objects.get(ext_id=ext_id)
                except Transfer.DoesNotExist:
                    return error_response(32716, status.HTTP_404_NOT_FOUND)

                if transfer.state == 3 and transfer.cancelled_at:
                    return error_response(32719, status.HTTP_404_NOT_FOUND)

                transfer.state = 3
                transfer.cancelled_at = timezone.now()
                transfer.save()

                return Response({
                    "id": transfer.id,
                    "result": {
                        "state": transfer.get_state_display()
                    }
                }, status=status.HTTP_200_OK)


            # 4) GET STATE ===================================
            elif method == "transfer.state":
                ext_id = params.get("ext_id")
                if not ext_id:
                    return error_response(32715, status.HTTP_400_BAD_REQUEST)

                try:
                    transfer = Transfer.objects.get(ext_id=ext_id)
                except Transfer.DoesNotExist:
                    return error_response(32716, status.HTTP_404_NOT_FOUND)

                if transfer.state == 3 and transfer.cancelled_at:
                    return error_response(32719, status.HTTP_404_NOT_FOUND)


                return Response({
                    "id": transfer.id,
                    "result": {
                        "ext_id":transfer.ext_id,
                        "state": transfer.get_state_display()
                    }
                }, status=status.HTTP_200_OK)


            # 5) HISTORY ====================================
            elif method == "transfer.history":
                card_number = format_card_number(params.get("card_number"))
                start_date = params.get("start_date")
                end_date = params.get("end_date")
                history_status = params.get("status")

                if None in [card_number,start_date,end_date,history_status]:
                    return error_response(32715,status.HTTP_404_NOT_FOUND)

                try:
                    transfers = Transfer.objects.filter(sender_card_number=card_number)
                    if not transfers:
                        return error_response(32716,status.HTTP_404_NOT_FOUND)
                    transfers = transfers.filter(created_at__range=[start_date,end_date])

                    if history_status:
                        status_map ={
                            "created":1,
                            "confirmed":2,
                            "cancelled":3
                        }
                        state = status_map.get(history_status.lower())

                        if state:
                            transfers = transfers.filter(state=state)
                    result = [
                        {
                            "ext_id":t.ext_id,
                            "sending_amount":t.sending_amount,
                            "state":t.get_state_display(),
                            "created_at":t.created_at

                        }
                        for t in transfers
                    ]

                    return Response({"result": result}, status=status.HTTP_200_OK)


                except Transfer.DoesNotExist:
                    return error_response(32716, status.HTTP_404_NOT_FOUND)


            # NOT FOUND METHOD ==============================
            else:
                return error_response(32714, status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


