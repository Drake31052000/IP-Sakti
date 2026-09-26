"""
auth.py — authentication, RBAC and registration.

Implements Plan Section 2 Steps 3-4 (credential migration, real session
tokens) and Section 3 Steps 2-4 (server-side permission dependency,
registration, login throttling).
"""
from __future__ import annotations

import time
from typing import Optional

from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel, Field

from database import get_conn, FRONTEND_ROLE_TO_ROLE
from security import (
    hash_password,
    verify_password,
    is_argon2_hash,
    legacy_sha256,
    create_access_token,
    verify_access_token,
)

# --------------------------------------------------------------------------
# Login throttling (Section 3 Step 4) — simple in-memory counter, keyed by
# (login_id). Good enough for a single-process prototype; swap for a shared
# store (Redis) behind a load balancer in production.
# --------------------------------------------------------------------------
_FAILED_ATTEMPTS: dict[str, list[float]] = {}
MAX_ATTEMPTS = 5
WINDOW_SECONDS = 15 * 60


def _too_many_attempts(login_id: str) -> bool:
    now = time.time()
    attempts = [t for t in _FAILED_ATTEMPTS.get(login_id, []) if now - t < WINDOW_SECONDS]
    _FAILED_ATTEMPTS[login_id] = attempts
    return len(attempts) >= MAX_ATTEMPTS


def _record_failed_attempt(login_id: str) -> None:
    _FAILED_ATTEMPTS.setdefault(login_id, []).append(time.time())


def _clear_attempts(login_id: str) -> None:
    _FAILED_ATTEMPTS.pop(login_id, None)


# --------------------------------------------------------------------------
# Login / credential verification with transparent Argon2id migration
# --------------------------------------------------------------------------
class LoginRequest(BaseModel):
    role: str
    id: str
    password: str


def authenticate(payload: LoginRequest) -> dict:
    role = FRONTEND_ROLE_TO_ROLE.get(payload.role.upper())
    if not role:
        raise HTTPException(status_code=400, detail="Unknown profession/role.")

    if _too_many_attempts(payload.id):
        raise HTTPException(
            status_code=429,
            detail={"success": False, "message": "Too many failed attempts. Try again later."},
        )

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM users WHERE login_id = ? AND role = ? AND active = 1",
        (payload.id, role),
    )
    user = cur.fetchone()

    if not user:
        conn.close()
        _record_failed_attempt(payload.id)
        raise HTTPException(
            status_code=401,
            detail={"success": False, "message": "Entered wrong user ID or password."},
        )

    stored_hash = user["password_hash"]
    ok = False
    if is_argon2_hash(stored_hash):
        ok = verify_password(payload.password, stored_hash)
    else:
        # Legacy SHA-256 account (Section 2 Step 3): verify against the old
        # scheme, then transparently re-hash with Argon2id on success.
        ok = legacy_sha256(payload.password) == stored_hash
        if ok:
            cur.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (hash_password(payload.password), user["id"]),
            )
            conn.commit()

    if not ok:
        conn.close()
        _record_failed_attempt(payload.id)
        raise HTTPException(
            status_code=401,
            detail={"success": False, "message": "Entered wrong user ID or password."},
        )

    _clear_attempts(payload.id)
    token = create_access_token(user["id"], user["login_id"], user["role"])
    conn.close()
    return {
        "success": True,
        "name": user["display_name"] or user["login_id"],
        "role": payload.role,
        "access_token": token,
        "token_type": "bearer",
    }


# --------------------------------------------------------------------------
# Bearer-token session dependency (replaces trusting X-User-ID/X-User-Role)
# --------------------------------------------------------------------------
def get_current_user(authorization: Optional[str] = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    token = authorization[len("Bearer "):]
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return payload  # {"uid", "sub", "role", "iat", "exp"}


def require_permission(permission: str):
    """FastAPI dependency factory: require_permission("files:read")."""

    def checker(user: dict = Depends(get_current_user)) -> dict:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM permissions WHERE role = ? AND permission = ?",
            (user["role"], permission),
        )
        allowed = cur.fetchone() is not None
        conn.close()
        if not allowed:
            raise HTTPException(status_code=403, detail="Permission denied")
        return user

    return checker


# --------------------------------------------------------------------------
# Registration (Section 3 Step 3) — real account creation, not a UI stub.
# --------------------------------------------------------------------------
class RegisterRequest(BaseModel):
    login_id: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=128)
    role: str


def register(req: RegisterRequest) -> dict:
    role = FRONTEND_ROLE_TO_ROLE.get(req.role.upper())
    if not role:
        raise HTTPException(status_code=400, detail="Unknown profession/role.")

    # Minimal password policy; extend as needed.
    if req.password.lower() == req.password or req.password.isalpha():
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters and mix letters with numbers/symbols.",
        )

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE login_id = ?", (req.login_id,))
    if cur.fetchone():
        conn.close()
        raise HTTPException(status_code=409, detail="This login ID is already registered.")

    cur.execute(
        "INSERT INTO users (login_id, password_hash, display_name, role, active) VALUES (?, ?, ?, ?, 1)",
        (req.login_id, hash_password(req.password), req.display_name, role),
    )
    conn.commit()
    conn.close()
    return {"success": True}
