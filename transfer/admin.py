from django.contrib import admin

from .models import Transfer,Error


# Register your models here.
@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    list_display = ('sender_card_number','receiver_card_number','sending_amount','created_at','confirmed_at','cancelled_at','sender_phone','state')
    search_fields = ['sender_card_number','receiver_card_number','sending_amount','created_at','confirmed_at','cancelled_at','sender_phone','state']



@admin.register(Error)
class ErrorAdmin(admin.ModelAdmin):
    list_display = ('code','uz','ru','en')
    search_fields = ['code','uz','ru','en']