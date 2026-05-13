"""LLM profile management endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body

router = APIRouter(prefix="/api/llm-profiles", tags=["llm-profiles"])


@router.get("/")
def list_profiles() -> dict[str, Any]:
    return {"todo": "not implemented yet", "endpoint": "llm_profiles.list", "items": []}


@router.post("/")
def create_profile(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return {"todo": "not implemented yet", "endpoint": "llm_profiles.create", "payload": payload}


@router.put("/{profile_id}")
def update_profile(profile_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return {
        "todo": "not implemented yet",
        "endpoint": "llm_profiles.update",
        "profile_id": profile_id,
        "payload": payload,
    }


@router.delete("/{profile_id}")
def delete_profile(profile_id: str) -> dict[str, Any]:
    return {"todo": "not implemented yet", "endpoint": "llm_profiles.delete", "profile_id": profile_id}


@router.post("/{profile_id}/test")
def test_profile(profile_id: str) -> dict[str, Any]:
    return {"todo": "not implemented yet", "endpoint": "llm_profiles.test", "profile_id": profile_id}
