# AGENTS.md

## Cursor Cloud specific instructions

### Overview

AgentChatBus is a single-process Python application (FastAPI + Uvicorn + SQLite). No external services, Docker, or databases are needed. See `README.md` and `docs/getting-started/install.md` for full documentation.

### Running the application

- Dev server: `source .venv/bin/activate && python -m src.main` (serves API + MCP + web console on port 39765)
- Bind to all interfaces: set `AGENTCHATBUS_HOST=0.0.0.0`
- Web console: open `http://127.0.0.1:39765` in a browser

### Testing

- Backend: `source .venv/bin/activate && pytest tests/ -x -v` (353 tests; conftest auto-starts a test server on port 39769 with a separate SQLite DB at `tests/data/bus_test.db`)
- Frontend: `cd frontend && npx vitest run` (some pre-existing failures on `main` branch related to status naming changes)
- Linting: `source .venv/bin/activate && flake8 src/ --max-line-length=120`

### Gotchas

- The test suite uses port **39769** (not 39765) and a dedicated test database. The `tests/conftest.py` enforces this and will refuse to run against production DB paths.
- `pytest-asyncio` version pinned at `>=0.23.0`; `asyncio_mode = "auto"` is set in `pyproject.toml`.
- The `python3.12-venv` system package is required to create the virtual environment (not installed by default on Ubuntu 24.04).
- The `frontend/` directory is only for JS unit tests (Vitest + jsdom); it does not contain a separate frontend application.
- When adding new built-in templates in `src/db/database.py`, update the template count assertion in `tests/test_thread_templates.py::test_builtin_templates_seeded`.
- Set `AGENTCHATBUS_ADMIN_TOKEN` env var to protect the `/api/agents/{id}/kick` endpoint. Without it, kick is unauthenticated.
- For multi-agent Cursor setup, see `doc/CURSOR_MULTI_AGENT_SETUP.md`.
