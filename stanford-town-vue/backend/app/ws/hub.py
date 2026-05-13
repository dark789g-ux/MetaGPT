"""WebSocket hub — stub for M1.

Real implementation (per-sim subscriber registry, replay-from-step, fan-out
of EventBus events) lands in M3. For now we accept the connection, parse
one ``subscribe`` message, emit a placeholder snapshot, then echo pings.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

router = APIRouter()


@router.websocket("/ws/sim/{sim_id}")
async def sim_socket(websocket: WebSocket, sim_id: str) -> None:
    await websocket.accept()
    logger.info("WS connected for sim {}", sim_id)

    # Expect a single subscribe handshake first.
    since_step = 0
    try:
        raw = await websocket.receive_text()
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            msg = {}
        if msg.get("action") == "subscribe":
            since_step = int(msg.get("since_step", 0) or 0)
    except WebSocketDisconnect:
        logger.info("WS for sim {} disconnected before subscribe", sim_id)
        return

    await websocket.send_json(
        {
            "event": "snapshot",
            "sim": {"id": sim_id},
            "current_step": since_step,
        }
    )

    # Stub echo loop — real fan-out replaces this in M3.
    try:
        while True:
            text = await websocket.receive_text()
            await websocket.send_json({"event": "pong", "echo": text})
    except WebSocketDisconnect:
        logger.info("WS for sim {} closed", sim_id)
