from __future__ import annotations

import threading
from pathlib import Path
from uuid import UUID

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.infra.identity import jwks
from app.infra.identity import resolve_identity


def _priv_pem(private_key) -> bytes:
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def _gen_and_persist(path: Path) -> rsa.RSAPrivateKey:
    """Make a key and write it to ``path`` exactly as the module would."""
    k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    path.write_bytes(_priv_pem(k))
    return k


# ─── FIX 1: atomic IdP key load — in-memory == on-disk, always ─────────────


def test_generate_key_pair_creates_and_persists_when_file_absent(
    monkeypatch, tmp_path
):
    """File absent → a key is generated, persisted, and the returned key
    matches what landed on disk (so a fresh verifier process agrees)."""
    key_path = tmp_path / ".idp-key.pem"
    monkeypatch.setattr(jwks, "_KEY_PATH", key_path)

    private_key, _ = jwks.generate_key_pair()

    assert key_path.exists()
    assert _priv_pem(private_key) == key_path.read_bytes()


def test_generate_key_pair_adopts_existing_on_disk_key(monkeypatch, tmp_path):
    """File present → the on-disk key is loaded and returned (never a fresh
    one), so the in-memory key matches the persisted key."""
    key_path = tmp_path / ".idp-key.pem"
    on_disk = _gen_and_persist(key_path)
    monkeypatch.setattr(jwks, "_KEY_PATH", key_path)

    private_key, _ = jwks.generate_key_pair()

    assert _priv_pem(private_key) == _priv_pem(on_disk)


def test_generate_key_pair_lost_race_returns_on_disk_key_not_candidate(
    monkeypatch, tmp_path
):
    """Simulate "lost the atomic create": the file already holds key K (a
    rival colour won), so generate_key_pair must DISCARD its freshly generated
    candidate and return K. The divergence (returning a different in-memory
    key than the file) is impossible."""
    key_path = tmp_path / ".idp-key.pem"
    monkeypatch.setattr(jwks, "_KEY_PATH", key_path)

    # The "winner" persists K *before* our generate_key_pair adopts it. We make
    # _load_key_from_disk miss on its first probe (mimicking the brief window
    # where exists() raced ahead of a readable file) so the code path goes
    # generate-candidate → O_EXCL fails → adopt-on-disk.
    winner_key = _gen_and_persist(key_path)

    private_key, _ = jwks.generate_key_pair()

    # Returned key is the on-disk key K, never the candidate.
    assert _priv_pem(private_key) == _priv_pem(winner_key)
    # And the file is untouched (we did not overwrite the winner's key).
    assert key_path.read_bytes() == _priv_pem(winner_key)


def test_generate_key_pair_concurrent_callers_converge_to_same_on_disk_key(
    monkeypatch, tmp_path
):
    """The race itself: many callers invoke generate_key_pair concurrently with
    the file absent. Exactly one wins the atomic O_EXCL claim; every caller
    returns the SAME key, equal to the single key persisted on disk."""
    key_path = tmp_path / ".idp-key.pem"
    monkeypatch.setattr(jwks, "_KEY_PATH", key_path)

    results: list[bytes] = []
    lock = threading.Lock()
    barrier = threading.Barrier(8)

    def worker():
        barrier.wait()  # maximise contention on the create
        priv, _ = jwks.generate_key_pair()
        with lock:
            results.append(_priv_pem(priv))

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    on_disk = key_path.read_bytes()
    assert len(results) == 8
    # Every caller agrees with every other caller …
    assert set(results) == {on_disk}
    # … and with the single key persisted on disk.
    assert all(r == on_disk for r in results)


def test_get_jwks_includes_builtin_default_idp_keys_when_remote_jwks_do_not_match(
    monkeypatch,
):
    resolve_identity._jwks_cache.update({"keys": None, "ts": 0.0, "url": None})

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"keys": [{"kid": "remote-key"}]}

    monkeypatch.setattr(resolve_identity, "_can_resolve_hostname", lambda _: True)
    monkeypatch.setattr(
        resolve_identity.requests,
        "get",
        lambda url, timeout: FakeResponse(),
    )
    monkeypatch.setattr(
        "app.infra.identity.jwks.get_jwks",
        lambda: {"keys": [{"kid": "default-idp-key-1"}]},
    )

    keys = resolve_identity._get_jwks()

    assert [key["kid"] for key in keys] == ["remote-key", "default-idp-key-1"]


def test_verify_jwt_accepts_builtin_default_idp_tokens(monkeypatch):
    monkeypatch.setattr(
        resolve_identity.jwt,
        "get_unverified_header",
        lambda token: {"kid": "default-idp-key-1", "alg": "RS256"},
    )
    monkeypatch.setattr(
        resolve_identity,
        "_get_jwks",
        lambda: [{"kid": "default-idp-key-1"}],
    )
    monkeypatch.setattr(
        resolve_identity.jwt,
        "decode",
        lambda token, key, algorithms, options: {
            "iss": resolve_identity._default_idp_base,
            "profile_id": "019ce726-fa14-7f2a-aebb-0067bca4b029",
        },
    )

    claims = resolve_identity.verify_jwt("token-123")

    assert claims["profile_id"] == "019ce726-fa14-7f2a-aebb-0067bca4b029"


