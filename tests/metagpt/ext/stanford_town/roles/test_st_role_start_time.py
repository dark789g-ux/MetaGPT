"""Unit tests for STRole.check_start_time validator."""
from datetime import datetime

import pytest

from metagpt.ext.stanford_town.roles.st_role import STRole


def test_check_start_time_accepts_bare_date():
    """Legacy meta.json shape: 'February 13, 2023'."""
    dt = STRole.check_start_time("February 13, 2023")
    assert dt == datetime(2023, 2, 13, 0, 0, 0)


def test_check_start_time_accepts_full_datetime():
    """New meta.json shape: 'February 13, 2023, 14:30:00'."""
    dt = STRole.check_start_time("February 13, 2023, 14:30:00")
    assert dt == datetime(2023, 2, 13, 14, 30, 0)


def test_check_start_time_rejects_garbage():
    with pytest.raises(ValueError):
        STRole.check_start_time("not a date")
