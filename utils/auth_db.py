"""
auth_db.py — local SQLite store for verifier users.

Why SQLite and not the chain?
  Passwords (even hashed) don't belong on a public append-only ledger
  that every peer can read. Auth is node-local by design.

Schema:
  users(id, username UNIQUE, password_hash, created_at)
"""

import sqlite3
import hashlib
import time
import os
from functools import wraps
from flask import session, jsonify


# ── DB init ───────────────────────────────────────────────────────────────────

def get_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str):
    """Create tables if they don't exist."""
    with get_db(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT    NOT NULL UNIQUE,
                password_hash TEXT    NOT NULL,
                created_at    REAL    NOT NULL
            )
        """)
        conn.commit()


# ── password helpers ──────────────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    # pbkdf2 with a fixed pepper + per-row salt would be better in prod,
    # but sha256 is fine for a dev/demo system.
    return hashlib.sha256(password.encode()).hexdigest()


# ── user management ───────────────────────────────────────────────────────────

def seed_admin(db_path: str, username: str = "admin", password: str = "admin123"):
    """Insert default admin if no users exist yet."""
    with get_db(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count == 0:
            conn.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?,?,?)",
                (username, _hash_password(password), time.time()),
            )
            conn.commit()


def register_user(db_path: str, username: str, password: str) -> tuple[bool, str]:
    """
    Returns (True, "") on success.
    Returns (False, reason) on failure.
    """
    if not username or not password:
        return False, "Username and password are required"
    try:
        with get_db(db_path) as conn:
            conn.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?,?,?)",
                (username, _hash_password(password), time.time()),
            )
            conn.commit()
        return True, ""
    except sqlite3.IntegrityError:
        return False, "Username already exists"


def authenticate_user(db_path: str, username: str, password: str) -> bool:
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE username = ?", (username,)
        ).fetchone()
    if not row:
        return False
    return row["password_hash"] == _hash_password(password)


def list_users(db_path: str) -> list[dict]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT id, username, created_at FROM users ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]


def delete_user(db_path: str, username: str) -> bool:
    with get_db(db_path) as conn:
        cur = conn.execute("DELETE FROM users WHERE username = ?", (username,))
        conn.commit()
    return cur.rowcount > 0


# ── Flask decorators ──────────────────────────────────────────────────────────

def login_required(f):
    """Returns 401 JSON if session not authenticated."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return jsonify({
                "error": "Authentication required",
                "code":  "UNAUTHORIZED"
            }), 401
        return f(*args, **kwargs)
    return decorated


def login_required_redirect(f):
    """Redirects to /login if session not authenticated."""
    from flask import redirect, url_for
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("verifier.login"))
        return f(*args, **kwargs)
    return decorated
