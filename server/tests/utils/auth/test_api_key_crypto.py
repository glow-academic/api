"""Tests for API key encryption primitives."""

import pytest

from app.utils.auth.decrypt_api_key import decrypt_api_key
from app.utils.auth.derive_key import KEY_LENGTH, SALT_LENGTH, derive_key
from app.utils.auth.encrypt_api_key import encrypt_api_key


def test_derive_key_is_deterministic_for_same_inputs():
    salt = b"a" * SALT_LENGTH

    first = derive_key("secret", salt)
    second = derive_key("secret", salt)

    assert first == second
    assert len(first) == KEY_LENGTH


def test_encrypt_and_decrypt_round_trip(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "unit-test-secret")

    encrypted = encrypt_api_key("sk-live-example")
    decrypted = decrypt_api_key(encrypted)

    assert encrypted != "sk-live-example"
    assert decrypted == "sk-live-example"


def test_decrypt_rejects_empty_input():
    with pytest.raises(ValueError, match="API key is missing"):
        decrypt_api_key("")


def test_encrypt_requires_secret_key(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(ValueError, match="SECRET_KEY"):
        encrypt_api_key("sk-test")
