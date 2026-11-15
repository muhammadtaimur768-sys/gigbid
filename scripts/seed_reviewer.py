"""Create (or reset the password of) the reviewer account: reviewer@gigbid.app, persona aiml.
Password from env REVIEWER_PASSWORD (default review-gigbid-2026). The API also seeds it at startup."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from apps.api.auth.security import hash_password  # noqa: E402
from apps.api.config import get_settings  # noqa: E402
from apps.api.db import SavedSearch, SessionLocal, User, init_db  # noqa: E402


def main() -> None:
    s = get_settings()
    init_db()
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == s.reviewer_email))
        if user is None:
            user = User(email=s.reviewer_email, name="Reviewer", password_hash="")
            db.add(user)
        user.password_hash = hash_password(s.reviewer_password)
        user.persona, user.onboarded = "aiml", True
        user.settings = {"autonomy": "manual", "marketplace_mode": "gigsim",
                         **{k: v for k, v in (user.settings or {}).items() if k not in ("autonomy",)}}
        db.commit()
        if not db.scalar(select(SavedSearch).where(SavedSearch.user_id == user.id)):
            db.add(SavedSearch(user_id=user.id, name="LLM / RAG work", query="", category=None,
                               skills=["python", "llm"], interval_minutes=30))
            db.commit()
        print(f"reviewer ready: {s.reviewer_email} (persona aiml)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
