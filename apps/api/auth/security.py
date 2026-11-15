"""Password hashing, JWT issue/verify, and the current-user dependency (cookie or bearer)."""
from __future__ import annotations

import datetime as dt

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import User, get_db

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:72], hashed.encode())
    except ValueError:
        return False


def create_token(user_id: str) -> str:
    s = get_settings()
    now = dt.datetime.now(dt.timezone.utc)
    payload = {"sub": user_id, "iat": now, "exp": now + dt.timedelta(hours=s.jwt_ttl_hours)}
    return jwt.encode(payload, s.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str) -> str | None:
    try:
        data = jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITHM])
        return data.get("sub")
    except jwt.PyJWTError:
        return None


def token_from_request(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    cookie = request.cookies.get(get_settings().cookie_name)
    if cookie:
        return cookie
    # EventSource cannot set headers; allow ?access_token= for SSE as a last resort.
    return request.query_params.get("access_token")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = token_from_request(request)
    user_id = decode_token(token) if token else None
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown user")
    request.state.user_id = user.id
    return user
