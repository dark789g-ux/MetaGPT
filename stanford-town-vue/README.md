# Stanford Town Vue

A standalone reimplementation of MetaGPT's `examples/stanford_town` generative-agents
simulation ("the Ville"), rebuilt as a self-contained Vue 3 + FastAPI + SQLite
application. It provides a dashboard for launching simulations, live and replay
simulation viewers, per-call LLM logs, and a persona state inspector.

All MetaGPT framework code that the simulator needs is vendored into this
repository (under `backend/core/` and `backend/simulator/`), so the project has
**zero external dependency on the `metagpt` package** and can be cloned and run
on its own.

## Architecture

The backend is a **single FastAPI process** that hosts the REST API, a WebSocket
hub for live updates, and an in-process asyncio `SimulationManager` that owns one
worker task per running simulation. **SQLite is the single source of truth** for
all simulation state (13 tables), with a bidirectional importer/exporter that
reads and writes the original Stanford Town on-disk JSON format.

The frontend is a Vue 3 SPA (Pinia stores, Ant Design Vue components, Vue Router).
The map is rendered with **PixiJS v8** against a pre-flattened map image produced
offline by `scripts/flatten_map.py` (instead of compositing ~18 Tiled tilesets at
runtime).

```
                        +-----------------------------------------+
   Browser (Vue 3 SPA)  |         FastAPI single process          |
  +------------------+  |  +-----------+  +--------------------+   |
  | Pinia stores     |--+->| REST API  |  | SimulationManager  |   |
  | AntD components  |  |  | routers   |  | (asyncio worker    |   |
  | PixiJS v8 canvas |<-+--| WebSocket |<-| task per sim)      |   |
  +------------------+  |  | hub       |  +---------+----------+   |
                        |  +-----+-----+            |              |
                        |        |        +---------v----------+   |
                        |        +------->|  SQLite database   |   |
                        |                 | (source of truth)  |   |
                        |                 +---------+----------+   |
                        |                           |              |
                        |                  JSON import / export    |
                        +-----------------------------------------+
```

## Project layout

```
stanford-town-vue/
  backend/      FastAPI app, vendored MetaGPT core + simulator, SQLite storage,
                Alembic migrations, runner (SimulationManager + StanfordTown runner),
                and bundled map / character / persona assets.
  frontend/     Vue 3 + Vite SPA: dashboard, viewers, LLM logs, persona state.
  scripts/      Offline preprocessing: flatten_map.py (map image) and
                copy_assets.py (pull original assets into backend/assets/).
  docs/         Design notes: json_format.md (storage format contract) and
                deployment.md.
```

Inside `backend/`:

```
  app/        FastAPI entrypoint (app/main.py), HTTP routers, WebSocket hub.
  core/       Vendored MetaGPT framework code (LLM providers, config, context).
  simulator/  Vendored Stanford Town simulator (roles, memory, plan, actions).
  runner/     SimulationManager, the live StanfordTown runner, LLM-config glue.
  storage/    SQLAlchemy models, repos, JSON importer/exporter.
  config/     Runtime settings (pydantic-settings).
  alembic/    Database migrations.
  assets/     Bundled maze, character sprite sheets, persona bootstrap memory.
  data/       SQLite database file (created at runtime; gitignored).
```

## Prerequisites

- **Python >= 3.10**
- **Node.js** (LTS) and **pnpm** (the frontend uses a `pnpm-lock.yaml`)

## Backend setup & run

All backend commands are run from the `backend/` directory.

```bash
cd backend

# 1. Create and activate a virtualenv
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS / Linux:
# source .venv/bin/activate

# 2. Install the backend (editable)
pip install -e .
# For development tooling (pytest, ruff, mypy):
# pip install -e ".[dev]"

# 3. Apply database migrations
alembic upgrade head

# 4. Run the server
uvicorn app.main:app --reload
```

Notes:

- **Secret key**: on first startup the app generates a Fernet secret key at
  `~/.stanford-town-vue/secret.key` and logs a warning to back it up. This key
  encrypts LLM profile API keys; if it is lost, existing encrypted profiles
  become unreadable. See the LLM configuration section below.
- **Migrations**: `app/main.py` also runs `alembic upgrade head` automatically on
  startup, so step 3 is mostly useful for inspecting the schema ahead of time.
