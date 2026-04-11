import hashlib
import os
from functools import wraps
from flask import session, jsonify


# ── Simple in-memory user store (swap for DB in production) ──────────────────
#
# Format: { username: hashed_password }
# Seeded with a default admin for development.
#
# To hash a password manually:
#   python -c "import hashlib; print(hashlib.sha256(b'yourpassword').hexdigest())"

_USERS: dict[str, str] = {}


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def seed_admin(username: str = "admin", password: str = "admin123"):
    """
    Seeds a default admin account.
    Call this once at app startup (only if no users exist).
    """
    if not _USERS:
        _USERS[username] = _hash_password(password)


def register_user(db_path: str, username: str, password: str) -> tuple[bool, str]:
    """Returns False if username already taken."""
    if username in _USERS:
        return False, "Username already exists"
    _USERS[username] = _hash_password(password)
    return True, ""


def authenticate_user(username: str, password: str) -> bool:
    stored = _USERS.get(username)
    if not stored:
        return False
    return stored == _hash_password(password)


# ── Decorators ────────────────────────────────────────────────────────────────

def login_required(f):
    """
    Route decorator — returns 401 JSON for API routes if not authenticated.
    """
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
    """
    Route decorator — redirects to /login for browser routes if not authenticated.
    """
    from flask import redirect, url_for
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated
