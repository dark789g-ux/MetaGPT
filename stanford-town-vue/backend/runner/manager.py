"""SimulationManager — orchestrates per-simulation worker tasks.

This is a Wave-1 stub. Real start/pause/resume/stop logic lands in M3,
once the simulator core has been vendored and the persistence schema is
in place.
"""

from __future__ import annotations

from typing import Any

from loguru import logger


class SimulationManager:
    """Singleton manager for all running simulations.

    Currently a stub; every operational method raises ``NotImplementedError``
    so that callers fail fast if they accidentally rely on this before M3.
    ``scan_interrupted`` is intentionally a no-op so the FastAPI lifespan
    handler can call it during startup without crashing.
    """

    def start(self, *args: Any, **kwargs: Any) -> Any:
        logger.info("SimulationManager.start called (stub)")
        raise NotImplementedError("SimulationManager.start is not implemented yet")

    def pause(self, sim_id: str) -> Any:
        logger.info("SimulationManager.pause({}) called (stub)", sim_id)
        raise NotImplementedError("SimulationManager.pause is not implemented yet")

    def resume(self, sim_id: str) -> Any:
        logger.info("SimulationManager.resume({}) called (stub)", sim_id)
        raise NotImplementedError("SimulationManager.resume is not implemented yet")

    def stop(self, sim_id: str) -> Any:
        logger.info("SimulationManager.stop({}) called (stub)", sim_id)
        raise NotImplementedError("SimulationManager.stop is not implemented yet")

    def status(self, sim_id: str) -> Any:
        logger.info("SimulationManager.status({}) called (stub)", sim_id)
        raise NotImplementedError("SimulationManager.status is not implemented yet")

    def list_running(self) -> list[str]:
        logger.info("SimulationManager.list_running called (stub)")
        raise NotImplementedError("SimulationManager.list_running is not implemented yet")

    def scan_interrupted(self) -> None:
        """Look for sims in ``running`` state with no live worker and mark them.

        No-op until M3 — safe to call at startup.
        """
        logger.debug("SimulationManager.scan_interrupted: no-op stub")


manager_singleton = SimulationManager()
