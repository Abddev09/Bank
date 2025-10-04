# card/models.py
import uuid
from django.db import models
from import_export import resources, results
from import_export.results import RowResult
from utils import format_card_number, format_expire, format_phone_number, format_balance, luhn_check

from django.core.exceptions import ValidationError

Status = (
    ('expired', 'expired'),
    ('active', 'active'),
    ('inactive', 'inactive')
)

class Card(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    card_number = models.CharField(max_length=32, unique=True)
    expire = models.CharField(max_length=20, null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status, default="active")
    balance = models.FloatField(default=0.0)

    def clean_card_number(self, card_number: str) -> str:
        """Kartani formatlash va validatsiya (16 digit + LUHN)"""
        formatted_card = format_card_number(card_number)
        clean_card = formatted_card.replace(" ", "")

        if len(clean_card) != 16:
            raise ValidationError(f"Card number must be exactly 16 digits: {card_number}")

        if not luhn_check(clean_card):
            raise ValidationError(f"Invalid card number (LUHN failed): {card_number}")

        return clean_card

    def save(self, *args, **kwargs):
        # Karta raqamini formatlash va tekshirish
        if self.card_number:
            self.card_number = self.clean_card_number(self.card_number)

        if self.expire:
            self.expire = format_expire(self.expire)
        if self.phone:
            self.phone = format_phone_number(self.phone)
        if self.balance is not None:
            self.balance = format_balance(self.balance)

        super().save(*args, **kwargs)

    def __str__(self):
        display_number = format_card_number(self.card_number) if self.card_number else ""
        return f"{display_number} ({self.status})"


class CardResource(resources.ModelResource):
    class Meta:
        model = Card
        import_id_fields = ['card_number']
        skip_unchanged = True
        use_bulk = True
        exclude = ('id',)

    def before_import_row(self, row, **kwargs):
        # id ni olib tashlash
        row.pop("id", None)

        if "card_number" in row:
            clean_card = Card().clean_card_number(row["card_number"])
            row["card_number"] = clean_card

        if "expire" in row:
            row["expire"] = format_expire(row["expire"])
        if "phone" in row:
            row["phone"] = format_phone_number(row["phone"])
        if "balance" in row:
            row["balance"] = format_balance(row["balance"])

    def import_row(self, row, instance_loader, **kwargs):
        if row.get("card_number") and Card.objects.filter(card_number=row["card_number"]).exists():
            result = RowResult()
            result.import_type = results.RowResult.IMPORT_TYPE_SKIP
            result.diff = [row.get(f) for f in self.get_fields()]
            return result

        return super().import_row(row, instance_loader, **kwargs)
