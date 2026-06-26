from app.core.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip():
    h = hash_password("supersecret")
    assert h != "supersecret"
    assert verify_password("supersecret", h)
    assert not verify_password("wrong", h)


def test_jwt_roundtrip():
    token = create_access_token("42")
    assert decode_token(token) == "42"
    assert decode_token("garbage") is None
