"""Tests for app.utils.auth.decrypt_api_key."""

import pytest

from app.utils.auth.decrypt_api_key import decrypt_api_key
from app.utils.auth.encrypt_api_key import encrypt_api_key


def test_round_trip_decrypt_matches_original(monkeypatch):
    """Encrypting then decrypting must return the original plaintext."""
    monkeypatch.setenv("SECRET_KEY", "round-trip-secret")
    original = "sk-live-abc123xyz"
    encrypted = encrypt_api_key(original)
    assert decrypt_api_key(encrypted) == original


def test_round_trip_with_unicode(monkeypatch):
    """Round-trip works with unicode characters."""
    monkeypatch.setenv("SECRET_KEY", "round-trip-secret")
    original = "key-\u00e9\u00e0\u00fc-\u4e16\u754c"
    encrypted = encrypt_api_key(original)
    assert decrypt_api_key(encrypted) == original


def test_decrypt_raises_on_empty_input(monkeypatch):
    """Empty or None-ish input must raise ValueError."""
    monkeypatch.setenv("SECRET_KEY", "some-secret")
    with pytest.raises(ValueError, match="API key is missing"):
        decrypt_api_key("")


def test_decrypt_raises_on_missing_secret_key(monkeypatch):
    """Must raise ValueError when SECRET_KEY is unset."""
    monkeypatch.setenv("SECRET_KEY", "temp-key")
    encrypted = encrypt_api_key("test")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(ValueError, match="SECRET_KEY"):
        decrypt_api_key(encrypted)


def test_decrypt_wrong_key_fails(monkeypatch):
    """Decrypting with a different SECRET_KEY must fail."""
    monkeypatch.setenv("SECRET_KEY", "key-one")
    encrypted = encrypt_api_key("my-secret-api-key")
    monkeypatch.setenv("SECRET_KEY", "key-two")
    with pytest.raises(Exception):
        decrypt_api_key(encrypted)
