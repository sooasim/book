"""Stdlib-only JWT (HS256) auth module for the OneClick eBook Studio API.

Implements compact-serialization JSON Web Tokens signed with HMAC-SHA256.
No third-party dependencies: only hmac, hashlib, base64, json, time, os.
"""

import base64
import hashlib
import hmac
import json
import os
import time

DEFAULT_SECRET = os.environ.get("OCES_SECRET", "dev-secret-change-me")


def b64url_encode(data: bytes) -> str:
    """Base64url-encode bytes without padding, returning an ASCII str."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(data: str) -> bytes:
    """Base64url-decode a (possibly unpadded) ASCII str back to bytes."""
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def _sign(signing_input: bytes, secret: str) -> bytes:
    """Compute the raw HMAC-SHA256 signature over the signing input."""
    return hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()


def make_token(
    user_id: str,
    secret: str = DEFAULT_SECRET,
    exp_seconds: int = 86400,
    now: int | None = None,
) -> str:
    """Create a signed HS256 JWT for the given user id."""
    issued = now if now is not None else int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": user_id, "iat": issued, "exp": issued + exp_seconds}

    header_b64 = b64url_encode(
        json.dumps(header, separators=(",", ":")).encode("utf-8")
    )
    payload_b64 = b64url_encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature_b64 = b64url_encode(_sign(signing_input, secret))

    return f"{header_b64}.{payload_b64}.{signature_b64}"


def verify_token(
    token: str,
    secret: str = DEFAULT_SECRET,
    now: int | None = None,
) -> dict:
    """Verify an HS256 JWT and return its payload dict.

    Raises ValueError on malformed token, bad signature, or expiration.
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("malformed token")
    header_b64, payload_b64, signature_b64 = parts

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected = _sign(signing_input, secret)
    try:
        provided = b64url_decode(signature_b64)
    except Exception:
        raise ValueError("bad signature")
    if not hmac.compare_digest(expected, provided):
        raise ValueError("bad signature")

    try:
        payload = json.loads(b64url_decode(payload_b64).decode("utf-8"))
    except Exception:
        raise ValueError("malformed token")

    current = now if now is not None else int(time.time())
    exp = payload.get("exp")
    if exp is not None and exp < current:
        raise ValueError("expired")

    return payload


def user_from_token(token: str, secret: str = DEFAULT_SECRET) -> str:
    """Return the subject (user id) from a verified token."""
    return verify_token(token, secret)["sub"]


def parse_bearer(authorization_header: str | None) -> str | None:
    """Extract the token from an 'Bearer <token>' header, else None."""
    if not authorization_header:
        return None
    parts = authorization_header.split(" ", 1)
    if len(parts) != 2 or parts[0] != "Bearer":
        return None
    token = parts[1].strip()
    return token or None
