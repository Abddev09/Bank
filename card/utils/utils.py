

def format_card_number(card_number: str) -> str:
    """Karta raqamini faqat raqamlardan 16 xonali qilib 4 guruh ko‘rinishida qaytaradi"""
    digits = ''.join(filter(str.isdigit, str(card_number)))
    if not digits:
        return None
    digits = digits.zfill(16)[:16]  # ortiqcha bo‘lsa kesamiz
    return ' '.join(digits[i:i+4] for i in range(0, 16, 4))


def format_phone_number(phone_number: str) -> str:
    """Telefon raqamni +998 XX XXX XX XX formatga keltiradi"""
    if not phone_number or str(phone_number).lower() in ["nan", "none", "empty"]:
        return None

    digits = ''.join(filter(str.isdigit, str(phone_number)))

    # Agar 9 xonali bo‘lsa (masalan 887091228) -> 998 bilan to‘ldiramiz
    if len(digits) == 9:
        digits = "998" + digits
    elif len(digits) == 12 and digits.startswith("998"):
        pass
    else:
        return digits  # noma’lum format bo‘lsa shuni qaytaradi

    # Formatlab chiqarish: +998 XX XXX XX XX
    return f"+{digits[0:3]} {digits[3:5]} {digits[5:8]} {digits[8:10]} {digits[10:12]}"


def format_expire(expire: str) -> str:
    if not expire or str(expire).lower() in ["nan", "none", "empty"]:
        return None

    expire = str(expire).replace(" ", "").replace("-", ".").replace("/", ".")
    parts = expire.split(".")

    if len(parts) != 2:
        return expire

    a, b = parts

    if len(a) == 4 and a.isdigit():
        yy = a[-2:]
        mm = b.zfill(2)
    elif len(b) == 4 and b.isdigit():
        yy = b[-2:]
        mm = a.zfill(2)

    else:
        if int(a) > 12:
            yy = a[-2:]
            mm = b.zfill(2)
        elif int(b) > 12:
            yy = b[-2:]
            mm = a.zfill(2)
        else:
            mm = a.zfill(2)
            yy = b[-2:]

    return f"{mm}/{yy}"



def format_balance(balance) -> float:
    if not balance or str(balance).lower() in ["nan", "none", "empty"]:
        return 0.0
    return float(str(balance).replace(",", "").replace(" ", ""))


def card_mask(card_number: str) -> str:
    return f"{card_number[:4]} {card_number[4:7]}** **** {card_number[-4:]}"

def phone_mask(phone: str) -> str:
    return phone[:7] + "****"


def prepare_message(card_number, balance, lang="UZ"):
    if lang == "UZ":
        return f"Sizning kartangiz {card_mask(card_number)} aktiv va foydalanishga {balance} UZS mavjud!"
    # boshqa tillarni ham qo‘shish mumkin



