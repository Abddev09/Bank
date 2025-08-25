from django.core.management.base import BaseCommand
from transfer.models import Error

ERRORS = [
    (32700, "Ext id must be unique", "Ext id должен быть уникальным", "Ext id noyob bo'lishi kerak"),
    (32701, "Ext id already exists", "Ext id уже существует", "Ext id allaqachon mavjud"),
    (32702, "Balance is not enough", "Недостаточно средств", "Hisobda mablag‘ yetarli emas"),
    (32703, "SMS service is not bind", "SMS сервис не подключен", "SMS xizmati ulanmagan"),
    (32704, "Card expiry is not valid", "Срок действия карты недействителен", "Karta amal qilish muddati noto‘g‘ri"),
    (32705, "Card is not active", "Карта неактивна", "Karta faol emas"),
    (32706, "Unknown error occurred", "Произошла неизвестная ошибка", "Noma’lum xatolik yuz berdi"),
    (32707, "Currency not allowed except 860, 643, 840", "Разрешены только валюты 860, 643, 840", "Faqat 860, 643, 840 valyutalari ruxsat etilgan"),
    (32708, "Amount is greater than allowed", "Сумма превышает допустимую", "Miqdor ruxsat etilgan chegaradan katta"),
    (32709, "Amount is small", "Сумма слишком мала", "Miqdor juda kichik"),
    (32710, "OTP expired", "OTP истек", "OTP muddati tugagan"),
    (32711, "Count of try is reached", "Превышено количество попыток", "Urinishlar soni tugadi"),
    (32712, "OTP is wrong, left try count is 2", "Неверный OTP, осталось 2 попытки", "Noto‘g‘ri OTP, yana 2 urinish qoldi"),
    (32713, "Method is not allowed", "Метод не разрешён", "Usulga ruxsat berilmagan"),
    (32714, "Method not found", "Метод не найден", "Usul topilmadi"),
]

class Command(BaseCommand):
    help = 'Populate Error model with predefined error messages'

    def handle(self, *args, **options):
        for code, en, ru, uz in ERRORS:
            error_obj, created = Error.objects.get_or_create(
                code=code,
                defaults={'en': en, 'ru': ru, 'uz': uz}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Added error {code}'))
            else:
                self.stdout.write(self.style.WARNING(f'Error {code} already exists'))
