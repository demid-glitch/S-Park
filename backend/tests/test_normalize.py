import pytest

from app.core.normalize import normalize_phone, normalize_plate


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("99112233", "+97699112233"),
        ("9911 2233", "+97699112233"),
        ("+976 9911-2233", "+97699112233"),
        ("97699112233", "+97699112233"),
        ("0097699112233", "+97699112233"),
        ("+14155552671", "+14155552671"),
    ],
)
def test_normalize_phone(raw, expected):
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize("raw", ["", "123", "abcdefgh", "+0123456789"])
def test_normalize_phone_rejects(raw):
    with pytest.raises(ValueError):
        normalize_phone(raw)


def test_normalize_plate():
    assert normalize_plate(" 1234 уба ") == "1234УБА"
    assert normalize_plate("12-34-УБА") == "1234УБА"
    with pytest.raises(ValueError):
        normalize_plate(" ")
