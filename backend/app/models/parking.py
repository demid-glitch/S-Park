from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models._types import BigIntPK, enum_column
from app.models.enums import ParkingSessionStatus


class ParkingSession(TimestampMixin, Base):
    __tablename__ = "parking_sessions"
    __table_args__ = (
        # One open session per plate per lot.
        Index(
            "uq_parking_sessions_open_plate",
            "lot_id",
            "plate",
            unique=True,
            postgresql_where=text("status = 'open'"),
            sqlite_where=text("status = 'open'"),
        ),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    lot_id: Mapped[int] = mapped_column(ForeignKey("lots.id", ondelete="RESTRICT"), index=True)
    spot_id: Mapped[int | None] = mapped_column(ForeignKey("spots.id", ondelete="SET NULL"))
    tariff_id: Mapped[int | None] = mapped_column(ForeignKey("tariffs.id", ondelete="SET NULL"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    plate: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[ParkingSessionStatus] = mapped_column(
        enum_column(ParkingSessionStatus, "parking_session_status"), default=ParkingSessionStatus.OPEN
    )
    entry_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    exit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    amount: Mapped[int | None] = mapped_column(Integer)
    opened_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    closed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
