import pandas as pd
from rest_framework import generics, parsers, status
from rest_framework.response import Response
from card.models import Card
from card.utils.utils import format_card_number, format_phone_number, format_expire, format_balance


class ImportCardData(generics.GenericAPIView):
    parser_classes = [parsers.MultiPartParser]

    def post(self, request, *args, **kwargs):
        file_obj = request.FILES.get("file")
        if not file_obj:
            return Response({"error": "File not provided"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if file_obj.name.endswith(".csv"):
                df = pd.read_csv(file_obj)
            else:
                df = pd.read_excel(file_obj)
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
                continue  # agar kartaning raqami yo‘q bo‘lsa, tashlab ketamiz

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
