# Stanford Town Vue

An independent Vue3 + Ant Design + FastAPI + SQLite reimplementation of the Stanford generative-agents simulation, derived from the `examples/stanford_town` example in MetaGPT.

- Zero external dependency on `metagpt` (necessary code is vendored under `backend/core/` and `backend/simulator/`).
- SQLite as the single source of truth, with bidirectional JSON I/O for compatibility with the original storage format.
- Pixi.js v7 map renderer, WebSocket live updates.

See `docs/` for the design spec and milestone breakdown.

## Quick start

```powershell
# Backend
cd backend
pip install -e .
alembic upgrade head
uvicorn app.main:app --reload

# Frontend (another terminal)
cd frontend
pnpm install
pnpm dev
```

Visit http://localhost:5173 in dev mode.
