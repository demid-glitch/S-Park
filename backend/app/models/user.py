from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models._types import BigIntPK, enum_column
from app.models.enums import Role


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("phone IS NOT NULL OR username IS NOT NULL", name="has_login"),)

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, index=True)
    # Staff may also log in with username + password; customers use phone OTP only.
    username: Mapped[str | None] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(enum_column(Role, "user_role"), default=Role.CUSTOMER, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    language: Mapped[str] = mapped_column(String(2), default="mn")
    # Attendants work at exactly one lot; null for every other role.
    assigned_lot_id: Mapped[int | None] = mapped_column(
        ForeignKey("lots.id", ondelete="SET NULL", use_alter=True), index=True
    )

    vehicles: Mapped[list["Vehicle"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Vehicle(TimestampMixin, Base):
    __tablename__ = "vehicles"
    __table_args__ = (UniqueConstraint("user_id", "plate", name="uq_vehicles_user_plate"),)

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plate: Mapped[str] = mapped_column(String(16), index=True)
    label: Mapped[str | None] = mapped_column(String(60))

    user: Mapped[User] = relationship(back_populates="vehicles")
