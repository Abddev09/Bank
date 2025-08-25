from rest_framework import serializers

from card.models import Card


# Validatsiya uchun serializer yaratamiz
class CardSerializer(serializers.ModelSerializer):
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
