from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models._types import BigIntPK, JsonType, enum_column
from app.models.enums import PaymentKind, PaymentMethod, PaymentStatus


class Payment(TimestampMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="amount_non_negative"),
        # Cash must be attributable to the attendant who took it.
        CheckConstraint("method <> 'cash' OR recorded_by_id IS NOT NULL", name="cash_has_attendant"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    lot_id: Mapped[int] = mapped_column(ForeignKey("lots.id", ondelete="RESTRICT"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    kind: Mapped[PaymentKind] = mapped_column(enum_column(PaymentKind, "payment_kind"))
    method: Mapped[PaymentMethod] = mapped_column(enum_column(PaymentMethod, "payment_method"), index=True)
    status: Mapped[PaymentStatus] = mapped_column(
        enum_column(PaymentStatus, "payment_status"), default=PaymentStatus.PENDING, index=True
    )
    amount: Mapped[int] = mapped_column(Integer)
    commission_amount: Mapped[int] = mapped_column(Integer, default=0)

    parking_session_id: Mapped[int | None] = mapped_column(
        ForeignKey("parking_sessions.id", ondelete="SET NULL"), index=True
    )
    # EV sessions arrive with the OCPP module; FK added then.
    ev_session_id: Mapped[int | None] = mapped_column(BigInteger)

    recorded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    shift_id: Mapped[int | None] = mapped_column(ForeignKey("shifts.id", ondelete="SET NULL"), index=True)

    idempotency_key: Mapped[str | None] = mapped_column(String(64), unique=True)
    qpay_invoice_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    qpay_payment_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    events: Mapped[list["PaymentEvent"]] = relationship(
        back_populates="payment", cascade="all, delete-orphan", order_by="PaymentEvent.id"
    )


class PaymentEvent(TimestampMixin, Base):
    """Append-only log of everything that happened to a payment (callbacks, checks, status changes)."""

    __tablename__ = "payment_events"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id", ondelete="CASCADE"), index=True)
    event: Mapped[str] = mapped_column(String(40))
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str | None] = mapped_column(String(20))
    payload: Mapped[dict[str, Any] | None] = mapped_column(JsonType)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    payment: Mapped[Payment] = relationship(back_populates="events")
