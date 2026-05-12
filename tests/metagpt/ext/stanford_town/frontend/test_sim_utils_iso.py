"""Unit tests for sim_utils._to_iso and list_simulations ISO formatting."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

FRONTEND_DIR = Path(__file__).resolve().parents[5] / "examples" / "stanford_town" / "frontend"
sys.path.insert(0, str(FRONTEND_DIR))

from translator import sim_utils  # noqa: E402


def test_to_iso_full_datetime():
    assert sim_utils._to_iso("February 13, 2023, 14:30:00", with_time=True) == "2023-02-13 14:30:00"


def test_to_iso_bare_date():
    assert sim_utils._to_iso("February 13, 2023", with_time=False) == "2023-02-13 00:00:00"


def test_to_iso_empty_returns_empty():
    assert sim_utils._to_iso("", with_time=True) == ""
    assert sim_utils._to_iso("", with_time=False) == ""


def test_to_iso_malformed_returns_empty():
    assert sim_utils._to_iso("not a date", with_time=True) == ""
    assert sim_utils._to_iso("February 13, 2023, 14:30", with_time=True) == ""


def _make_meta(tmp_path: Path, sim_code: str, meta: dict) -> Path:
    storage = tmp_path / "storage"
    reverie = storage / sim_code / "reverie"
    reverie.mkdir(parents=True)
    (reverie / "meta.json").write_text(json.dumps(meta))
    return storage


def test_list_simulations_new_shape(tmp_path: Path):
    storage = _make_meta(tmp_path, "new_sim", {
        "fork_sim_code": "base",
        "start_date": "February 13, 2023",
        "start_time": "February 13, 2023, 14:30:00",
        "curr_time": "February 13, 2023, 15:00:10",
        "persona_names": ["Isabella"],
        "step": 18,
    })
    rows = sim_utils.list_simulations(storage)
    assert len(rows) == 1
    r = rows[0]
    assert r["start_time"] == "2023-02-13 14:30:00"
    assert r["cur_time"] == "2023-02-13 15:00:10"


def test_list_simulations_old_shape_falls_back(tmp_path: Path):
    """Old archives lack start_time; fall back to start_date + 00:00:00."""
    storage = _make_meta(tmp_path, "old_sim", {
        "fork_sim_code": "base",
        "start_date": "February 13, 2023",
        "curr_time": "February 13, 2023, 03:14:20",
        "persona_names": ["Isabella"],
        "step": 5,
    })
    rows = sim_utils.list_simulations(storage)
    assert rows[0]["start_time"] == "2023-02-13 00:00:00"
    assert rows[0]["cur_time"] == "2023-02-13 03:14:20"


def test_list_simulations_missing_curr_time_is_blank(tmp_path: Path):
    storage = _make_meta(tmp_path, "no_curr", {
        "fork_sim_code": "base",
        "start_date": "February 13, 2023",
        "persona_names": ["Isabella"],
        "step": 0,
    })
    rows = sim_utils.list_simulations(storage)
    assert rows[0]["cur_time"] == ""
