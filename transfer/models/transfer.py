# transfer/models.py
from django.db import models

Currencys = (
    ('643','RUB'),
    ('840','USD'),
    ('860','UZS')
)

State = (
    (1, 'created'),
    (2, 'confirmed'),
    (3, 'cancelled')
)

class Transfer(models.Model):
    ext_id = models.CharField(max_length=40, default='', unique=True, editable=False)
    sender_id = models.TextField()
    receiver_id = models.TextField()
    sending_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    currency = models.CharField(choices=Currencys, max_length=3)
    receiving_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    state = models.IntegerField(choices=State, default=1)
    exchange_rate = models.FloatField(null=True, blank=True)
    rate_updated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    def get_state_display(self):
        return dict(State).get(self.state, 'unknown')

    def __str__(self):
        return f"{self.ext_id} - {self.sender_id} -> {self.receiver_id}"


class Error(models.Model):
    code = models.IntegerField(unique=True)
    en = models.CharField(max_length=255)
    ru = models.CharField(max_length=255)
    uz = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.code} - {self.uz}"