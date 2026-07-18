import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta


class InvalidTokenError(ValueError):
    pass


class ExpiredTokenError(InvalidTokenError):
    pass


class RoomTokenService:
    def __init__(self, secret: str, ttl: timedelta) -> None:
        if len(secret) < 16:
            raise ValueError("room token secret must contain at least 16 characters")
        self._secret = secret.encode()
        self._ttl = ttl

    def issue(self, room_id: str, participant_id: str, now: datetime | None = None) -> str:
        now = now or datetime.now(UTC)
        payload = {
            "room_id": room_id,
            "participant_id": participant_id,
            "exp": int((now + self._ttl).timestamp()),
        }
        encoded = self._encode(json.dumps(payload, separators=(",", ":")).encode())
        signature = self._sign(encoded)
        return f"{encoded}.{signature}"

    def verify(self, token: str, now: datetime | None = None) -> dict[str, str | int]:
        try:
            encoded, supplied_signature = token.split(".", 1)
            expected_signature = self._sign(encoded)
            if not hmac.compare_digest(supplied_signature, expected_signature):
                raise InvalidTokenError("invalid token signature")
            payload = json.loads(self._decode(encoded))
            room_id = payload["room_id"]
            participant_id = payload["participant_id"]
            expires = int(payload["exp"])
            if not isinstance(room_id, str) or not isinstance(participant_id, str):
                raise InvalidTokenError("invalid token claims")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            if isinstance(exc, InvalidTokenError):
                raise
            raise InvalidTokenError("malformed token") from exc
        if int((now or datetime.now(UTC)).timestamp()) >= expires:
            raise ExpiredTokenError("token expired")
        return {"room_id": room_id, "participant_id": participant_id, "exp": expires}

    def _sign(self, value: str) -> str:
        return self._encode(hmac.new(self._secret, value.encode(), hashlib.sha256).digest())

    @staticmethod
    def _encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode()

    @staticmethod
    def _decode(value: str) -> bytes:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
