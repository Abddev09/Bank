import luhn
from rest_framework import serializers
from decimal import Decimal
import re


class TransferCreateSerializer(serializers.Serializer):
    sender_card_number = serializers.CharField(max_length=32, required=True)
    receiver_card_number = serializers.CharField(max_length=32, required=True)
    sender_card_expiry = serializers.CharField(max_length=20, required=True)
    sending_amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    currency = serializers.ChoiceField(choices=[('643', 'RUB'), ('840', 'USD'), ('860', 'UZS')])

    def validate_sender_card_number(self, value):
        """Jo'natuvchi karta raqamini validatsiya qilish (LUHN + 16 raqam)"""
        cleaned = re.sub(r'[^0-9]', '', str(value))  # faqat raqamlarni olish
        if len(cleaned) != 16:
            raise serializers.ValidationError("Card number must be exactly 16 digits")
        if not luhn.verify(cleaned):
            raise serializers.ValidationError("Invalid card number (LUHN check failed)")
        return cleaned

    def validate_receiver_card_number(self, value):
        """Qabul qiluvchi karta raqamini validatsiya qilish (LUHN + 16 raqam)"""
        cleaned = re.sub(r'[^0-9]', '', str(value))
        if len(cleaned) != 16:
            raise serializers.ValidationError("Card number must be exactly 16 digits")
        if not luhn.verify(cleaned):
            raise serializers.ValidationError("Invalid card number (LUHN check failed)")
        return cleaned

    def validate_sender_card_expiry(self, value):
        """Amal qilish muddatini validatsiya qilish (MM/YY)"""
        pattern = r'^(0[1-9]|1[0-2])\/([0-9]{2})$'
        if not re.match(pattern, str(value)):
            raise serializers.ValidationError("Expiry must be in MM/YY format")
        return value

    def validate(self, data):
        """Umumiy validatsiya"""
        if data['sender_card_number'] == data['receiver_card_number']:
            raise serializers.ValidationError("Sender and receiver cards cannot be the same")
        return data


class TransferConfirmSerializer(serializers.Serializer):
    ext_id = serializers.CharField(max_length=40, required=True)
    otp = serializers.CharField(min_length=6, max_length=6, required=True)

    def validate_ext_id(self, value):
        """Transfer ID ni validatsiya qilish"""
        if not value.startswith('tr-'):
            raise serializers.ValidationError("Invalid transfer ID format")
        return value

    def validate_otp(self, value):
        """OTP ni validatsiya qilish"""
        if not value.isdigit():
            raise serializers.ValidationError("OTP must contain only digits")
        return value


class TransferCancelSerializer(serializers.Serializer):
    ext_id = serializers.CharField(max_length=40, required=True)

    def validate_ext_id(self, value):
        """Transfer ID ni validatsiya qilish"""
        if not value.startswith('tr-'):
            raise serializers.ValidationError("Invalid transfer ID format")
        return value


class TransferStateSerializer(serializers.Serializer):
    ext_id = serializers.CharField(max_length=40, required=True)

    def validate_ext_id(self, value):
        """Transfer ID ni validatsiya qilish"""
        if not value.startswith('tr-'):
            raise serializers.ValidationError("Invalid transfer ID format")
        return value


class TransferHistorySerializer(serializers.Serializer):
    card_number = serializers.CharField(max_length=32, required=True)
    start_date = serializers.DateField(required=True)
    end_date = serializers.DateField(required=True)
    status = serializers.ChoiceField(
        choices=[('created', 'Created'), ('confirmed', 'Confirmed'), ('cancelled', 'Cancelled')],
        required=False
    )

    def validate_card_number(self, value):
        """Karta raqamini validatsiya qilish"""
        cleaned = re.sub(r'[^0-9]', '', str(value))
        if len(cleaned) < 13 or len(cleaned) > 19:
            raise serializers.ValidationError("Card number must be 13-19 digits")
        return value

    def validate(self, data):
        """Sanalarni tekshirish"""
        if data['start_date'] > data['end_date']:
            raise serializers.ValidationError("Start date cannot be later than end date")
        return data