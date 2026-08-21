import base64
import hashlib
from cryptography.fernet import Fernet, InvalidToken
from app.core.config import get_settings


def _fernet() -> Fernet:
    settings = get_settings()
    raw = (settings.encryption_key or settings.jwt_secret).encode("utf-8")
    digest = hashlib.sha256(raw).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt stored secret") from exc
