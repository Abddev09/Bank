from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

import uuid

from card.models import Card

Currencys = (
    ('643','RUB'),
    ('840','USD'),
    ('860','UZS')
)

State = (
    ('created', 'created'),
    ('confirmed', 'confirmed'),
    ('cancelled', 'cancelled')
)

class Transfer(models.Model):
    ext_id = models.CharField(max_length=40, default='', unique=True, editable=False)
    sender_card_number = models.CharField(max_length=20)
    receiver_card_number = models.CharField(max_length=20)
    sender_card_expiry = models.CharField(max_length=5)
    sender_phone = models.CharField(max_length=20)
    receiver_phone = models.CharField(max_length=20)
    sending_amount = models.PositiveIntegerField()
    currency = models.CharField(choices=Currencys)
    receiving_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    state = models.CharField(choices=State)
    try_count = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(3)])
    otp = models.CharField(max_length=6,null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True,blank=True)
    cancelled_at = models.DateTimeField(null=True,blank=True)


class Error(models.Model):
    code = models.IntegerField(unique=True)
    en = models.CharField(max_length=255)
    ru = models.CharField(max_length=255)
    uz = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.code} - {self.uz}"