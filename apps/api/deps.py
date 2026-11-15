"""Shared helpers for routers."""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from .auth.token_store import get_token
from .db import User
from .schemas import UserOut, UserSettings
from .services import marketplace


def user_settings(user: User) -> UserSettings:
    try:
        return UserSettings.model_validate(user.settings or {})
    except Exception:
        return UserSettings()


def user_out(user: User) -> UserOut:
    return UserOut(id=user.id, email=user.email, name=user.name or "", persona=user.persona,
                   onboarded=bool(user.onboarded), settings=user_settings(user))


def marketplace_token(db: Session, user: User) -> str:
    return get_token(db, user.id, "gigsim") or marketplace.default_token(user.persona)


def trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", "") or ""
