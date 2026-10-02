from pydantic import BaseModel, Field

from app.schemas.common import Phone


class OtpRequest(BaseModel):
    phone: Phone


class OtpVerify(BaseModel):
    phone: Phone
    code: str = Field(pattern=r"^\d{4,8}$")


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
