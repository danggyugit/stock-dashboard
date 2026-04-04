"""Authentication module — Google OAuth + JWT.

Handles Google ID token verification, user creation/lookup,
JWT token generation, and request-level user extraction.
"""

import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel

from config import get_settings
from db import get_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# --- JWT helpers ---

def _create_jwt(user_id: int, email: str) -> str:
    """Create a JWT token for the given user."""
    from jose import jwt

    settings = get_settings()
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRE_HOURS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def _decode_jwt(token: str) -> dict:
    """Decode and validate a JWT token."""
    from jose import jwt, JWTError

    settings = get_settings()
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


# --- Dependency: get current user ---

def get_current_user(authorization: str | None = Header(default=None)) -> int:
    """FastAPI dependency to extract user_id from JWT Bearer token.

    Returns:
        user_id (int)

    Raises:
        HTTPException 401 if no token or invalid token.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = authorization.split(" ", 1)[1]
    payload = _decode_jwt(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return int(user_id)


def get_optional_user(authorization: str | None = Header(default=None)) -> int | None:
    """Same as get_current_user but returns None instead of 401."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        token = authorization.split(" ", 1)[1]
        payload = _decode_jwt(token)
        user_id = payload.get("sub")
        return int(user_id) if user_id else None
    except Exception:
        return None


# --- Routes ---

class GoogleAuthRequest(BaseModel):
    """Request body for Google OAuth login."""
    credential: str  # Google ID token (from Google Sign-In)


class AuthResponse(BaseModel):
    """Response with JWT token and user info."""
    token: str
    user: dict


@router.post("/google", response_model=AuthResponse)
def google_login(request: GoogleAuthRequest) -> dict:
    """Exchange Google ID token for a JWT.

    Verifies the Google ID token, creates user if new,
    and returns a JWT for subsequent API calls.
    """
    settings = get_settings()

    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Google OAuth not configured (GOOGLE_CLIENT_ID missing)")

    # Verify Google ID token
    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests

        idinfo = id_token.verify_oauth2_token(
            request.credential,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"Invalid Google token: {e}")

    google_id = idinfo["sub"]
    email = idinfo.get("email", "")
    name = idinfo.get("name", "")
    avatar_url = idinfo.get("picture", "")

    conn = get_connection()

    # Find or create user
    existing = conn.execute(
        "SELECT id, email, name, avatar_url FROM users WHERE google_id = ?",
        [google_id],
    ).fetchone()

    if existing:
        user_id = existing[0]
        # Update name/avatar if changed
        conn.execute(
            "UPDATE users SET name = ?, avatar_url = ? WHERE id = ?",
            [name, avatar_url, user_id],
        )
    else:
        user_id = conn.execute("SELECT nextval('seq_user_id')").fetchone()[0]
        conn.execute(
            """INSERT INTO users (id, google_id, email, name, avatar_url)
               VALUES (?, ?, ?, ?, ?)""",
            [user_id, google_id, email, name, avatar_url],
        )
        logger.info("New user created: %s (%s)", name, email)

        # Assign any orphaned portfolios (no user_id) to this first user
        conn.execute(
            "UPDATE portfolios SET user_id = ? WHERE user_id IS NULL",
            [user_id],
        )

    token = _create_jwt(user_id, email)

    return {
        "token": token,
        "user": {
            "id": user_id,
            "email": email,
            "name": name,
            "avatar_url": avatar_url,
        },
    }


@router.get("/me")
def get_me(user_id: int = Depends(get_current_user)) -> dict:
    """Get current authenticated user info."""
    conn = get_connection()
    row = conn.execute(
        "SELECT id, email, name, avatar_url FROM users WHERE id = ?",
        [user_id],
    ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": row[0],
        "email": row[1],
        "name": row[2],
        "avatar_url": row[3],
    }
