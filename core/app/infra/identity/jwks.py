"""JWKS key management for default-idp OIDC provider."""

from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwk

# Global key pair cache
_key_pair: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey] | None = None


def generate_key_pair() -> tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
    """Generate a new RSA-2048 key pair.

    Returns:
        Tuple of (private_key, public_key)
    """
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    public_key = private_key.public_key()
    return private_key, public_key


def get_or_create_key_pair() -> tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
    """Get existing key pair or create a new one.

    In production, keys should be persisted and loaded from secure storage.
    For now, we generate on first use and cache in memory.

    Returns:
        Tuple of (private_key, public_key)
    """
    global _key_pair

    if _key_pair is None:
        _key_pair = generate_key_pair()

    return _key_pair


def get_private_key() -> rsa.RSAPrivateKey:
    """Get the private key for signing tokens.

    Returns:
        RSA private key
    """
    private_key, _ = get_or_create_key_pair()
    return private_key


def get_public_key() -> rsa.RSAPublicKey:
    """Get the public key for token verification.

    Returns:
        RSA public key
    """
    _, public_key = get_or_create_key_pair()
    return public_key


def get_jwks() -> dict[str, Any]:
    """Get JWKS (JSON Web Key Set) for public key exposure.

    Returns:
        JWKS dictionary with public key in JWK format
    """
    public_key = get_public_key()

    # Serialize public key to PEM format
    pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    # Convert to JWK format using jose library
    jwk_dict = jwk.construct(pem, algorithm="RS256")

    # Get the JWK representation
    public_jwk = jwk_dict.to_dict()

    # Add kid (key ID) - use a stable identifier
    # In production, this should be based on key rotation policy
    public_jwk["kid"] = "default-idp-key-1"
    public_jwk["use"] = "sig"
    public_jwk["alg"] = "RS256"

    return {"keys": [public_jwk]}


def get_key_id() -> str:
    """Get the key ID for token signing.

    Returns:
        Key ID string
    """
    return "default-idp-key-1"
