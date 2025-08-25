from rest_framework import viewsets, parsers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .serializer import TransferSerializer
from transfer.models import Transfer
import random
from telegram import Bot

from .utils import send_otp

bot = Bot(token='7589714957:AAGC0TUiYwHqiSXuNVT5Xr7CVZGb4w1ZZRg')

class TransfersAPIViewsSet(viewsets.ViewSet):
    parser_classes = [parsers.JSONParser, parsers.FormParser]

    @action(detail=False, methods=['post'], url_path='add_transfer')
    def add_transfer(self, request):
        serializer = TransferSerializer(data=request.data)
        if serializer.is_valid():
            transfer = serializer.save()
            transfer.state = 'created'
            transfer.try_count = 0
            transfer.otp = f"{random.randint(100000, 999999)}"
            transfer.save()

            # Telegram orqali yuborish
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
                    "state": transfer.state,
                    "otp_sent": otp_sent
                }
            }, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
