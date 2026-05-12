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
