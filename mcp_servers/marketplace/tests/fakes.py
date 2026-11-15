"""In-memory marketplace adapter used by server tests."""
from __future__ import annotations

from mcp_servers.marketplace.adapters.base import InsufficientConnects, MarketplaceNotFound, MarketplaceUnavailable

JOB = {"id": "job-001", "title": "Build a RAG chatbot", "description": "Need RAG over PDFs.", "category": "AI & ML",
       "skills_required": ["python", "rag"], "budget_type": "fixed", "budget_min": 500, "budget_max": 1500,
       "duration": "1-3 months", "posted_at": "2026-11-10T10:00:00Z", "client_id": "cl-01", "connects_cost": 12,
       "proposals_count": 4, "screening_questions": ["Describe a RAG system you built."],
       "experience_level": "expert"}


class FakeAdapter:
    name = "fake"

    def __init__(self, balance: int = 30):
        self.balance = balance
        self.submits = 0
        self.sent: list[str] = []
        self.down = False

    def _check(self):
        if self.down:
            raise MarketplaceUnavailable("fake down")

    async def health(self):
        return {"ok": not self.down, "marketplace": self.name}

    async def search_jobs(self, q="", category=None, skills=None, since=None, limit=20, offset=0):
        self._check()
        jobs = [JOB] if (not q or q.lower() in JOB["title"].lower()) else []
        return {"jobs": jobs[offset:offset + limit], "total": len(jobs)}

    async def get_job(self, job_id):
        self._check()
        if job_id != JOB["id"]:
            raise MarketplaceNotFound(job_id, 404)
        return JOB

    async def get_client_history(self, client_id):
        return {"client_id": client_id, "name": "Acme", "hires": 3, "avg_rating": 4.8, "payment_verified": True,
                "reviews": [{"rating": 5, "text": "good"}]}

    async def get_connects(self):
        return {"freelancer_id": "fl-aiml", "balance": self.balance, "weekly_spent": 0}

    async def list_threads(self):
        return [{"thread_id": "th-1", "job_id": "job-001", "client_id": "cl-01", "unread": 1}]

    async def list_messages(self, thread_id):
        return [{"id": "m1", "sender": "client", "body": "Can you start Monday? mail me at bob@x.com",
                 "created_at": "2026-11-11T09:00:00Z"}]

    async def get_market_stats(self, category):
        return {"category": category, "n": 100, "hourly": {"p25": 30, "p50": 45, "p75": 70},
                "fixed": {"p25": 400, "p50": 900, "p75": 2000}}

    async def list_proposals(self):
        return [{"proposal_id": "p1", "job_id": "job-001", "status": "viewed"},
                {"proposal_id": "p2", "job_id": "job-002", "status": "lost"}]

    async def create_proposal_draft(self, payload, idempotency_key, dry_run):
        return {"draft_id": None if dry_run else "draft-1", "status": "preview" if dry_run else "draft",
                "job_id": payload["job_id"], "preview": payload, "connects_cost": 12,
                "balance_after": self.balance - 12}

    async def submit_proposal(self, payload, idempotency_key, dry_run):
        self._check()
        if dry_run:
            return {"status": "would_submit", "job_id": payload["job_id"], "would_send": payload,
                    "connects_cost": 12, "balance_after": self.balance - 12}
        if self.balance < 12:
            raise InsufficientConnects("not enough Connects", 402)
        self.balance -= 12
        self.submits += 1
        return {"status": "submitted", "job_id": payload["job_id"], "proposal_id": f"prop-{self.submits}",
                "connects_spent": 12, "balance_after": self.balance}

    async def send_message(self, thread_id, body, idempotency_key, dry_run):
        if dry_run:
            return {"status": "would_send", "thread_id": thread_id, "would_send": {"body": body}}
        self.sent.append(body)
        return {"status": "sent", "thread_id": thread_id, "message_id": f"m{len(self.sent)}"}
