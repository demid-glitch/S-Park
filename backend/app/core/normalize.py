import re

_PHONE_RE = re.compile(r"^\+[1-9]\d{7,14}$")
_SEPARATORS = re.compile(r"[\s\-()]")


def normalize_phone(raw: str) -> str:
    """Returns E.164. Bare 8-digit numbers are treated as Mongolian (+976)."""
    phone = _SEPARATORS.sub("", raw)
    if phone.startswith("00"):
        phone = "+" + phone[2:]
    if re.fullmatch(r"\d{8}", phone):
        phone = "+976" + phone
    elif re.fullmatch(r"976\d{8}", phone):
        phone = "+" + phone
    if not _PHONE_RE.fullmatch(phone):
        raise ValueError("invalid phone number")
    return phone


def normalize_plate(raw: str) -> str:
    plate = _SEPARATORS.sub("", raw).upper()
    if not 2 <= len(plate) <= 16:
        raise ValueError("invalid plate")
    return plate


_USERNAME_RE = re.compile(r"^[a-z0-9_.-]{3,50}$")


def normalize_username(raw: str) -> str:
    username = raw.strip().lower()
    if not _USERNAME_RE.fullmatch(username):
        raise ValueError("username must be 3-50 characters: letters, digits, _ . -")
    return username
