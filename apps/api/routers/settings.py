"""Settings: autonomy, budgets, rates, filters, saved searches, connected accounts, memory viewer."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth.security import get_current_user
from ..auth.token_store import delete_token, list_providers
from ..db import SavedSearch, User, get_db
from ..deps import user_settings
from ..graphs import runtime
from ..schemas import (ConnectedAccount, MemoryDeleteIn, MemoryItemOut, MemoryOut, OkOut, SavedSearchIn,
                       SavedSearchOut, SettingsIn, SettingsOut)
from ..services.memory import delete_memory, list_memory

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _ss_out(s: SavedSearch) -> SavedSearchOut:
    return SavedSearchOut(id=s.id, name=s.name, query=s.query, category=s.category, skills=s.skills or [],
                          interval_minutes=s.interval_minutes, enabled=s.enabled, last_run_at=s.last_run_at)


def _settings_out(db: Session, user: User) -> SettingsOut:
    searches = db.scalars(select(SavedSearch).where(SavedSearch.user_id == user.id).order_by(SavedSearch.id))
    accounts = [ConnectedAccount(provider=t.provider, connected=True, scope=t.scope or "", expires_at=t.expires_at)
                for t in list_providers(db, user.id)]
    for p in ("gigsim", "upwork"):
        if not any(a.provider == p for a in accounts):
            accounts.append(ConnectedAccount(provider=p, connected=False))
    return SettingsOut(persona=user.persona, settings=user_settings(user),
                       saved_searches=[_ss_out(s) for s in searches], accounts=accounts)


@router.get("", response_model=SettingsOut)
def get_settings_(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _settings_out(db, user)


@router.put("", response_model=SettingsOut)
def put_settings(body: SettingsIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    st = user_settings(user)
    for field in ("autonomy", "rates", "filters", "budgets", "marketplace_mode"):
        v = getattr(body, field)
        if v is not None:
            setattr(st, field, v)
    if body.persona:
        user.persona = body.persona
    user.settings = st.model_dump()
    db.commit()
    return _settings_out(db, user)


@router.get("/searches", response_model=list[SavedSearchOut])
def list_searches(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [_ss_out(s) for s in db.scalars(select(SavedSearch).where(SavedSearch.user_id == user.id))]


@router.post("/searches", response_model=SavedSearchOut, status_code=201)
def create_search(body: SavedSearchIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = SavedSearch(user_id=user.id, **body.model_dump())
    db.add(s)
    db.commit()
    return _ss_out(s)


def _own_search(db: Session, user: User, sid: int) -> SavedSearch:
    s = db.get(SavedSearch, sid)
    if s is None or s.user_id != user.id:
        raise HTTPException(404, "Saved search not found")
    return s


@router.put("/searches/{sid}", response_model=SavedSearchOut)
def update_search(sid: int, body: SavedSearchIn, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    s = _own_search(db, user, sid)
    for k, v in body.model_dump().items():
        setattr(s, k, v)
    db.commit()
    return _ss_out(s)


@router.delete("/searches/{sid}", response_model=OkOut)
def delete_search(sid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.delete(_own_search(db, user, sid))
    db.commit()
    return OkOut(detail="deleted")


@router.delete("/accounts/{provider}", response_model=OkOut)
def disconnect(provider: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not delete_token(db, user.id, provider):
        raise HTTPException(404, "Account not connected")
    return OkOut(detail="disconnected")


@router.get("/memory", response_model=MemoryOut)
async def memory(user: User = Depends(get_current_user)):
    items = await list_memory(runtime.store, user.id)
    return MemoryOut(items=[MemoryItemOut(**i) for i in items], available=runtime.store is not None)


@router.delete("/memory", response_model=OkOut)
async def memory_delete(body: MemoryDeleteIn, user: User = Depends(get_current_user)):
    if not await delete_memory(runtime.store, user.id, body.namespace, body.key):
        raise HTTPException(404, "Memory item not found")
    return OkOut(detail="deleted")
