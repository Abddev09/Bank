from rest_framework import serializers

from card.models import Card


# Validatsiya uchun serializer yaratamiz
class CardSerializer(serializers.ModelSerializer):
    """
        Serializer for validating and serializing Card model data.

        Fields:
            - card_number (str): Must be a 16-digit numeric string.
            - expire (str): Expiry date in MM/YY format.
            - phone (str): Must start with '998' (Uzbekistan format).
            - status (str): Card status, e.g., "active" or "inactive".
            - balance (float): Must be zero or positive.

        Validation:
            - validate_card_number: Ensures card number is exactly 16 digits.
            - validate_phone: Ensures phone starts with 998 if provided.
            - validate_balance: Ensures balance is not negative.

        Example:
            >>> data = {
                    "card_number": "8600123412341234",
                    "expire": "12/26",
                    "phone": "998901234567",
                    "status": "active",
                    "balance": 100000
                }
            >>> serializer = CardSerializer(data=data)
            >>> serializer.is_valid()
            True
            >>> serializer.save()
            <Card object>
        """
    class Meta:
        model = Card
        fields = ['card_number', 'expire', 'phone', 'status', 'balance']

    # qo‘shimcha validatsiya
    def validate_card_number(self, value):
        if not value.isdigit() or len(value) != 16:
            raise serializers.ValidationError("Card number must be 16 digits")
        return value

    def validate_phone(self, value):
        if value and not value.startswith("998"):
            raise serializers.ValidationError("Phone must start with 998")
        return value

    def validate_balance(self, value):
        if value < 0:
            raise serializers.ValidationError("Balance cannot be negative")
        return value
