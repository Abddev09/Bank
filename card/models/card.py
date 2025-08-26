from django.db import models
from import_export import resources, results
from import_export.results import RowResult

from utils import format_card_number, format_expire, format_phone_number, format_balance

Status = (
    ('expired', 'expired'),
    ('active', 'active'),
    ('inactive', 'inactive')
)

class Card(models.Model):
    card_number = models.CharField(max_length=32, unique=True)
    expire = models.CharField(max_length=20, null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status, default="active")
    balance = models.FloatField(default=0.0)

    def save(self, *args, **kwargs):
        # Farmatting
        if self.card_number:
            self.card_number = format_card_number(self.card_number)
        if self.expire:
            self.expire = format_expire(self.expire)
        if self.phone:
            self.phone = format_phone_number(self.phone)
        if self.balance is not None:
            self.balance = format_balance(self.balance)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.card_number} ({self.status})"







class CardResource(resources.ModelResource):
    class Meta:
        model = Card
        import_id_fields = ['card_number']  # idsiz faqat card number ni pk qilib qaabul qisin
        skip_unchanged = True
        use_bulk = True
        exclude = ('id',)   # id umuman ishlatilmidi

    def before_import_row(self, row, **kwargs):
        # id kesa op tashimiz kerak emas chunki
        row.pop("id", None)

        # Farmatting
        if "card_number" in row:
            row["card_number"] = format_card_number(row["card_number"])
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
            result.diff = [row.get(f) for f in self.get_fields()]  # preview uchun ko'rsatish
            return result

        return super().import_row(row, instance_loader, **kwargs)

