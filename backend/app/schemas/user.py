from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models import Role
from app.schemas.common import ORMModel, Phone, Plate

Language = Literal["mn", "en"]


class UserOut(ORMModel):
    id: int
    phone: str | None
    username: str | None
    full_name: str | None
    email: str | None
    role: Role
    is_active: bool
    language: str
    assigned_lot_id: int | None
    created_at: datetime


class UserSelfUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=255)
    language: Language | None = None


class StaffCreate(BaseModel):
    phone: Phone
    full_name: str = Field(max_length=120)
    role: Role
    assigned_lot_id: int | None = None


class StaffUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=120)
    role: Role | None = None
    is_active: bool | None = None
    assigned_lot_id: int | None = None


class VehicleCreate(BaseModel):
    plate: Plate
    label: str | None = Field(default=None, max_length=60)


class VehicleOut(ORMModel):
    id: int
    plate: str
    label: str | None
