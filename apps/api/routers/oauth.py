"""Upwork OAuth (authorization code + PKCE) discovered from the Upwork MCP server's OAuth metadata."""
from __future__ import annotations

import base64
import hashlib
import secrets
from urllib.parse import urlencode, urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..auth.security import get_current_user
from ..auth.token_store import decrypt, encrypt, save_token
from ..config import get_settings
from ..db import OAuthState, User, get_db
from ..schemas import OAuthStartOut

router = APIRouter(prefix="/api/oauth", tags=["oauth"])


async def discover_metadata() -> dict:
    """RFC 9728 protected-resource metadata -> RFC 8414 authorization-server metadata."""
    s = get_settings()
    async with httpx.AsyncClient(timeout=8.0) as c:
        if s.upwork_metadata_url:
            r = await c.get(s.upwork_metadata_url)
            r.raise_for_status()
            meta = r.json()
            if "authorization_endpoint" in meta:
                return meta
            servers = meta.get("authorization_servers") or []
        else:
            u = urlparse(s.upwork_mcp_url)
            base = f"{u.scheme}://{u.netloc}"
            servers = []
            try:
                r = await c.get(f"{base}/.well-known/oauth-protected-resource{u.path}")
                if r.status_code != 200:
                    r = await c.get(f"{base}/.well-known/oauth-protected-resource")
                if r.status_code == 200:
                    servers = r.json().get("authorization_servers") or []
            except httpx.HTTPError:
                servers = []
            if not servers:
                servers = [base]
        issuer = servers[0].rstrip("/")
        for path in ("/.well-known/oauth-authorization-server", "/.well-known/openid-configuration"):
            r = await c.get(issuer + path)
            if r.status_code == 200:
                return r.json()
    raise HTTPException(502, "Could not discover Upwork OAuth metadata")


def _redirect_uri() -> str:
    return get_settings().public_base_url.rstrip("/") + "/api/oauth/upwork/callback"


async def begin_upwork(db: Session, user: User) -> OAuthStartOut:
    s = get_settings()
    if not s.upwork_client_id:
        return OAuthStartOut(configured=False, detail="Upwork OAuth not configured (UPWORK_CLIENT_ID missing)")
    meta = await discover_metadata()
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(24)
    db.add(OAuthState(state=state, user_id=user.id, provider="upwork", enc_code_verifier=encrypt(verifier),
                      token_endpoint=meta["token_endpoint"], redirect_uri=_redirect_uri()))
    db.commit()
    params = {"response_type": "code", "client_id": s.upwork_client_id, "redirect_uri": _redirect_uri(),
              "state": state, "code_challenge": challenge, "code_challenge_method": "S256",
              "resource": s.upwork_mcp_url}
    return OAuthStartOut(configured=True, authorize_url=f"{meta['authorization_endpoint']}?{urlencode(params)}")


@router.get("/upwork/start", response_model=OAuthStartOut)
async def upwork_start(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return await begin_upwork(db, user)


@router.get("/upwork/callback")
async def upwork_callback(code: str = "", state: str = "", error: str = "", db: Session = Depends(get_db)):
    s = get_settings()
    web = s.web_base_url.rstrip("/") or ""
    if error:
        return RedirectResponse(f"{web}/settings?oauth=error&detail={error[:60]}")
    row = db.get(OAuthState, state)
    if row is None or not code:
        raise HTTPException(400, "Invalid OAuth state")
    verifier = decrypt(row.enc_code_verifier) or ""
    data = {"grant_type": "authorization_code", "code": code, "redirect_uri": row.redirect_uri,
            "client_id": s.upwork_client_id, "code_verifier": verifier}
    if s.upwork_client_secret:
        data["client_secret"] = s.upwork_client_secret
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.post(row.token_endpoint, data=data, headers={"Accept": "application/json"})
    if r.status_code >= 400:
        db.delete(row)
        db.commit()
        return RedirectResponse(f"{web}/settings?oauth=error&detail=token_exchange_{r.status_code}")
    tok = r.json()
    save_token(db, row.user_id, "upwork", tok["access_token"], tok.get("refresh_token"),
               tok.get("expires_in"), tok.get("scope", ""))
    try:  # mirror into the Upwork MCP adapter's encrypted store so the live adapter can use it
        from mcp_servers.marketplace.adapters.token_store import EncryptedTokenStore
        EncryptedTokenStore().put(row.user_id, "tokens", {k: tok.get(k) for k in
                                  ("access_token", "refresh_token", "expires_in", "scope", "token_type")})
    except Exception:
        pass
    db.delete(row)
    db.commit()
    return RedirectResponse(f"{web}/settings?oauth=connected")
