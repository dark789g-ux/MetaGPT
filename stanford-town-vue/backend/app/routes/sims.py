"""Simulation lifecycle + state endpoints.

All handlers are Wave-1 stubs returning placeholder dicts. They preserve
the path/query shapes so OpenAPI is accurate for frontend codegen.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Query

router = APIRouter(prefix="/api/sims", tags=["simulations"])


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

@router.post("/")
def create_and_start(payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    return {"todo": "not implemented yet", "endpoint": "sims.create_and_start", "payload": payload}


@router.get("/")
def list_sims(status: str | None = Query(default=None)) -> dict[str, Any]:
    return {"todo": "not implemented yet", "endpoint": "sims.list", "status": status, "items": []}


@router.get("/{sim_id}")
def get_sim(sim_id: str) -> dict[str, Any]:
    return {"todo": "not implemented yet", "endpoint": "sims.get", "sim_id": sim_id}


@router.post("/{sim_id}/pause")
def pause_sim(sim_id: str) -> dict[str, Any]:
    return {"todo": "not implemented yet", "endpoint": "sims.pause", "sim_id": sim_id}


@router.post("/{sim_id}/resume")
def resume_sim(sim_id: str) -> dict[str, Any]:
    return {"todo": "not implemented yet", "endpoint": "sims.resume", "sim_id": sim_id}


@router.post("/{sim_id}/stop")
def stop_sim(sim_id: str) -> dict[str, Any]:
    return {"todo": "not implemented yet", "endpoint": "sims.stop", "sim_id": sim_id}


@router.delete("/{sim_id}")
def delete_sim(sim_id: str) -> dict[str, Any]:
    return {"todo": "not implemented yet", "endpoint": "sims.delete", "sim_id": sim_id}


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

@router.get("/{sim_id}/steps")
def list_steps(
    sim_id: str,
    from_: int | None = Query(default=None, alias="from"),
    to: int | None = Query(default=None),
) -> dict[str, Any]:
    return {
        "todo": "not implemented yet",
        "endpoint": "sims.list_steps",
        "sim_id": sim_id,
        "from": from_,
        "to": to,
        "items": [],
    }


@router.get("/{sim_id}/steps/{step}")
def get_step(sim_id: str, step: int) -> dict[str, Any]:
    return {"todo": "not implemented yet", "endpoint": "sims.get_step", "sim_id": sim_id, "step": step}


# ---------------------------------------------------------------------------
# Personas (scoped under a simulation)
# ---------------------------------------------------------------------------

@router.get("/{sim_id}/personas")
def list_personas(sim_id: str) -> dict[str, Any]:
    return {"todo": "not implemented yet", "endpoint": "sims.list_personas", "sim_id": sim_id, "items": []}


@router.get("/{sim_id}/personas/{name}/state")
def persona_state(
    sim_id: str,
    name: str,
    step: int | None = Query(default=None),
) -> dict[str, Any]:
    return {
        "todo": "not implemented yet",
        "endpoint": "sims.persona_state",
        "sim_id": sim_id,
        "name": name,
        "step": step,
    }


@router.get("/{sim_id}/personas/{name}/memory")
def persona_memory(
    sim_id: str,
    name: str,
    type: str | None = Query(default=None),
    before_step: int | None = Query(default=None),
) -> dict[str, Any]:
    return {
        "todo": "not implemented yet",
        "endpoint": "sims.persona_memory",
        "sim_id": sim_id,
        "name": name,
        "type": type,
        "before_step": before_step,
        "items": [],
    }
