"""Register/login/logout/me plus onboarding (persona, rates, filters, budget, marketplace, portfolio)."""
from __future__ import annotations

import os
import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth.security import create_token, get_current_user, hash_password, verify_password
from ..auth.token_store import save_token
from ..config import ROOT, get_settings
from ..db import User, get_db
from ..deps import user_out, user_settings
from ..integrations import optional
from ..schemas import (AuthOut, LoginIn, MarketplaceConnectIn, MarketplaceConnectOut, OkOut, OnboardingIn,
                       PortfolioUploadOut, RegisterIn, UserOut)
from ..services import marketplace

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_cookie(response: Response, token: str) -> None:
    s = get_settings()
    response.set_cookie(s.cookie_name, token, httponly=True, secure=s.cookie_secure, samesite="lax",
                        max_age=s.jwt_ttl_hours * 3600, path="/")


@router.post("/register", response_model=AuthOut, status_code=201)
def register(body: RegisterIn, response: Response, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = User(email=email, password_hash=hash_password(body.password), name=body.name, settings={})
    db.add(user)
    db.commit()
    token = create_token(user.id)
    _set_cookie(response, token)
    return AuthOut(user=user_out(user), access_token=token)


@router.post("/login", response_model=AuthOut)
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    token = create_token(user.id)
    _set_cookie(response, token)
    return AuthOut(user=user_out(user), access_token=token)


@router.post("/logout", response_model=OkOut)
def logout(response: Response):
    response.delete_cookie(get_settings().cookie_name, path="/")
    return OkOut()


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user_out(user)


@router.put("/onboarding", response_model=UserOut)
def onboarding(body: OnboardingIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    st = user_settings(user)
    if body.rates:
        st.rates = body.rates
    if body.filters:
        st.filters = body.filters
    if body.budgets:
        st.budgets = body.budgets
    if body.autonomy:
        st.autonomy = body.autonomy
    user.persona = body.persona
    user.settings = st.model_dump()
    user.onboarded = True
    db.commit()
    return user_out(user)


@router.post("/marketplace", response_model=MarketplaceConnectOut)
async def connect_marketplace(body: MarketplaceConnectIn, user: User = Depends(get_current_user),
                              db: Session = Depends(get_db)):
    st = user_settings(user)
    if body.mode == "upwork":
        from .oauth import begin_upwork
        res = await begin_upwork(db, user)
        return MarketplaceConnectOut(mode="upwork", connected=False, detail=res.detail,
                                     authorize_url=res.authorize_url)
    token = body.token or marketplace.default_token(user.persona)
    save_token(db, user.id, "gigsim", token, scope="gigsim")
    st.marketplace_mode = "gigsim"
    user.settings = st.model_dump()
    db.commit()
    ok = True
    detail = ""
    try:
        await marketplace.get_connects(token)
    except marketplace.MarketplaceUnavailable as e:
        ok, detail = False, f"saved; marketplace unreachable ({e})"
    return MarketplaceConnectOut(mode="gigsim", connected=ok, detail=detail)


_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


@router.post("/portfolio", response_model=PortfolioUploadOut)
async def upload_portfolio(file: UploadFile = File(...), user: User = Depends(get_current_user)):
    raw = await file.read()
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(413, "File too large (10 MB max)")
    name = _SAFE.sub("_", Path(file.filename or "upload.md").name)[:120]
    if not name.lower().endswith((".md", ".txt", ".pdf", ".json")):
        raise HTTPException(415, "Upload .md, .txt, .pdf or .json")
    dest = Path(os.getenv("UPLOAD_DIR") or (ROOT / "data" / "uploads")) / user.id
    try:
        dest.mkdir(parents=True, exist_ok=True)
        (dest / name).write_bytes(raw)
    except OSError as exc:
        raise HTTPException(507, f"Could not store the upload: {exc.strerror}") from exc
    text = ""
    if name.lower().endswith(".pdf"):
        try:
            import io
            from pypdf import PdfReader
            text = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(raw)).pages)
        except Exception:
            text = ""
    else:
        text = raw.decode("utf-8", errors="ignore")
    get_retriever = optional("rag.retriever", "get_retriever")
    if get_retriever is None:
        return PortfolioUploadOut(filename=name, bytes=len(raw), indexed=False,
                                  detail="stored; retrieval index unavailable")
    try:
        r = get_retriever(user.persona or "aiml")
        if not text.strip():
            return PortfolioUploadOut(filename=name, bytes=len(raw), indexed=False,
                                      detail="stored; no extractable text (scanned PDF?)")
        info = r.add_document(text=text, item_id=f"upload-{user.id[:8]}-{Path(name).stem}"[:64], type="upload",
                              source=name, user_id=user.id)
        detail = "" if info.get("persisted", True) else "indexed for this server instance (index storage is read-only here)"
        return PortfolioUploadOut(filename=name, bytes=len(raw), indexed=True, detail=detail)
    except Exception as exc:  # noqa: BLE001
        return PortfolioUploadOut(filename=name, bytes=len(raw), indexed=False, detail=f"stored; indexing failed: {exc}"[:300])
