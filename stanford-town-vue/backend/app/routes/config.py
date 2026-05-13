"""Config-related endpoints.

Note: ``/api/config/effective`` is intentionally exposed from meta.py per
the spec; this module is the dedicated home for future read/write config
operations.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/config", tags=["config"])
