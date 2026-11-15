"""SQLAlchemy storage for GigSim. All tables are prefixed ``gs_``."""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

import sqlalchemy as sa
import yaml

PKG = Path(__file__).resolve().parent
ROOT = PKG.parent
SEED_DIR = PKG / "seed_data"

metadata = sa.MetaData()

gs_state = sa.Table("gs_state", metadata, sa.Column("key", sa.String(64), primary_key=True), sa.Column("value", sa.Text))
gs_clients = sa.Table("gs_clients", metadata, sa.Column("id", sa.String(32), primary_key=True), sa.Column("data", sa.JSON),
                      sa.Column("hidden", sa.JSON))
gs_jobs = sa.Table(
    "gs_jobs", metadata,
    sa.Column("id", sa.String(32), primary_key=True),
    sa.Column("pool", sa.String(16), index=True),      # historical | stream | dev
    sa.Column("status", sa.String(16), index=True),    # closed | pending | open
    sa.Column("release_order", sa.Integer, index=True),
    sa.Column("category", sa.String(64), index=True),
    sa.Column("posted_at", sa.String(32)),
    sa.Column("data", sa.JSON),
    sa.Column("hidden", sa.JSON),
)
gs_freelancers = sa.Table("gs_freelancers", metadata, sa.Column("id", sa.String(32), primary_key=True), sa.Column("persona", sa.String(16)),
                          sa.Column("name", sa.String(128)), sa.Column("balance", sa.Integer), sa.Column("weekly_spent", sa.Integer))
gs_proposals = sa.Table(
    "gs_proposals", metadata,
    sa.Column("proposal_id", sa.String(48), primary_key=True),
    sa.Column("freelancer_id", sa.String(32), index=True),
    sa.Column("job_id", sa.String(32), index=True),
    sa.Column("status", sa.String(16)),
    sa.Column("cover_letter", sa.Text),
    sa.Column("screening_answers", sa.JSON),
    sa.Column("bid_amount", sa.Float),
    sa.Column("connects_spent", sa.Integer),
    sa.Column("created_at", sa.String(32)),
    sa.Column("updated_at", sa.String(32)),
    sa.Column("decision", sa.JSON),
)
gs_threads = sa.Table(
    "gs_threads", metadata,
    sa.Column("thread_id", sa.String(48), primary_key=True),
    sa.Column("freelancer_id", sa.String(32), index=True),
    sa.Column("job_id", sa.String(32)),
    sa.Column("client_id", sa.String(32)),
    sa.Column("proposal_id", sa.String(48)),
    sa.Column("last_message_at", sa.String(32)),
    sa.Column("unread", sa.Integer, default=0),
)
gs_messages = sa.Table("gs_messages", metadata, sa.Column("id", sa.String(64), primary_key=True), sa.Column("thread_id", sa.String(48), index=True),
                       sa.Column("sender", sa.String(16)), sa.Column("body", sa.Text), sa.Column("created_at", sa.String(32)))
gs_events = sa.Table("gs_events", metadata, sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
                     sa.Column("freelancer_id", sa.String(32), nullable=True, index=True), sa.Column("type", sa.String(32)),
                     sa.Column("ts", sa.String(32), index=True), sa.Column("payload", sa.JSON))
gs_idempotency = sa.Table(
    "gs_idempotency", metadata,
    sa.Column("freelancer_id", sa.String(32), primary_key=True),
    sa.Column("endpoint", sa.String(64), primary_key=True),
    sa.Column("key", sa.String(128), primary_key=True),
    sa.Column("request_hash", sa.String(64)),
    sa.Column("status_code", sa.Integer),
    sa.Column("response", sa.JSON),
)


@lru_cache(maxsize=1)
def config() -> dict:
    return yaml.safe_load((PKG / "config.yaml").read_text())


def database_url() -> str:
    url = os.environ.get("GIGSIM_DATABASE_URL")
    if url:
        return url
    path = ROOT / "data" / "processed" / "gigsim.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"


_engines: dict[str, sa.Engine] = {}


def get_engine(url: str | None = None) -> sa.Engine:
    url = url or database_url()
    if url not in _engines:
        kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {"pool_pre_ping": True}
        eng = sa.create_engine(url, future=True, **kwargs)
        metadata.create_all(eng)
        _engines[url] = eng
        with eng.begin() as conn:
            if conn.execute(sa.select(sa.func.count()).select_from(gs_jobs)).scalar() == 0:
                seed(eng)
    return _engines[url]


def _load(name: str):
    return json.loads((SEED_DIR / name).read_text())


def seed(engine: sa.Engine | None = None) -> dict:
    """Drop and recreate all gs_ tables, then load gigsim/seed_data/*.json."""
    engine = engine or get_engine()
    metadata.drop_all(engine)
    metadata.create_all(engine)
    hidden = _load("hidden.json")
    meta = _load("meta.json")
    cfg = config()
    with engine.begin() as conn:
        conn.execute(gs_clients.insert(), [dict(id=c["id"], data=c, hidden=hidden["clients"].get(c["id"], {})) for c in _load("clients.json")])
        rows = []
        for j in _load("jobs_historical.json"):
            rows.append(dict(id=j["id"], pool="historical", status="closed", release_order=None, category=j["category"],
                             posted_at=j["posted_at"], data=j, hidden={}))
        for n, s in enumerate(_load("jobs_stream.json")):
            j = s["job"]
            rows.append(dict(id=j["id"], pool="stream", status="open" if s["release_tick"] == 0 else "pending", release_order=n,
                             category=j["category"], posted_at=j["posted_at"], data=j, hidden=hidden["jobs"].get(j["id"], {})))
        for j in _load("jobs_dev.json"):
            rows.append(dict(id=j["id"], pool="dev", status="open", release_order=None, category=j["category"],
                             posted_at=j["posted_at"], data=j, hidden=hidden["jobs"].get(j["id"], {})))
        conn.execute(gs_jobs.insert(), rows)
        conn.execute(gs_freelancers.insert(), _load("freelancers.json"))
        threads = _load("threads.json")
        for p in threads["proposals"]:
            conn.execute(gs_proposals.insert().values(**p, updated_at=p["created_at"], decision={"frozen": True}))
        for t in threads["threads"]:
            msgs = [m for m in threads["messages"] if m["thread_id"] == t["thread_id"]]
            conn.execute(gs_threads.insert().values(**t, last_message_at=max(m["created_at"] for m in msgs), unread=1))
        conn.execute(gs_messages.insert(), threads["messages"])
        conn.execute(gs_state.insert(), [dict(key="sim_now", value=meta["sim_start"]), dict(key="tick", value="0"),
                                         dict(key="start_balance", value=str(cfg["start_balance"]))])
    return meta["counts"]


def get_state(conn, key: str, default: str | None = None) -> str | None:
    v = conn.execute(sa.select(gs_state.c.value).where(gs_state.c.key == key)).scalar()
    return default if v is None else v


def set_state(conn, key: str, value: str) -> None:
    if conn.execute(sa.select(gs_state.c.key).where(gs_state.c.key == key)).first():
        conn.execute(gs_state.update().where(gs_state.c.key == key).values(value=value))
    else:
        conn.execute(gs_state.insert().values(key=key, value=value))
