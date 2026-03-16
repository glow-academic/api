"""Tests for cache_key — deterministic key generation."""

from app.utils.cache.cache_key import CACHE_KEY_PREFIX, cache_key


def test_returns_prefixed_string():
    key = cache_key("/v5/resources/args/get", {"ids": ["abc"]})

    assert key.startswith(CACHE_KEY_PREFIX)


def test_deterministic_same_inputs():
    key1 = cache_key("/v5/resources/args/get", {"ids": ["abc", "def"]})
    key2 = cache_key("/v5/resources/args/get", {"ids": ["abc", "def"]})

    assert key1 == key2


def test_different_path_different_key():
    key1 = cache_key("/v5/resources/args/get", {"ids": ["abc"]})
    key2 = cache_key("/v5/resources/tools/get", {"ids": ["abc"]})

    assert key1 != key2


def test_different_body_different_key():
    key1 = cache_key("/v5/resources/args/get", {"ids": ["abc"]})
    key2 = cache_key("/v5/resources/args/get", {"ids": ["def"]})

    assert key1 != key2


def test_different_user_ctx_different_key():
    key1 = cache_key("/path", {"ids": ["a"]}, user_ctx="user1")
    key2 = cache_key("/path", {"ids": ["a"]}, user_ctx="user2")

    assert key1 != key2


def test_none_body_same_as_empty():
    key1 = cache_key("/path")
    key2 = cache_key("/path", None)

    assert key1 == key2


def test_none_user_ctx_same_as_default():
    key1 = cache_key("/path", {"ids": ["a"]})
    key2 = cache_key("/path", {"ids": ["a"]}, user_ctx=None)

    assert key1 == key2


def test_key_order_independent():
    key1 = cache_key("/path", {"a": "1", "b": "2"})
    key2 = cache_key("/path", {"b": "2", "a": "1"})

    assert key1 == key2
