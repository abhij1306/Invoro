# Password hashing, JWT handling, and encryption helpers.
from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2 import exceptions as argon2_exceptions
from app.core.config import settings
from cryptography.fernet import Fernet, InvalidToken
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import OctKey
from joserfc.jwt import JWTClaimsRegistry

_PASSWORD_HASHER = PasswordHasher()
_ARGON2_PREFIXES = ("$argon2id$", "$argon2i$", "$argon2d$")
_LEGACY_PBKDF2_SHA256_SCHEME = "pbkdf2-sha256"
_LEGACY_PBKDF2_MAX_ROUNDS = 1_000_000


class TokenDecodeError(ValueError):
    """Raised when a JWT cannot be decoded or validated."""


def _jwt_key() -> OctKey:
    return OctKey.import_key(settings.jwt_secret_key)


def hash_password(password: str) -> str:
    return _PASSWORD_HASHER.hash(password)


def _is_argon2_hash(hashed_password: str) -> bool:
    return str(hashed_password or "").startswith(_ARGON2_PREFIXES)


def _decode_passlib_base64(value: str) -> bytes:
    encoded = value.replace(".", "+")
    return base64.b64decode(encoded + ("=" * (-len(encoded) % 4)), validate=True)


def _verify_legacy_pbkdf2_sha256(password: str, hashed_password: str) -> bool:
    parts = hashed_password.split("$")
    if len(parts) != 5 or parts[0] or parts[1] != _LEGACY_PBKDF2_SHA256_SCHEME:
        return False
    rounds_text, salt_text, checksum_text = parts[2:]
    if not rounds_text.isascii() or not rounds_text.isdecimal():
        return False
    rounds = int(rounds_text)
    if not 1 <= rounds <= _LEGACY_PBKDF2_MAX_ROUNDS:
        return False
    if not salt_text or len(salt_text) > 128 or len(checksum_text) > 128:
        return False
    salt = _decode_passlib_base64(salt_text)
    expected = _decode_passlib_base64(checksum_text)
    if len(expected) != hashlib.sha256().digest_size:
        return False
    actual = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        rounds,
    )
    return hmac.compare_digest(actual, expected)


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        if _is_argon2_hash(hashed_password):
            return _PASSWORD_HASHER.verify(hashed_password, password)
        return _verify_legacy_pbkdf2_sha256(password, hashed_password)
    except (TypeError, ValueError, argon2_exceptions.Argon2Error):
        return False


def password_needs_rehash(hashed_password: str) -> bool:
    try:
        if _is_argon2_hash(hashed_password):
            return _PASSWORD_HASHER.check_needs_rehash(hashed_password)
        return True
    except (TypeError, ValueError, argon2_exceptions.Argon2Error):
        return False


def create_access_token(subject: str, *, token_version: int = 0) -> str:
    expires_at = datetime.now(UTC) + timedelta(hours=settings.jwt_expire_hours)
    payload = {"sub": subject, "exp": expires_at, "ver": token_version}
    return jwt.encode(
        {"alg": settings.jwt_algorithm},
        payload,
        _jwt_key(),
        algorithms=[settings.jwt_algorithm],
    )


def decode_access_token(token: str) -> dict[str, str | int]:
    try:
        decoded = jwt.decode(
            token,
            _jwt_key(),
            algorithms=[settings.jwt_algorithm],
        )
        JWTClaimsRegistry().validate(decoded.claims)
    except JoseError as exc:
        raise TokenDecodeError("Invalid token") from exc
    return dict(decoded.claims)


def _fernet() -> Fernet:
    key = settings.encryption_key.encode("utf-8")
    derived_key = base64.urlsafe_b64encode(hashlib.sha256(key).digest())
    return Fernet(derived_key)


def _legacy_fernet() -> Fernet:
    key = settings.encryption_key.encode("utf-8")
    padded_key = base64.urlsafe_b64encode(key.ljust(32, b"0")[:32])
    return Fernet(padded_key)


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str) -> str:
    token = value.encode("utf-8")
    try:
        return _fernet().decrypt(token).decode("utf-8")
    except InvalidToken:
        return _legacy_fernet().decrypt(token).decode("utf-8")
