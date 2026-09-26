"""
security.py — password hashing and session tokens.

Implements Plan Section 2 (Authentication and Password Security Upgrade):
  * Argon2id password hashing (replacing the prototype's SHA-256).
  * Transparent migration: a user who still has a legacy SHA-256 hash is
    re-hashed with Argon2id the moment they successfully log in.
  * Signed, short-lived, server-verified session tokens (Bearer tokens),
    replacing the old client-supplied X-User-ID / X-User-Role headers.

No third-party JWT library is required: tokens are a small HMAC-SHA256
signed payload (subject, role, expiry) so the backend stays dependency-light
per the plan's "do not rewrite everything at once" rule.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHash

# --------------------------------------------------------------------------
# Password hashing (Argon2id)
# --------------------------------------------------------------------------
_pwd_hasher = PasswordHasher()  # Argon2id by default in argon2-cffi >= 20.1


def hash_password(password: str) -> str:
    """Hash a plaintext password with Argon2id."""
    return _pwd_hasher.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a plaintext password against an Argon2id hash."""
    try:
        return _pwd_hasher.verify(stored_hash, password)
    except (VerifyMismatchError, InvalidHash):
        return False


def is_argon2_hash(value: str) -> bool:
    return isinstance(value, str) and value.startswith("$argon2")


def legacy_sha256(password: str) -> str:
    """Reproduces the OLD prototype hashing scheme, used only to detect and
    migrate pre-existing accounts. Never used to store NEW passwords."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Signed session tokens
# --------------------------------------------------------------------------
# SESSION_SECRET must come from the environment in production (see .env /
# Section 8 Step 5: "move secrets to environment variables"). A random
# fallback is generated at process start so the prototype still runs
# out-of-the-box, but every restart then invalidates old sessions — that is
# intentional: it stops anyone from assuming a default/dev secret is stable.
SESSION_SECRET = os.environ.get("IP_SAKTI_SECRET") or base64.urlsafe_b64encode(os.urandom(32)).decode()
TOKEN_TTL_SECONDS = int(os.environ.get("IP_SAKTI_TOKEN_TTL", str(60 * 60 * 8)))  # 8h default


def _sign(payload_b64: str) -> str:
    sig = hmac.new(SESSION_SECRET.encode(), payload_b64.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).decode().rstrip("=")


def create_access_token(user_id: int, login_id: str, role: str, ttl: Optional[int] = None) -> str:
    payload = {
        "uid": user_id,
        "sub": login_id,
        "role": role,
        "iat": int(time.time()),
        "exp": int(time.time()) + (ttl or TOKEN_TTL_SECONDS),
    }
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = _sign(payload_b64)
    return f"{payload_b64}.{signature}"


def verify_access_token(token: str) -> Optional[dict]:
    """Returns the decoded payload if the token is well-formed, correctly
    signed and not expired; otherwise None. Never trusts anything in the
    token without checking the signature first (constant-time compare)."""
    if not token or "." not in token:
        return None
    payload_b64, _, signature = token.partition(".")
    expected_sig = _sign(payload_b64)
    if not hmac.compare_digest(signature, expected_sig):
        return None
    try:
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()))
    except Exception:
        return None
    if payload.get("exp", 0) < time.time():
        return None
    return payload
