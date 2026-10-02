from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models._types import BigIntPK, enum_column
from app.models.enums import SpotStatus, TariffKind


class Lot(TimestampMixin, Base):
    __tablename__ = "lots"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    address: Mapped[str | None] = mapped_column(String(255))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    # Platform commission taken from each online (QPay) payment, in percent.
    commission_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    zones: Mapped[list["Zone"]] = relationship(back_populates="lot", cascade="all, delete-orphan")
    tariffs: Mapped[list["Tariff"]] = relationship(back_populates="lot", cascade="all, delete-orphan")


class Zone(TimestampMixin, Base):
    __tablename__ = "zones"
    __table_args__ = (UniqueConstraint("lot_id", "name", name="uq_zones_lot_name"),)

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    lot_id: Mapped[int] = mapped_column(ForeignKey("lots.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(60))

    lot: Mapped[Lot] = relationship(back_populates="zones")
    spots: Mapped[list["Spot"]] = relationship(back_populates="zone", cascade="all, delete-orphan")


class Spot(TimestampMixin, Base):
    __tablename__ = "spots"
    __table_args__ = (UniqueConstraint("lot_id", "code", name="uq_spots_lot_code"),)

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    # Denormalized from zone so occupancy queries per lot need no join.
    lot_id: Mapped[int] = mapped_column(ForeignKey("lots.id", ondelete="CASCADE"), index=True)
    zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(20))
    status: Mapped[SpotStatus] = mapped_column(enum_column(SpotStatus, "spot_status"), default=SpotStatus.FREE)
    is_ev: Mapped[bool] = mapped_column(Boolean, default=False)

    zone: Mapped[Zone] = relationship(back_populates="spots")


class Tariff(TimestampMixin, Base):
    __tablename__ = "tariffs"
    __table_args__ = (
        CheckConstraint("rate >= 0", name="rate_non_negative"),
        CheckConstraint("free_minutes >= 0", name="free_minutes_non_negative"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    lot_id: Mapped[int] = mapped_column(ForeignKey("lots.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    kind: Mapped[TariffKind] = mapped_column(enum_column(TariffKind, "tariff_kind"))
    # Whole tugrik (MNT has no minor unit in practice).
    rate: Mapped[int] = mapped_column(Integer)
    free_minutes: Mapped[int] = mapped_column(Integer, default=0)
    daily_cap: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    lot: Mapped[Lot] = relationship(back_populates="tariffs")
