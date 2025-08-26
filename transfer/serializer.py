# transfer/serializer.py
import uuid
from datetime import datetime
from rest_framework import serializers

from utils import format_card_number
from transfer.models import Transfer, Error
from card.models import Card

class TransferSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transfer
        fields = [
            'ext_id',
            'sender_card_number',
            'receiver_card_number',
            'sender_card_expiry',
            'sending_amount',
            'currency',
        ]
        read_only_fields = ['ext_id']

    def get_error(self, code):
        try:
            return Error.objects.get(code=code)
        except Error.DoesNotExist:
            return None

    def validate_sender_card_number(self, value):

        try:
            card_formatted_number = format_card_number(value)
            card = Card.objects.get(card_number=card_formatted_number)
        except Card.DoesNotExist:
            error = self.get_error(32701)
            raise serializers.ValidationError(
                {"code": error.code if error else 32701, "message": error.en if error else "Sender card not found"}
            )

        if card.status != 'active':
            error = self.get_error(32705)
            raise serializers.ValidationError(
                {"code": error.code if error else 32705, "message": error.en if error else "Sender card not active"}
            )

        self.sender_card_instance = card
        return value

    def validate_receiver_card_number(self, value):
        try:
            card_formatted_number = format_card_number(value)
            card = Card.objects.get(card_number=card_formatted_number)
        except Card.DoesNotExist:
            error = self.get_error(32701)
            raise serializers.ValidationError(
                {"code": error.code if error else 32701, "message": error.en if error else "Receiver card not found"}
            )

        if card.status != 'active':
            error = self.get_error(32705)
            raise serializers.ValidationError(
                {"code": error.code if error else 32705, "message": error.en if error else "Receiver card not active"}
            )

        self.receiver_card_instance = card
        return value

    def validate_sender_card_expiry(self, value):
        card = getattr(self, 'sender_card_instance', None)
        if not card:
            error = self.get_error(32706)
            raise serializers.ValidationError(
                {"code": error.code if error else 32706, "message": error.en if error else "Sender card missing"}
            )

        try:
            month, year = map(int, value.split('/'))
            exp_date = datetime(year + 2000, month, 1)
        except:
            error = self.get_error(32704)
            raise serializers.ValidationError(
                {"code": error.code if error else 32704, "message": error.en if error else "Invalid expiry"}
            )

        if exp_date < datetime.now():
            error = self.get_error(32704)
            raise serializers.ValidationError(
                {"code": error.code if error else 32704, "message": error.en if error else "Card expired"}
            )

        if card.expire != value:
            error = self.get_error(32704)
            raise serializers.ValidationError(
                {"code": error.code if error else 32704, "message": error.en if error else "Expiry mismatch"}
            )

        return value

    def validate_currency(self, value):
        allowed = ['643', '840', '860']
        if str(value) not in allowed:
            error = self.get_error(32707)
            raise serializers.ValidationError(
                {"code": error.code if error else 32707, "message": error.en if error else "Currency not allowed"}
            )
        return str(value)

    def validate_sending_amount(self, value):
        card = getattr(self, 'sender_card_instance', None)
        if not card:
            error = self.get_error(32706)
            raise serializers.ValidationError(
                {"code": error.code if error else 32706, "message": error.en if error else "Sender card missing"}
            )

        if value <= 0:
            error = self.get_error(32709)
            raise serializers.ValidationError(
                {"code": error.code if error else 32709, "message": error.en if error else "Amount too small"}
            )

        if value > card.balance:
            error = self.get_error(32702)
            raise serializers.ValidationError(
                {"code": error.code if error else 32702, "message": error.en if error else "Balance not enough"}
            )

        return value

    def create(self, validated_data):
        validated_data['ext_id'] = f"tr-{uuid.uuid4()}"
        validated_data['receiver_phone'] = self.receiver_card_instance.phone
        validated_data['sender_phone'] = self.sender_card_instance.phone
        validated_data['state'] = 1
        # OTP generatsiya qilamiz (masalan, 6 xonali random)
        validated_data['otp'] = str(uuid.uuid4().int)[:6]
        return super().create(validated_data)




class ErrorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Error
        fields = '__all__'

