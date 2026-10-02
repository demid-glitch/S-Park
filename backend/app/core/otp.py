import hashlib
import hmac
import logging
import secrets
from typing import Protocol

from app.core.config import Settings

logger = logging.getLogger(__name__)


class OtpCooldown(Exception):
    pass


class KeyValueStore(Protocol):
    async def set(self, name: str, value: str, ex: int | None = None, nx: bool = False) -> bool | None: ...
    async def get(self, name: str) -> str | None: ...
    async def incr(self, name: str) -> int: ...
    async def expire(self, name: str, time: int) -> bool: ...
    async def delete(self, *names: str) -> int: ...


class SmsSender(Protocol):
    async def send(self, phone: str, message: str) -> None: ...


class ConsoleSmsSender:
    """Placeholder until an SMS provider is chosen. Never prints codes in production."""

    def __init__(self, environment: str) -> None:
        self._environment = environment

    async def send(self, phone: str, message: str) -> None:
        if self._environment == "production":
            logger.error("No SMS provider configured; OTP for %s was not delivered", phone)
        else:
            logger.warning("[dev sms] %s: %s", phone, message)


class OtpService:
    def __init__(self, store: KeyValueStore, sms: SmsSender, settings: Settings) -> None:
        self._store = store
        self._sms = sms
        self._s = settings

    def _hash(self, phone: str, code: str) -> str:
        return hmac.new(self._s.jwt_secret.encode(), f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()

    async def request(self, phone: str) -> None:
        cooldown_ok = await self._store.set(
            f"otp:cooldown:{phone}", "1", ex=self._s.otp_resend_cooldown_seconds, nx=True
        )
        if not cooldown_ok:
            raise OtpCooldown
        code = "".join(secrets.choice("0123456789") for _ in range(self._s.otp_length))
        await self._store.set(f"otp:code:{phone}", self._hash(phone, code), ex=self._s.otp_ttl_seconds)
        await self._store.delete(f"otp:attempts:{phone}")
        await self._sms.send(phone, f"S-Park code: {code}")

    async def verify(self, phone: str, code: str) -> bool:
        code_key, attempts_key = f"otp:code:{phone}", f"otp:attempts:{phone}"
        stored = await self._store.get(code_key)
        if stored is None:
            return False
        attempts = await self._store.incr(attempts_key)
        await self._store.expire(attempts_key, self._s.otp_ttl_seconds)
        if attempts > self._s.otp_max_attempts:
            await self._store.delete(code_key, attempts_key)
            return False
        if not hmac.compare_digest(stored, self._hash(phone, code)):
            return False
        await self._store.delete(code_key, attempts_key)
        return True
