"""
database.py — normalized schema and connection helper.

Implements Plan Section 3 Step 1 ("Move toward users + roles + permissions
instead of seven separate user tables") and Section 4 Step 3 (chunk/metadata
tables), plus the audit_log table from Section 8 Step 3.

The seven legacy per-profession tables (admin, researcher, ip_pro, startup,
govt, citizen, ayush) are replaced by a single `users` table with a `role`
column. Demo credentials are migrated automatically on first run so the
existing demo login IDs / passwords keep working unchanged.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from security import hash_password

BASE_DIR = Path(__file__).resolve().parent.parent  # IP-SAKTI/
DB_PATH = BASE_DIR / "data" / "ip_sakti.db"
UPLOAD_DIR = BASE_DIR / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

ROLES = ["admin", "researcher", "ip_pro", "startup", "govt", "citizen", "ayush"]

# Frontend sends UPPERCASE role keys (see FRONTEND_ROLE_TO_TABLE in the
# original prototype). Keep that contract stable for the existing UI.
FRONTEND_ROLE_TO_ROLE = {
    "ADMIN": "admin",
    "RESEARCHER": "researcher",
    "IP_PRO": "ip_pro",
    "STARTUP": "startup",
    "GOVT": "govt",
    "CITIZEN": "citizen",
    "AYUSH": "ayush",
}

# 5 demo credentials per role, seeded once. Format: (login_id, plain_password, display_name)
DEMO_USERS = {
    "admin": [
        ("king", "king123", "Admin One"),
        ("admin2", "Admin@456", "Admin Two"),
        ("admin3", "Admin@789", "Admin Three"),
        ("admin4", "Admin@111", "Admin Four"),
        ("admin5", "Admin@222", "Admin Five"),
    ],
    "researcher": [
        ("res1", "Res@123", "Researcher One"),
        ("res2", "Res@456", "Researcher Two"),
        ("res3", "Res@789", "Researcher Three"),
        ("res4", "Res@111", "Researcher Four"),
        ("res5", "Res@222", "Researcher Five"),
    ],
    "ip_pro": [
        ("ippro1", "Ippro@123", "IP Professional One"),
        ("ippro2", "Ippro@456", "IP Professional Two"),
        ("ippro3", "Ippro@789", "IP Professional Three"),
        ("ippro4", "Ippro@111", "IP Professional Four"),
        ("ippro5", "Ippro@222", "IP Professional Five"),
    ],
    "startup": [
        ("startup1", "Start@123", "Startup One"),
        ("startup2", "Start@456", "Startup Two"),
        ("startup3", "Start@789", "Startup Three"),
        ("startup4", "Start@111", "Startup Four"),
        ("startup5", "Start@222", "Startup Five"),
    ],
    "govt": [
        ("govt1", "Govt@123", "Govt Official One"),
        ("govt2", "Govt@456", "Govt Official Two"),
        ("govt3", "Govt@789", "Govt Official Three"),
        ("govt4", "Govt@111", "Govt Official Four"),
        ("govt5", "Govt@222", "Govt Official Five"),
    ],
    "citizen": [
        ("citizen1", "Citizen@123", "Citizen One"),
        ("citizen2", "Citizen@456", "Citizen Two"),
        ("citizen3", "Citizen@789", "Citizen Three"),
        ("citizen4", "Citizen@111", "Citizen Four"),
        ("citizen5", "Citizen@222", "Citizen Five"),
    ],
    "ayush": [
        ("ayush1", "Ayush@123", "AYUSH Student One"),
        ("ayush2", "Ayush@456", "AYUSH Student Two"),
        ("ayush3", "Ayush@789", "AYUSH Student Three"),
        ("ayush4", "Ayush@111", "AYUSH Student Four"),
        ("ayush5", "Ayush@222", "AYUSH Student Five"),
    ],
}

# Role -> permission grants (Section 3 Step 2's require_permission()).
DEFAULT_PERMISSIONS = {
    "admin": ["query:ask", "files:read", "files:write", "files:delete", "users:manage", "audit:read"],
    "researcher": ["query:ask"],
    "ip_pro": ["query:ask"],
    "startup": ["query:ask"],
    "govt": ["query:ask"],
    "citizen": ["query:ask"],
    "ayush": ["query:ask"],
}


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            login_id TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL,
            role TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            permission TEXT NOT NULL,
            UNIQUE(role, permission)
        )
        """
    )

    # File records table for Record Management (admin) — now stores a
    # server-generated storage id only; the original filename is metadata.
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            stored_name TEXT NOT NULL,
            uploaded_by TEXT,
            uploaded_at TEXT,
            content_type TEXT,
            extracted_text TEXT,
            authority TEXT,
            jurisdiction TEXT,
            language TEXT DEFAULT 'English',
            source_version TEXT,
            effective_date TEXT
        )
        """
    )

    # Document chunks (Section 4 Step 3).
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS document_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL,
            text TEXT NOT NULL,
            jurisdiction TEXT,
            language TEXT,
            source_version TEXT,
            page_number INTEGER,
            section_title TEXT
        )
        """
    )

    # Audit log (Section 8 Step 3).
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            resource TEXT,
            timestamp TEXT NOT NULL,
            request_id TEXT,
            details TEXT
        )
        """
    )

    # Answer feedback (thumbs up/down on a query response).
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            role TEXT,
            query_text TEXT,
            answer_snippet TEXT,
            rating TEXT NOT NULL,
            language TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )

    conn.commit()
    _seed_permissions(conn)
    _seed_demo_users(conn)
    _migrate_legacy_role_tables(conn)
    conn.close()


def _seed_permissions(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    for role, perms in DEFAULT_PERMISSIONS.items():
        for perm in perms:
            cur.execute(
                "INSERT OR IGNORE INTO permissions (role, permission) VALUES (?, ?)",
                (role, perm),
            )
    conn.commit()


def _seed_demo_users(conn: sqlite3.Connection) -> None:
    """Seed demo accounts once, Argon2id-hashed from the start."""
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM users")
    if cur.fetchone()["c"] > 0:
        return
    for role, users in DEMO_USERS.items():
        for login_id, plain_pw, name in users:
            cur.execute(
                "INSERT INTO users (login_id, password_hash, display_name, role, active) "
                "VALUES (?, ?, ?, ?, 1)",
                (login_id, hash_password(plain_pw), name, role),
            )
    conn.commit()


def _migrate_legacy_role_tables(conn: sqlite3.Connection) -> None:
    """If a pre-upgrade database (7 separate per-role tables, SHA-256
    hashes) is detected, copy its rows into the new `users` table so no
    account is lost. Legacy password hashes are copied as-is; they are
    transparently upgraded to Argon2id the next time each user logs in
    (see auth.authenticate())."""
    cur = conn.cursor()
    for role in ROLES:
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (role,)
        )
        if not cur.fetchone():
            continue
        cur.execute(f"SELECT login_id, password_hash, name FROM {role}")
        for row in cur.fetchall():
            cur.execute("SELECT 1 FROM users WHERE login_id=?", (row["login_id"],))
            if cur.fetchone():
                continue
            cur.execute(
                "INSERT INTO users (login_id, password_hash, display_name, role, active) "
                "VALUES (?, ?, ?, ?, 1)",
                (row["login_id"], row["password_hash"], row["name"] or row["login_id"], role),
            )
    conn.commit()
