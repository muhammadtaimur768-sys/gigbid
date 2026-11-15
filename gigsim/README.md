# GigSim

A deterministic, synthetic freelance marketplace used to develop and grade GigBid. FastAPI app `gigsim.app:app`, default port 8100.
All content is synthetic and template-driven (random seed 42); no language model is used to produce it.

## Run

```bash
.venv/bin/python -m gigsim.generate      # rebuild data/personas, data/policy_pack, gigsim/seed_data, evals/datasets
.venv/bin/python -m gigsim.seed          # (re)seed the database from gigsim/seed_data/*.json
.venv/bin/uvicorn gigsim.app:app --port 8100
```

The app also seeds itself on first request if its tables are empty.

| Env var | Default | Meaning |
|---|---|---|
| `GIGSIM_DATABASE_URL` | `sqlite:///data/processed/gigsim.db` | SQLAlchemy URL; tables are prefixed `gs_` (Postgres works too) |
| `GIGSIM_ERROR_RATE` | `0.02` | probability of a simulated `503` on any authenticated call (set `0` in tests) |
| `GIGSIM_RATE_LIMIT` | `60` | requests per minute per token, then `429` + `Retry-After` |
| `GIGSIM_POLICY_UPDATE` | `1` | activates the 2026-11-02 platform policy update |
| `GIGSIM_ADMIN_KEY` | `gigsim-admin` | value of the `X-Admin-Key` header for `/admin/*` |
| `GIGSIM_CLIENT_LLM` | `0` | `1` blends an Ollama judgement into client decisions (prompt: `gigsim/prompts/client_decision.md`) |

Other knobs (tick size, client-model weights, surcharge values) live in `gigsim/config.yaml`.

## Auth

`Authorization: Bearer <token>`. Tokens (`gigsim/seed_data/tokens.json`): `gs-aiml-token` → `fl-aiml`, `gs-fullstack-token` → `fl-fullstack`,
`gs-data-token` → `fl-data`. Every freelancer starts with 140 Connects minus the seeded proposals.

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/health` | no auth; sim clock, tick, policy flag |
| GET | `/jobs?q=&category=&skills=a,b&since=ISO&limit=50&offset=0` | `{jobs, total}`; only open jobs of the live stream, newest first |
| GET | `/jobs/{job_id}` | any released job (stream, dev set or historical) |
| GET | `/clients/{client_id}/history` | spend, hires, rating, payment verification, reviews |
| GET | `/connects` | `{freelancer_id, balance, weekly_spent}` |
| GET | `/market/stats?category=` | p25/p50/p75 of awarded hourly and fixed amounts over the historical jobs |
| GET | `/policy` | active policy-update parameters |
| POST | `/proposals` | `{job_id, cover_letter, screening_answers[], bid_amount, idempotency_key, dry_run}` |
| GET | `/proposals` | own proposals with status `submitted / viewed / replied / interview / hired / lost` |
| GET | `/threads` | own client conversations |
| GET | `/threads/{id}/messages` | marks the thread read |
| POST | `/threads/{id}/messages` | `{body, idempotency_key}` |
| GET | `/events?since=ISO` | `proposal_status`, `new_message`, `new_job` events (sim-clock timestamps) |
| POST | `/admin/tick` | `X-Admin-Key`; optional `{n_jobs, hours}`; releases stream jobs, advances client decisions |
| POST | `/admin/reset` | `X-Admin-Key`; reseeds everything |
| GET | `/admin/hidden/{job_id}` | `X-Admin-Key`; hidden labels for graders only |

Errors are JSON `{error, detail}`: `401 unauthorized`, `402 insufficient_connects`, `404 not_found`, `409 already_applied | idempotency_conflict | job_closed`,
`422 proposal_too_long | idempotency_key_required`, `429 rate_limited` (with `Retry-After`), `503 upstream_unavailable`.

### Proposal semantics

- **Idempotency:** the same `idempotency_key` with the same body returns the stored response (header `Idempotent-Replay: true`) and never spends Connects twice; the same key with a different body returns `409`.
- **dry_run:** runs every check (job open, length, balance, surcharge) and returns `{would_send, connects_cost, surcharge, balance_after}` without writing anything. No key needed.
- **Policy update (2026-11-02):** jobs posted less than 60 minutes before the sim clock cost +2 Connects (early-bird surcharge), and cover letters over 2,500 characters are rejected with `422 proposal_too_long`. The same change is described for GigBid in `data/policy_pack/updates/2026-11-02.yaml`.

## Simulation

- Sim clock starts at `2026-11-03T09:00:00Z`; each tick advances it one hour and releases 20 stream jobs (`gigsim/config.yaml`).
- Each proposal moves one stage per tick: `submitted → viewed → replied | lost → interview → hired | lost`; clients write messages on reply, interview and decision. Seeded conversations stay frozen.
- Client decisions come from `gigsim.client_model.score_proposal(job_id, cover_letter, bid_amount) -> {reply_prob, replied, interview, hired, factors}`, a pure function: must-have skills mentioned in the letter (aliases count), bid within the hidden budget ceiling, generic-opening penalty ("Dear Sir", "I am a passionate", ...), length vs. preference, title overlap, answered screening questions, plus a hash-seeded draw. Scam jobs never reply.
- Hidden fields (scam, injection, duplicate_of, client preferences, estimated hours) live only in the `gs_jobs.hidden` column and `seed_data/hidden.json`.

## Data produced by `python -m gigsim.generate`

- `data/personas/{aiml,fullstack,data}/`: `profile.json`, `cv.md`, `cv.pdf`, `case_studies/*.md` (YAML frontmatter), `repos/*/README.md + src/*`, `reviews.json`, `proposals.jsonl`, and `manifest.json` (one metadata row per item). The same project appears as a case study (by slug), a repo (by codename) and in proposals/reviews (by a casual description); repos' code reveals skills their README never names; about 15% of proposal outcomes deliberately contradict their wording.
- `data/policy_pack/`: `policy.md`, `rules.yaml`, `updates/2026-11-02.yaml`.
- `gigsim/seed_data/`: 1,500 historical (closed) jobs, 600 stream jobs (120 open at start; about 5% duplicates, 8% scams, 5% planted prompt injection), 600 dev-set jobs, 500 clients, tokens, seeded threads.
- `evals/datasets/dev_{persona}.jsonl` (200 each, gold `action`, `is_scam`, `has_injection`, `evidence_ids`, `fair_price_band`, `requirements`, `job_type`, plus `skip_reason`) and `tool_tasks.jsonl` (40 tasks with expected tool calls). Gold evidence ids are case studies and repos whose underlying project uses the job's required skills, taken from the same graph that produced the corpus.

`gigsim/CHECKSUMS.sha256` covers `gigsim/*.py`; verify with `shasum -a 256 -c gigsim/CHECKSUMS.sha256`.
