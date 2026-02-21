"""
app/auth.py
───────────
JWT-based authentication + role-based access control.

Roles:
  admin    — can upload/delete documents AND ask questions
  employee — can only ask questions

Default users are seeded from environment variables on app startup.
"""

import bcrypt
import jwt
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.database import get_db

# ── HTTP Bearer security scheme ───────────────────────────────────────────────
_bearer = HTTPBearer(auto_error=True)


# ── Password utilities ────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── JWT utilities ─────────────────────────────────────────────────────────────

def create_access_token(username: str, role: str, display_name: str) -> str:
    payload = {
        "sub": username,
        "role": role,
        "display_name": display_name,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc)
        + timedelta(hours=settings.TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please log in again.",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        )


# ── User DB helpers ───────────────────────────────────────────────────────────

def get_user_by_username(username: str) -> dict | None:
    """Return user doc (without _id) or None."""
    return get_db()["users"].find_one({"username": username}, {"_id": 0})


def authenticate_user(username: str, password: str) -> dict:
    """
    Verify credentials. Returns user dict on success.
    Raises 401 on failure (deliberately vague message).
    """
    user = get_user_by_username(username)
    if not user or not verify_password(password, user.get("hashed_password", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
        )
    return user


# ── FastAPI dependency: current user ─────────────────────────────────────────

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    payload = decode_token(credentials.credentials)
    user = get_user_by_username(payload.get("sub", ""))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with token no longer exists.",
        )
    return user


# ── Role guards ───────────────────────────────────────────────────────────────

def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )
    return user


def require_any_role(user: dict = Depends(get_current_user)) -> dict:
    """Any authenticated user (admin or employee)."""
    return user


# ── Default user seeding ──────────────────────────────────────────────────────

def seed_default_users() -> None:
    """
    Called once on startup. Creates initial admin and employee accounts
    if they don't already exist in the `users` collection.
    Credentials come from environment variables (see .env.example).
    """
    users_col = get_db()["users"]

    defaults = [
        {
            "username": settings.ADMIN_USERNAME,
            "password": settings.ADMIN_PASSWORD,
            "role": "admin",
            "display_name": "Administrator",
        },
        {
            "username": settings.EMPLOYEE_USERNAME,
            "password": settings.EMPLOYEE_PASSWORD,
            "role": "employee",
            "display_name": "Employee",
        },
    ]

    for u in defaults:
        if not users_col.find_one({"username": u["username"]}):
            users_col.insert_one(
                {
                    "username": u["username"],
                    "hashed_password": hash_password(u["password"]),
                    "role": u["role"],
                    "display_name": u["display_name"],
                }
            )
            import logging
            logging.getLogger(__name__).info(
                "Seeded default %s user: '%s'", u["role"], u["username"]
            )
