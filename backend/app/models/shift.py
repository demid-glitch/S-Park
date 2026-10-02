from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models._types import BigIntPK, enum_column
from app.models.enums import ShiftStatus


class Shift(TimestampMixin, Base):
    __tablename__ = "shifts"
    __table_args__ = (
        # An attendant can have only one open shift at a time.
        Index(
            "uq_shifts_open_attendant",
            "attendant_id",
            unique=True,
            postgresql_where=text("status = 'open'"),
            sqlite_where=text("status = 'open'"),
        ),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    attendant_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    lot_id: Mapped[int] = mapped_column(ForeignKey("lots.id", ondelete="RESTRICT"), index=True)
    status: Mapped[ShiftStatus] = mapped_column(enum_column(ShiftStatus, "shift_status"), default=ShiftStatus.OPEN)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expected_cash: Mapped[int | None] = mapped_column(Integer)
    declared_cash: Mapped[int | None] = mapped_column(Integer)
    confirmed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
