"""Encrypted OAuth/marketplace token store (Fernet). Tokens are never logged or returned to clients."""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import OAuthToken

log = logging.getLogger("gigbid.tokens")
_warned = False


def _fernet() -> Fernet:
    global _warned
    key = get_settings().token_enc_key
    if not key:
        if not _warned:
            log.warning("TOKEN_ENC_KEY not set; deriving a development key from JWT_SECRET")
            _warned = True
        digest = hashlib.sha256(("gigbid-token-store:" + get_settings().jwt_secret).encode()).digest()
        key = base64.urlsafe_b64encode(digest).decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str | None:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except (InvalidToken, ValueError):
        return None


def save_token(db: Session, user_id: str, provider: str, access_token: str, refresh_token: str | None = None,
               expires_in: int | None = None, scope: str = "") -> OAuthToken:
    row = db.scalar(select(OAuthToken).where(OAuthToken.user_id == user_id, OAuthToken.provider == provider))
    if row is None:
        row = OAuthToken(user_id=user_id, provider=provider, enc_access_token="")
        db.add(row)
    row.enc_access_token = encrypt(access_token)
    row.enc_refresh_token = encrypt(refresh_token) if refresh_token else None
    row.expires_at = (dt.datetime.utcnow() + dt.timedelta(seconds=expires_in)) if expires_in else None
    row.scope = scope or ""
    db.commit()
    return row


def get_token(db: Session, user_id: str, provider: str) -> str | None:
    row = db.scalar(select(OAuthToken).where(OAuthToken.user_id == user_id, OAuthToken.provider == provider))
    return decrypt(row.enc_access_token) if row else None


def list_providers(db: Session, user_id: str) -> list[OAuthToken]:
    return list(db.scalars(select(OAuthToken).where(OAuthToken.user_id == user_id)))


def delete_token(db: Session, user_id: str, provider: str) -> bool:
    row = db.scalar(select(OAuthToken).where(OAuthToken.user_id == user_id, OAuthToken.provider == provider))
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True