- **Map flattening**: the PixiJS viewer expects pre-flattened map images. Generate
  them once from the repo root:

  ```bash
  python scripts/flatten_map.py            # writes the_ville_ground.png / _foreground.png
  python scripts/flatten_map.py --force    # overwrite existing outputs
  ```

  This reads `backend/assets/maze/the_ville/visuals/the_ville_jan7.json`. It
  requires Pillow (`pip install Pillow`). If the bundled assets are not present,
  run `python scripts/copy_assets.py` first to pull them from an
  `examples/stanford_town` source tree.
- **Optional LLM config via MetaGPT**: if you do not configure an LLM profile in
  the UI, the simulator falls back to ambient MetaGPT `core` configuration — a
  `~/.metagpt/config2.yaml` (or a bundled `default.yaml` / environment variables).
  See LLM configuration below.

Settings are read by `config/settings.py` via pydantic-settings. All fields are
overridable with the `STT_` env prefix or a `backend/.env` file:

| Setting              | Env var                  | Default                              |
| -------------------- | ------------------------ | ------------------------------------ |
| `database_url`       | `STT_DATABASE_URL`       | `sqlite:///./data/stanford_town.db`  |
| `secret_key_path`    | `STT_SECRET_KEY_PATH`    | `~/.stanford-town-vue/secret.key`    |
| `logs_dir`           | `STT_LOGS_DIR`           | `~/.stanford-town-vue/logs`          |
| `assets_dir`         | `STT_ASSETS_DIR`         | `assets` (relative to `backend/`)    |
| `frontend_dev_origin`| `STT_FRONTEND_DEV_ORIGIN`| `http://localhost:5173`              |

## Frontend setup & run

All frontend commands are run from the `frontend/` directory.

```bash
cd frontend

# Install dependencies
pnpm install

# Run the dev server (Vite, port 5173)
pnpm dev

# Type-check and produce a production build into frontend/dist/
pnpm build
```

The Vite dev server listens on **http://localhost:5173** and proxies `/api`,
`/ws`, `/static`, and `/assets` to the backend at `http://localhost:8000`, so
run the backend in a separate terminal first. With both running, open
http://localhost:5173.

`pnpm gen:api` regenerates `src/types/api.ts` from the backend's live
`/openapi.json` (the backend must be running).

## LLM configuration

The simulator can reach an LLM through several configuration sources, resolved in
priority order (highest first):

1. **UI per-launch override** — values chosen on the launch form for a single run.
2. **UI LLM profile** — a saved profile (provider, model, base URL, params, API
   key) attached to the simulation. The runner looks the profile up, decrypts its
   key, and builds a dedicated context for that run.
3. **`default.yaml`** — a bundled MetaGPT-style default config, if present.
4. **Environment variables** — provider/model/key picked up from the environment.
5. **`~/.metagpt/config2.yaml`** — the user's ambient MetaGPT configuration.

When no UI profile is attached, the runner falls back to ambient MetaGPT `core`
config (sources 3-5). This is convenient for users who already have a working
`~/.metagpt/config2.yaml`.

LLM profiles are managed through the `/api/llm-profiles` endpoints. Each profile's
API key is stored **Fernet-encrypted** using the app secret key, and the API never
returns the key — only non-secret fields (name, provider, model, base URL, params)
are serialized back to clients. Supported providers: `openai`, `deepseek`,
`anthropic`.

## The four pages

- **Dashboard** (`/`) — a launch form (pick a fork, personas, start time, LLM
  profile) plus a table of all simulations and their status.
- **Live viewer** (`/sims/:id/live`) — the PixiJS map with agents updating in
  real time over the WebSocket as a running simulation steps.
- **Replay viewer** (`/sims/:id/replay`) — the same map driven by a step slider
  for scrubbing through a completed simulation's recorded history.
- **LLM logs + persona state** (`/sims/:id/llm-logs`, `/sims/:id/personas/:name`)
  — every LLM call for a simulation (prompt, response, tokens, latency, errors)
  and a per-persona inspector for scratch state, schedule, and associative memory.

## Import / export

The backend can **import** an original Stanford Town simulation directory (the
on-disk JSON fork format — `reverie/meta.json`, `environment/`, `movement/`,
`personas/`, `llm_logs.jsonl`) into the SQLite database, and **export** any
simulation back out to that JSON format (`compressed` or `live` layout). The
on-disk JSON contract is documented in `docs/json_format.md`. Import/export is
exposed via the `/api/sims/import` and `/api/sims/{id}/export` endpoints and the
Import / Export settings page in the UI.
