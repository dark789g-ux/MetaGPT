"""Unit tests for sim_utils.validate_personas."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# The frontend Django app lives outside the package tree; add it to sys.path
# so we can import sim_utils without spinning up Django.
FRONTEND_DIR = Path(__file__).resolve().parents[5] / "examples" / "stanford_town" / "frontend"
sys.path.insert(0, str(FRONTEND_DIR))

from translator import sim_utils  # noqa: E402


def _make_base(tmp_path: Path, sim_code: str, persona_names: list[str]) -> Path:
    """Write a minimal storage/<sim>/reverie/meta.json with the given personas."""
    storage = tmp_path / "storage"
    reverie = storage / sim_code / "reverie"
    reverie.mkdir(parents=True)
    (reverie / "meta.json").write_text(json.dumps({"persona_names": persona_names}))
    return storage


def test_returns_none_when_personas_absent(tmp_path: Path):
    storage = _make_base(tmp_path, "base_a", ["Isabella", "Maria"])
    assert sim_utils.validate_personas(None, None, "base_a", storage) is None


def test_rejects_empty_personas_list(tmp_path: Path):
    storage = _make_base(tmp_path, "base_a", ["Isabella", "Maria"])
    err = sim_utils.validate_personas([], "Isabella", "base_a", storage)
    assert err == "personas must not be empty."


def test_rejects_unknown_personas(tmp_path: Path):
    storage = _make_base(tmp_path, "base_a", ["Isabella", "Maria"])
    err = sim_utils.validate_personas(["Isabella", "Ghost"], "Isabella", "base_a", storage)
    assert "unknown personas" in err
    assert "Ghost" in err


def test_rejects_missing_inner_voice_when_personas_given(tmp_path: Path):
    storage = _make_base(tmp_path, "base_a", ["Isabella", "Maria"])
    err = sim_utils.validate_personas(["Isabella"], None, "base_a", storage)
    assert err == "inner_voice must be one of the selected personas."


def test_rejects_inner_voice_outside_selection(tmp_path: Path):
    storage = _make_base(tmp_path, "base_a", ["Isabella", "Maria"])
    err = sim_utils.validate_personas(["Isabella"], "Maria", "base_a", storage)
    assert err == "inner_voice must be one of the selected personas."


def test_accepts_valid_subset(tmp_path: Path):
    storage = _make_base(tmp_path, "base_a", ["Isabella", "Maria", "Klaus"])
    assert sim_utils.validate_personas(["Isabella", "Klaus"], "Klaus", "base_a", storage) is None


def test_fork_meta_missing_returns_error(tmp_path: Path):
    storage = tmp_path / "storage"
    storage.mkdir()
    err = sim_utils.validate_personas(["Isabella"], "Isabella", "base_missing", storage)
    assert "meta.json" in err.lower() or "not found" in err.lower()
