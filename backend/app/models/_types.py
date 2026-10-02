import enum

from sqlalchemy import JSON, BigInteger, Enum, Integer
from sqlalchemy.dialects.postgresql import JSONB

JsonType = JSON().with_variant(JSONB(), "postgresql")


def enum_column(enum_cls: type[enum.Enum], name: str) -> Enum:
    """Stores enum *values* (e.g. "platform_admin") rather than member names."""
    return Enum(
        enum_cls,
        name=name,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )

# SQLite only autoincrements INTEGER PRIMARY KEY, so tests use Integer there.
BigIntPK = BigInteger().with_variant(Integer, "sqlite")
