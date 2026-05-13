"""Catalog / metadata endpoints.

This module also currently owns ``GET /api/config/effective`` per the
Wave-1 spec, even though it lives under the ``/api/config`` URL space.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter(tags=["meta"])


@router.get("/api/meta/personas")
def list_personas() -> dict[str, Any]:
    return {"todo": "not implemented yet", "endpoint": "meta.list_personas", "items": []}


@router.get("/api/meta/maps")
def list_maps() -> dict[str, Any]:
    return {"todo": "not implemented yet", "endpoint": "meta.list_maps", "items": []}


@router.get("/api/config/effective")
def effective_config() -> dict[str, Any]:
    """Return the resolved runtime configuration the backend is using.

    Hosted here in Wave 1 to keep all read-only metadata together; may move
    to ``routes/config.py`` in M2 when write endpoints are added.
    """
    return {"todo": "not implemented yet", "endpoint": "meta.effective_config", "config": {}}
