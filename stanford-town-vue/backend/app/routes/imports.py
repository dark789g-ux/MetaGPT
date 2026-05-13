"""Import / export endpoints for forked simulations."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body

router = APIRouter(prefix="/api/sims", tags=["imports"])


@router.post("/import")
def import_sim(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return {
        "todo": "not implemented yet",
        "endpoint": "imports.import_sim",
        "source_path": payload.get("source_path"),
    }


@router.post("/{sim_id}/export")
def export_sim(sim_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return {
        "todo": "not implemented yet",
        "endpoint": "imports.export_sim",
        "sim_id": sim_id,
        "target_dir": payload.get("target_dir"),
    }


@router.get("/import/forks")
def list_forks() -> dict[str, Any]:
    return {"todo": "not implemented yet", "endpoint": "imports.list_forks", "items": []}
