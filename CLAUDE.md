# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Backend (`backend/`, Python 3.10–3.12, managed with `uv`):

```bash
cd backend
uv sync                                                # install/sync deps + venv
uv run uvicorn ticket_agent.main:app --reload --port 8000  # run API (dev)
uv run python -m compileall src/ticket_agent           # fast syntax/compile check
uv run python _generate_diverse_tickets.py             # generate 50 diverse demo tickets
```

Frontend (`frontend/`, Vue 3 + Vite + TypeScript; use `npm.cmd` on Windows):

```bash
cd frontend
npm.cmd install
npm.cmd run dev      # vite dev server on 127.0.0.1:5174
npm.cmd run build    # vue-tsc type-check + vite build
npm.cmd run smoke:page-agent
```

Tests are standalone async smoke scripts (no pytest suite). Run a **single** one directly, e.g.:

```bash
cd backend
uv run python tests/smoke_module_k_workflow_routing.py
```

Smoke modules run against a MySQL test database (`ticket_agent_test`), separate from the demo DB (`ticket_agent`). They call `configure_mysql_test_database` / `reset_mysql_test_data` from `tests/mysql_smoke_utils.py` before `asyncio.run(main())`.

## Architecture

**Pipeline.** A phone-call transcript is turned into a standard ticket, processed by a multi-agent orchestrator, audited via Mock Tools, assisted by PageAgent/SunPilot for form-fill/reply, and closed only after human review. `src/ticket_agent/main.py` (FastAPI) exposes ticket CRUD, `/api/tickets/{id}/ai-process[-stream]` (SSE), call-record→draft generation, and config/metrics endpoints.

**Five business agents** (`src/ticket_agent/agents/`): Classifier, Intake, Resolution, Escalation, Notification. Each extends `BaseAgent` (`agents/base.py`), is constructed from an `AgentCard`, and shares one module-level `AsyncOpenAI` client. `Orchestrator` (`orchestrator/orchestrator.py`) builds all five from `agent_registry` and keeps legacy aliases (`intent_agent`, `extract_agent`, `tool_agent`, `verify_agent`, `reply_agent`) pointing at them — files like `reply_agent.py`/`intent_agent.py` are compat shims, not a 6th agent.

**Orchestration order** in `process_ticket()`: load → IN_PROGRESS → high-risk short-circuit → classifier → normalize intent → intake → field enrichment → escalation (risk gate) → maybe stop (PENDING_INFO / PENDING_HUMAN_CONFIRM) → resolution (tool plan) → `tool_registry.validate_tool_call` → `mock_executor.execute` → re-run escalation → finish review (PENDING_HUMAN_REVIEW) or escalate. `public_result()` strips `_`-prefixed internal keys.

**Config is the single source of truth.** `workflow_config.json` drives field maps, scenarios, and gating. Load via `load_workflow_config()` (`@lru_cache`), validate through `WorkflowConfig.model_validate(...).to_runtime_dict()` (camelCase JSON aliases → snake_case runtime keys). Do not reintroduce hardcoded field maps that compete with it.

**Deterministic fast-lane + LLM slow-lane.** Intake runs deterministic extraction first; the fast-lane only fires when **all** configured `required_fields` are extracted, otherwise it falls through to an LLM merge that fills gaps only. The LLM must never override deterministic values (state, evidence IDs, failure reasons, gating, closure).

**Two separate LLM configs** (`config.py`): business agents use `LLM_*` (DeepSeek-compatible gateway, default model `deepseek-v4-flash`); PageAgent/SunPilot use `PAGE_AGENT_LLM_*` (Ali/Qwen), proxied through backend endpoints (`/api/llm/proxy/*`). Keep them distinct.

**Persistence.** MySQL via SQLAlchemy 2 + asyncmy; schema in `backend/src/ticket_agent/migrations/mysql/` (`001_i1_schema.sql`, `002_dispatch_ext.sql`); Alembic present. DB config from `.env` (`DATABASE_URL=mysql+asyncmy://...`); see `.env.example`. **Transaction management**: uses SQLAlchemy 2.0 async context manager pattern (`async with engine.connect() as conn: async with conn.begin() as trans:`); transactions auto-commit on context exit (no exception) or auto-rollback (on exception). Do not call `commit()` manually — it closes the transaction and causes "closed transaction" errors on subsequent operations. Database layer is in `src/ticket_agent/models/database.py` (connection/init) and `src/ticket_agent/repositories/repositories.py` (CRUD operations).

## Boundaries (do not violate)

- The automated flow **cannot close a ticket**. Closure only happens via `POST /api/tickets/{ticket_id}/close`. NotificationAgent may only emit `closureSuggestion.canClose`.
- PageAgent is restricted to white-listed page actions — no arbitrary DOM-index clicks, no JS execution, no direct save/close/transfer.
- All text files must be UTF-8 without BOM.
- Confirm with the user before modifying `.env`, DB schema, seed data, or adding dependencies; do not delete source/docs/config/lock files without confirmation; do not commit, push, or create remotes without an explicit request.
- Commit messages must be short — a single line, no body.

See `AGENTS.md` (root) for the fuller collaboration guide these rules derive from.

## Language Use

**Simplified Chinese** for:
- Task execution results and error messages (任务执行结果与错误信息)
- Confirmations and clarifications with the user (与用户的确认和澄清)
- Solution descriptions and to-do items (解决方案描述与待办事项)
