from transfer.models import Error


def get_error_response(error_code):
    try:
        error = Error.objects.get(code=error_code)
        return {
            "code": error.code,
            "message": error.en,
            "message_uz": error.uz,
            "message_ru": error.ru,
            "message_en": error.en,
        }
    except:
        return {
            "code": 32706,
            "message": "Unknown error occurred",
            "message_uz": "Noma'lum xatolik yuz berdi",
            "message_ru": "Произошла неизвестная ошибка",
            "message_en": "Unknown error occurred",
        }