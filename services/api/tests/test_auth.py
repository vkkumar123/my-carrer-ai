"""Supabase tokens signed with asymmetric keys (ES256) are verified via the project's JWKS."""

from datetime import UTC, datetime, timedelta

import jwt
from cryptography.hazmat.primitives.asymmetric import ec

from app import auth
from app.config import get_settings


def _token(key, **overrides) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": "7f1c6a52-2b8e-4f55-9d6e-0a1b2c3d4e5f",
        "email": "vivek@example.com",
        "aud": "authenticated",
        "iat": now,
        "exp": now + timedelta(hours=1),
        "user_metadata": {"full_name": "Vivek Kumar"},
    } | overrides
    return jwt.encode(claims, key, algorithm="ES256", headers={"kid": "k1"})


class _FakeJWKS:
    def __init__(self, public_key):
        self.public_key = public_key

    def get_signing_key_from_jwt(self, token):
        return type("K", (), {"key": self.public_key})()


def _me(client, token):
    return client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})


def test_supabase_es256_token_creates_user(client, monkeypatch):
    private = ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setattr(get_settings(), "supabase_url", "https://example.supabase.co")
    monkeypatch.setattr(auth, "_jwks", lambda: _FakeJWKS(private.public_key()))

    r = _me(client, _token(private))
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Vivek Kumar"

    other = ec.generate_private_key(ec.SECP256R1())
    assert _me(client, _token(other)).status_code == 401
    expired = _token(private, exp=datetime.now(UTC) - timedelta(minutes=1))
    assert _me(client, expired).status_code == 401


def test_asymmetric_token_rejected_without_supabase_url(client):
    private = ec.generate_private_key(ec.SECP256R1())
    assert _me(client, _token(private)).status_code == 401
