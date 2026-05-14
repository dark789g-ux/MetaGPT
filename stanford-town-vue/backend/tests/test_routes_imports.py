"""Integration tests for /api/sims/import* and /api/sims/{id}/export."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

# Make backend/ importable when pytest runs from the repo root.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.deps import get_db  # noqa: E402
from app.main import app  # noqa: E402
from storage.db import Base  # noqa: E402


# The MetaGPT root (parent of stanford-town-vue/).
_PROJECT_ROOT = _BACKEND_DIR.parent.parent
_BUNDLED_FORK = (
    _PROJECT_ROOT / "examples" / "stanford_town" / "storage" / "base_the_ville_n25"
)


@pytest.fixture()
def session_factory():
    from sqlalchemy.pool import StaticPool
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    yield SessionLocal
    engine.dispose()


@pytest.fixture()
def client(session_factory) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


# ----------------------------------------------------------------- import


@pytest.mark.skipif(
    not _BUNDLED_FORK.is_dir(),
    reason="Bundled fork base_the_ville_n25 not present in this checkout",
)
def test_import_bundled_fork_succeeds(client):
    resp = client.post(
        "/api/sims/import",
        json={
            "source_path": str(_BUNDLED_FORK),
            "on_conflict": "fail",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["sim_id"] >= 1
    assert body["sim_code"] == "base_the_ville_n25"
    assert body["counts"]["personas"] == 25


@pytest.mark.skipif(
    not _BUNDLED_FORK.is_dir(),
    reason="Bundled fork base_the_ville_n25 not present",
)
def test_import_duplicate_fails(client):
    payload = {"source_path": str(_BUNDLED_FORK), "on_conflict": "fail"}
    r1 = client.post("/api/sims/import", json=payload)
    assert r1.status_code == 200, r1.text
    r2 = client.post("/api/sims/import", json=payload)
    assert r2.status_code == 409


@pytest.mark.skipif(
    not _BUNDLED_FORK.is_dir(),
    reason="Bundled fork base_the_ville_n25 not present",
)
def test_import_replace_succeeds(client):
    payload = {"source_path": str(_BUNDLED_FORK), "on_conflict": "fail"}
    r1 = client.post("/api/sims/import", json=payload)
    assert r1.status_code == 200, r1.text
    payload2 = {"source_path": str(_BUNDLED_FORK), "on_conflict": "replace"}
    r2 = client.post("/api/sims/import", json=payload2)
    assert r2.status_code == 200, r2.text


def test_import_missing_path_returns_400(client):
    resp = client.post(
        "/api/sims/import",
        json={
            "source_path": "/nonexistent/place/that/does/not/exist",
            "on_conflict": "fail",
        },
    )
    assert resp.status_code == 400


# ----------------------------------------------------------------- export


@pytest.mark.skipif(
    not _BUNDLED_FORK.is_dir(),
    reason="Bundled fork base_the_ville_n25 not present",
)
def test_export_round_trip(client, tmp_path):
    imp = client.post(
        "/api/sims/import",
        json={"source_path": str(_BUNDLED_FORK), "on_conflict": "fail"},
    )
    assert imp.status_code == 200, imp.text
    sim_id = imp.json()["sim_id"]

    target = tmp_path / "exports"
    target.mkdir()
    resp = client.post(
        f"/api/sims/{sim_id}/export",
        json={"target_dir": str(target), "layout": "compressed"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    out_path = Path(body["output_path"])
    assert out_path.is_dir()
    assert (out_path / "meta.json").is_file()


def test_export_unknown_sim_returns_404(client, tmp_path):
    resp = client.post(
        "/api/sims/9999/export",
        json={"target_dir": str(tmp_path), "layout": "compressed"},
    )
    assert resp.status_code == 404


# ------------------------------------------------------------------ forks


def test_list_forks_returns_bundled(client):
    resp = client.get("/api/sims/import/forks")
    assert resp.status_code == 200, resp.text
    items = resp.json()
    # The bundled storage/ folder is present in this checkout.
    sources = {item["source"] for item in items}
    if _BUNDLED_FORK.is_dir():
        assert "storage" in sources
        assert len(items) > 0
        # Bundled fork must surface with its 25 persona names.
        bundled = [
            i
            for i in items
            if i["sim_code"] == "base_the_ville_n25" and i["source"] == "storage"
        ]
        assert bundled, "expected base_the_ville_n25 in forks list"
        assert len(bundled[0]["persona_names"]) == 25
    else:
        # Empty checkout — endpoint must still respond cleanly.
        assert isinstance(items, list)
