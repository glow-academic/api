"""Tests for app.utils.auth.encrypt_api_key."""

import base64

import pytest

from app.utils.auth.derive_key import IV_LENGTH, SALT_LENGTH
from app.utils.auth.encrypt_api_key import encrypt_api_key


def test_encrypt_returns_valid_base64(monkeypatch):
    """Encrypted output must be decodable base64."""
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-123")
    result = encrypt_api_key("sk-abc123")
    decoded = base64.b64decode(result)
    # salt + iv + at least one AES block (16 bytes)
    assert len(decoded) >= SALT_LENGTH + IV_LENGTH + 16


def test_encrypt_different_calls_produce_different_ciphertexts(monkeypatch):
    """Each call uses random salt/IV, so same plaintext yields different ciphertext."""
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-123")
    c1 = encrypt_api_key("same-key")
    c2 = encrypt_api_key("same-key")
    assert c1 != c2


def test_encrypt_raises_without_secret_key(monkeypatch):
    """Must raise ValueError when SECRET_KEY is unset."""
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(ValueError, match="SECRET_KEY"):
        encrypt_api_key("sk-test")


def test_encrypt_handles_empty_string(monkeypatch):
    """Encrypting an empty string should still produce valid base64 output."""
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-123")
    result = encrypt_api_key("")
    decoded = base64.b64decode(result)
    assert len(decoded) >= SALT_LENGTH + IV_LENGTH + 16


def test_encrypt_handles_unicode_key(monkeypatch):
    """Encrypting a unicode string should succeed."""
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-123")
    result = encrypt_api_key("sk-\u00e9\u00e0\u00fc\u4e16\u754c")
    decoded = base64.b64decode(result)
    assert len(decoded) >= SALT_LENGTH + IV_LENGTH + 16
