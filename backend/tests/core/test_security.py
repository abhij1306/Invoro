from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet

from app.core import security


def test_password_hash_verify_roundtrip() -> None:
    hashed = security.hash_password("correct horse battery staple")

    assert security.verify_password("correct horse battery staple", hashed) is True
    assert security.verify_password("wrong password", hashed) is False


def test_access_token_roundtrip(monkeypatch) -> None:
    monkeypatch.setattr(security.settings, "jwt_secret_key", "test-jwt-secret")
    monkeypatch.setattr(security.settings, "jwt_algorithm", "HS256")
    monkeypatch.setattr(security.settings, "jwt_expire_hours", 1)

    token = security.create_access_token("user-123", token_version=7)
    payload = security.decode_access_token(token)

    assert payload["sub"] == "user-123"
    assert payload["ver"] == 7


def test_encrypt_secret_roundtrip_uses_sha256_key_derivation(monkeypatch) -> None:
    raw_key = "short-but-stable-test-key"
    monkeypatch.setattr(security.settings, "encryption_key", raw_key)

    encrypted = security.encrypt_secret("provider-secret")

    assert security.decrypt_secret(encrypted) == "provider-secret"
    derived_key = base64.urlsafe_b64encode(
        hashlib.sha256(raw_key.encode("utf-8")).digest()
    )
    assert Fernet(derived_key).decrypt(encrypted.encode("utf-8")) == b"provider-secret"
