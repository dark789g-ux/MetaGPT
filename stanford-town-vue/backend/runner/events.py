"""Event bus stub — pub/sub between simulation workers and WS subscribers.

Real implementation lands in M3 alongside the WebSocket hub.
"""

from __future__ import annotations

from typing import Any, Callable

from loguru import logger


class EventBus:
    """In-process event bus.

    For Wave 1 all methods are stubs; signatures are stable so callers in
    other packages can already type against them.
    """

    def subscribe(self, sim_id: str, handler: Callable[[dict[str, Any]], Any]) -> None:
        logger.debug("EventBus.subscribe({}) called (stub)", sim_id)

    def unsubscribe(self, sim_id: str, handler: Callable[[dict[str, Any]], Any]) -> None:
        logger.debug("EventBus.unsubscribe({}) called (stub)", sim_id)

    def emit(self, sim_id: str, event: dict[str, Any]) -> None:
        logger.debug("EventBus.emit({}, {}) called (stub)", sim_id, event.get("event"))
