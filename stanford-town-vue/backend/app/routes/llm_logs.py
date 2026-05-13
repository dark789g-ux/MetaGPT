"""LLM call log endpoints (scoped under a simulation)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

# These endpoints live under /api/sims/{sim_id}/llm-logs but are kept in
# their own module to match the spec's split of concerns.
router = APIRouter(prefix="/api/sims", tags=["llm-logs"])


@router.get("/{sim_id}/llm-logs")
def list_llm_logs(
    sim_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    persona: str | None = Query(default=None),
    model: str | None = Query(default=None),
) -> dict[str, Any]:
    return {
        "todo": "not implemented yet",
        "endpoint": "llm_logs.list",
        "sim_id": sim_id,
        "offset": offset,
        "limit": limit,
        "persona": persona,
        "model": model,
        "items": [],
        "total": 0,
    }


@router.get("/{sim_id}/llm-logs/{call_id}")
def get_llm_log(sim_id: str, call_id: str) -> dict[str, Any]:
    return {
        "todo": "not implemented yet",
        "endpoint": "llm_logs.get",
        "sim_id": sim_id,
        "call_id": call_id,
    }
