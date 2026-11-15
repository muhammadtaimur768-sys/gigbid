# GigBid developer entry points:  make dev | test | eval | seed | demo | lint
# Extra: make up | down | logs | guards | e2e | eval-smoke | openapi | checksums

SHELL := /bin/bash
.DEFAULT_GOAL := help

PY       ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python)
COMPOSE  ?= docker compose
WEB      := apps/web
PERSONAS := aiml fullstack data

# Module entry points owned by other packages (override if they move).
GIGSIM_GENERATE_MODULE ?= gigsim.generate
GIGSIM_SEED_MODULE     ?= gigsim.seed
RAG_INDEX_MODULE       ?= rag.ingest
API_SEED_MODULE        ?= apps.api.seed
RESULTS_TABLE_MODULE   ?= evals.runners.make_results_table

HAS_MOD = $(PY) -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('$(1)') else 1)" 2>/dev/null

export PYTHONPATH := $(CURDIR)

.PHONY: help
help:
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

# ------------------------------------------------------------------ run
.PHONY: dev
dev: ## Run GigSim, MCP servers, API (reload) and Vite locally without Docker (Ctrl-C stops all)
	@test -f .env || cp .env.example .env
	@trap 'kill 0' INT TERM EXIT; \
	set -a; source .env; set +a; \
	$(PY) -m uvicorn gigsim.app:app --port 8100 & \
	sleep 2; \
	$(PY) -m mcp_servers.portfolio.server --http & \
	$(PY) -m mcp_servers.marketplace.server --http & \
	$(PY) -m mcp_servers.workspace.server --http & \
	RUN_MODE=inline $(PY) -m uvicorn apps.api.main:app --port 8000 --reload --reload-dir apps --reload-dir agent --reload-dir rag & \
	(cd $(WEB) && npm run dev) & \
	wait

.PHONY: up
up: ## Start the full stack with docker compose (web on http://localhost:8080)
	@test -f .env || cp .env.example .env
	$(COMPOSE) up --build -d
	@echo "web: http://localhost:8080   api: http://localhost:8000/api/health"

.PHONY: down
down: ## Stop the docker compose stack (volumes kept)
	$(COMPOSE) down

.PHONY: logs
logs: ## Tail docker compose logs
	$(COMPOSE) logs -f --tail=100

# ------------------------------------------------------------------ data
.PHONY: seed
seed: ## Generate + seed GigSim, build portfolio indexes, seed the reviewer account
	@if [ ! -d gigsim/seed_data ]; then $(PY) -m $(GIGSIM_GENERATE_MODULE); fi
	$(PY) -m $(GIGSIM_SEED_MODULE)
	@if $(call HAS_MOD,$(RAG_INDEX_MODULE)); then \
		for p in $(PERSONAS); do echo ">> index $$p"; $(PY) -m $(RAG_INDEX_MODULE) --persona $$p || exit 1; done; \
	else echo "!! $(RAG_INDEX_MODULE) not found, index will be built lazily on first query"; fi
	@if $(call HAS_MOD,$(API_SEED_MODULE)); then $(PY) -m $(API_SEED_MODULE); \
	else echo "!! $(API_SEED_MODULE) not found, reviewer is seeded on API startup"; fi

# ------------------------------------------------------------------ quality
.PHONY: lint
lint: ## ruff + web typecheck
	$(PY) -m ruff check .
	@if [ -d $(WEB)/node_modules ]; then cd $(WEB) && npm run typecheck; \
	else echo "!! $(WEB)/node_modules missing, skipping typecheck (run npm ci in $(WEB))"; fi

.PHONY: guards
guards: ## CI guards: gigsim unchanged, prompts only in agent/prompts, README numbers traced, no secrets
	$(PY) scripts/check_gigsim_unchanged.py
	$(PY) scripts/check_prompts_location.py
	$(PY) scripts/check_readme_numbers.py
	$(PY) scripts/check_secrets.py

.PHONY: test
test: ## Unit + contract + integration tests (deterministic, no LLM needed)
	LLM_PROVIDER=heuristic GIGSIM_ERROR_RATE=0 $(PY) -m pytest -q tests/unit tests/contract tests/integration mcp_servers

.PHONY: e2e
e2e: ## Playwright UI tests (mocked API)
	cd $(WEB) && npx playwright test

.PHONY: openapi
openapi: ## Regenerate apps/web/openapi.json and the typed TS client
	$(PY) scripts/dump_openapi.py
	cd $(WEB) && npm run gen:api

.PHONY: checksums
checksums: ## Re-record gigsim/CHECKSUMS.sha256 (only when the provided simulator is updated upstream)
	$(PY) scripts/check_gigsim_unchanged.py --write

# ------------------------------------------------------------------ evaluation
.PHONY: eval
eval: ## Retrieval, decision and fixed GigSim reply-rate evals -> evals/results/*.json, then README tables
	GIGSIM_ERROR_RATE=0 $(PY) -m evals.runners.rag_eval
	GIGSIM_ERROR_RATE=0 $(PY) -m evals.runners.decision_eval
	GIGSIM_ERROR_RATE=0 $(PY) -m evals.runners.gigsim_outcomes
	@if $(call HAS_MOD,$(RESULTS_TABLE_MODULE)); then $(PY) -m $(RESULTS_TABLE_MODULE); fi

.PHONY: eval-smoke
eval-smoke: ## 30-job smoke eval + threshold gate (what .github/workflows/eval.yml runs)
	LLM_PROVIDER=heuristic GIGSIM_ERROR_RATE=0 $(PY) -m evals.runners.decision_eval --smoke 30 --profile heuristic
	LLM_PROVIDER=heuristic GIGSIM_ERROR_RATE=0 $(PY) -m evals.runners.rag_eval --smoke 30
	$(PY) scripts/check_eval_thresholds.py

# ------------------------------------------------------------------ demo
.PHONY: demo
demo: ## Start the docker stack, seed the reviewer, advance GigSim so the inbox has fresh jobs
	@test -f .env || cp .env.example .env
	$(COMPOSE) up --build -d
	@echo ">> waiting for the API"; \
	for i in $$(seq 1 60); do curl -fsS http://localhost:8000/api/health >/dev/null 2>&1 && break; sleep 3; done
	-$(COMPOSE) exec -T api python -m $(API_SEED_MODULE)
	curl -fsS -X POST -H "X-Admin-Key: $${GIGSIM_ADMIN_KEY:-gigsim-admin}" http://localhost:8100/admin/tick >/dev/null && echo ">> GigSim advanced one tick"
	@echo ""
	@echo "Open http://localhost:8080 and sign in as reviewer@gigbid.app (password = REVIEWER_PASSWORD in .env)"
