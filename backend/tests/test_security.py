"""JWT + password hashing."""
from datetime import timedelta

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_roundtrip():
    hashed = hash_password("Secret123!")
    assert hashed != "Secret123!"
    assert verify_password("Secret123!", hashed)
    assert not verify_password("wrong", hashed)


def test_token_roundtrip():
    token = create_access_token("user-id-123")
    assert decode_access_token(token) == "user-id-123"


def test_expired_token_rejected():
    token = create_access_token("user-id-123", expires_delta=timedelta(seconds=-1))
    assert decode_access_token(token) is None


def test_garbage_token_rejected():
    assert decode_access_token("not-a-jwt") is None