# ─── JWKS cache: fetch is paid once, not per request ───────────────────────


def test_get_jwks_caches_within_ttl_so_second_call_does_not_refetch(monkeypatch):
    """A successful fetch populates the cache; a second call inside the TTL
    window must serve from cache and not hit Keycloak again. This is the
    whole point of the cache — without it every request pays the network
    round-trip (now offloaded to a thread, but still wasteful)."""
    resolve_identity._jwks_cache.update({"keys": None, "ts": 0.0, "url": None})

    calls = {"n": 0}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"keys": [{"kid": "remote-key"}]}

    def fake_get(url, timeout):
        calls["n"] += 1
        return FakeResponse()

    monkeypatch.setattr(resolve_identity, "_can_resolve_hostname", lambda _: True)
    monkeypatch.setattr(resolve_identity, "JWKS_URLS", ["http://kc/certs"])
    monkeypatch.setattr(resolve_identity.requests, "get", fake_get)
    monkeypatch.setattr("app.infra.identity.jwks.get_jwks", lambda: {"keys": []})

    first = resolve_identity._get_jwks()
    second = resolve_identity._get_jwks()

    assert [k["kid"] for k in first] == ["remote-key"]
    assert [k["kid"] for k in second] == ["remote-key"]
    # The network fetch happened exactly once across both resolves.
    assert calls["n"] == 1


def test_get_jwks_fallback_refreshes_timestamp_to_avoid_per_request_refetch(
    monkeypatch,
):
    """When the refresh fails but cached keys exist, the fallback path must
    bump the cache timestamp. Otherwise the stale `ts` keeps the cache
    "expired" and a slow/down Keycloak gets re-hit on *every* request. With
    the fix, the failing fetch is attempted at most once per TTL window."""
    # Controllable clock — hold time still so both calls land in one TTL window.
    monkeypatch.setattr(resolve_identity.time, "time", lambda: 10_000.0)

    # Prime the cache with keys but an old timestamp so the first call is
    # past the TTL and tries to refresh.
    resolve_identity._jwks_cache.update(
        {"keys": [{"kid": "cached-key"}], "ts": 0.0, "url": None}
    )

    calls = {"n": 0}

    def failing_get(url, timeout):
        calls["n"] += 1
        raise RuntimeError("Keycloak is slow/down")

    monkeypatch.setattr(resolve_identity, "_can_resolve_hostname", lambda _: True)
    monkeypatch.setattr(resolve_identity, "JWKS_URLS", ["http://kc/certs"])
    monkeypatch.setattr(resolve_identity.requests, "get", failing_get)
    monkeypatch.setattr("app.infra.identity.jwks.get_jwks", lambda: {"keys": []})

    first = resolve_identity._get_jwks()
    second = resolve_identity._get_jwks()

    # Both calls return the cached keys despite the failing remote.
    assert [k["kid"] for k in first] == ["cached-key"]
    assert [k["kid"] for k in second] == ["cached-key"]
    # The blocking fetch was attempted only once: the fallback bumped `ts`, so
    # the second call (same TTL window) is a cache hit. Pre-fix this was 2.
    assert calls["n"] == 1


# ─── resolve_identity does not block the event loop on the KC fetch ────────


@pytest.mark.asyncio
async def test_resolve_identity_runs_verify_jwt_off_the_event_loop(monkeypatch):
    """`verify_jwt` (which may do a blocking `requests.get` to Keycloak via
    `_get_jwks`) must be offloaded to a worker thread inside the async
    `resolve_identity`, so a slow Keycloak can't freeze the asyncio event
    loop. We assert by capturing the thread `verify_jwt` runs on: with the
    fix it runs on a *different* thread than the event loop; an inline call
    would run on the loop's own thread."""
    loop_thread_id = threading.get_ident()
    seen = {"verify_thread": None}

    def fake_verify_jwt(token):
        seen["verify_thread"] = threading.get_ident()
        return {"profile_id": "019b3be4-36f0-788c-9df2-481eb5917940"}

    async def fake_resolve_profile_id(claims, pool):
        return UUID("019b3be4-36f0-788c-9df2-481eb5917940")

    async def fake_emulation_chain(pool, profile_id):
        return []

    async def fake_get_or_create_session(conn, profile_id):
        return UUID("019b3be4-36f0-788c-9df2-481eb5917941")

    class _FakeAcquire:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *a):
            return False

    class FakePool:
        def acquire(self):
            return _FakeAcquire()

    monkeypatch.setattr(resolve_identity, "verify_jwt", fake_verify_jwt)
    monkeypatch.setattr(resolve_identity, "_resolve_profile_id", fake_resolve_profile_id)
    monkeypatch.setattr(
        resolve_identity, "resolve_emulation_chain", fake_emulation_chain
    )
    monkeypatch.setattr(
        resolve_identity, "get_or_create_session", fake_get_or_create_session
    )

    identity = await resolve_identity.resolve_identity("token-123", FakePool())

    assert str(identity.profile_id) == "019b3be4-36f0-788c-9df2-481eb5917940"
    # verify_jwt ran, and on a worker thread — not the event loop's thread.
    assert seen["verify_thread"] is not None
    assert seen["verify_thread"] != loop_thread_id
