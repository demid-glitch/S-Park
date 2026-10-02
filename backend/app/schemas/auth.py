from pydantic import BaseModel, Field

from app.schemas.common import Phone


class OtpRequest(BaseModel):
    phone: Phone


class OtpVerify(BaseModel):
    phone: Phone
    code: str = Field(pattern=r"^\d{4,8}$")


class PasswordLogin(BaseModel):
    username: str = Field(max_length=50)
    password: str = Field(max_length=256)


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=256)
    new_password: str = Field(min_length=10, max_length=256)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
