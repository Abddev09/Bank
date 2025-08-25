from rest_framework import viewsets, parsers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from card.models import Card
from card.serializers import CardSerializer
from card.utils.utils import format_card_number, format_phone_number, format_expire, format_balance


class CardViewSet(viewsets.ViewSet):
    parser_classes = [parsers.MultiPartParser,parsers.JSONParser, parsers.FormParser]

    @action(detail=False, methods=['post'], url_path='import')
    def import_cards(self, request):
        file_obj = request.FILES.get("file")
        if not file_obj:
            return Response({"error": "File not provided"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            import pandas as pd
            if file_obj.name.endswith(".csv"):
                df = pd.read_csv(file_obj)
            else:
                df = pd.read_excel(file_obj, engine='openpyxl')  # <--- shu yerga engine qo‘shish

        except Exception as e:
            return Response({"error": f"Failed to read file: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

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
                }
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        return Response({
            "message": "Import successful",
            "created": created_count,
            "updated": updated_count
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='add')
    def add_card(self, request):
        serializer = CardSerializer(data=request.data)
        if serializer.is_valid():
            card = serializer.save()
            return Response({"message": "Card added", "card": CardSerializer(card).data})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)