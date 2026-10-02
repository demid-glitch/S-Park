from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.models import SpotStatus, TariffKind
from app.schemas.common import ORMModel


class LotPublic(ORMModel):
    id: int
    name: str
    address: str | None
    latitude: Decimal | None
    longitude: Decimal | None


class LotOut(LotPublic):
    owner_id: int
    commission_percent: Decimal
    is_active: bool


class LotCreate(BaseModel):
    owner_id: int
    name: str = Field(max_length=120)
    address: str | None = Field(default=None, max_length=255)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    commission_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)


class LotUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    address: str | None = Field(default=None, max_length=255)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    commission_percent: Decimal | None = Field(default=None, ge=0, le=100)
    is_active: bool | None = None


class Occupancy(BaseModel):
    capacity: int
    free: int
    occupied: int
    reserved: int
    out_of_service: int
    occupancy_percent: float


class ZoneCreate(BaseModel):
    name: str = Field(max_length=60)


class ZoneOut(ORMModel):
    id: int
    lot_id: int
    name: str


class SpotsCreate(BaseModel):
    codes: list[str] = Field(min_length=1, max_length=500)
    is_ev: bool = False


class SpotOut(ORMModel):
    id: int
    zone_id: int
    code: str
    status: SpotStatus
    is_ev: bool


class TariffBase(BaseModel):
    name: str = Field(max_length=60)
    kind: TariffKind
    rate: int = Field(ge=0)
    free_minutes: int = Field(default=0, ge=0)
    daily_cap: int | None = Field(default=None, ge=0)


class TariffCreate(TariffBase):
    @model_validator(mode="after")
    def _cap_only_for_hourly(self) -> "TariffCreate":
        if self.daily_cap is not None and self.kind != TariffKind.HOURLY:
            raise ValueError("daily_cap applies to hourly tariffs only")
        return self


class TariffUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=60)
    rate: int | None = Field(default=None, ge=0)
    free_minutes: int | None = Field(default=None, ge=0)
    daily_cap: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class TariffOut(ORMModel, TariffBase):
    id: int
    lot_id: int
    is_active: bool
