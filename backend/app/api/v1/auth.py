from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import DbSession, get_otp_service
from app.core.otp import OtpCooldown, OtpService
from app.core.security import InvalidToken, create_access_token, create_refresh_token, decode_token
from app.models import Role, User
from app.schemas.auth import OtpRequest, OtpVerify, RefreshRequest, TokenPair

router = APIRouter(prefix="/auth", tags=["auth"])

Otp = Annotated[OtpService, Depends(get_otp_service)]


def _tokens(user: User) -> TokenPair:
    return TokenPair(access_token=create_access_token(user.id), refresh_token=create_refresh_token(user.id))


@router.post("/otp/request", status_code=status.HTTP_202_ACCEPTED)
async def request_otp(body: OtpRequest, otp: Otp) -> dict[str, str]:
    try:
        await otp.request(body.phone)
    except OtpCooldown:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Please wait before requesting another code")
    return {"detail": "sent"}


@router.post("/otp/verify")
async def verify_otp(body: OtpVerify, otp: Otp, db: DbSession) -> TokenPair:
    if not await otp.verify(body.phone, body.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired code")

    user = await db.scalar(select(User).where(User.phone == body.phone))
    if user is None:
        # Self sign-up always creates a customer; staff accounts are created by admins/owners.
        user = User(phone=body.phone, role=Role.CUSTOMER)
        db.add(user)
        await db.commit()
        await db.refresh(user)
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account disabled")
    return _tokens(user)


@router.post("/refresh")
async def refresh(body: RefreshRequest, db: DbSession) -> TokenPair:
    try:
        user_id = decode_token(body.refresh_token, "refresh")
    except InvalidToken:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token") from None
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    return _tokens(user)
