"""Verify start_backend appends --start_hms to the spawned CLI when set."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

FRONTEND_DIR = Path(__file__).resolve().parents[5] / "examples" / "stanford_town" / "frontend"
sys.path.insert(0, str(FRONTEND_DIR))

from translator import sim_utils  # noqa: E402


def _captured_cmd(start_hms, tmp_path):
    """Spawn start_backend with mocked Popen; return the cmd list it was called with."""
    fake_proc = MagicMock()
    fake_proc.stdout = MagicMock()
    fake_proc.stdout.readline = MagicMock(return_value=b"")
    with patch.object(sim_utils.subprocess, "Popen", return_value=fake_proc) as mock_pop:
        sim_utils.start_backend(
            idea="x",
            sim_code="new_sim",
            fork_sim_code="base",
            n_round=1,
            investment=None,
            st_root=tmp_path,
            log_dir=tmp_path / "logs",
            start_hms=start_hms,
        )
    return mock_pop.call_args.args[0]


def test_start_backend_appends_start_hms_when_set(tmp_path):
    cmd = _captured_cmd("14:30:00", tmp_path)
    assert "--start_hms" in cmd
    assert cmd[cmd.index("--start_hms") + 1] == "14:30:00"


def test_start_backend_omits_start_hms_when_none(tmp_path):
    cmd = _captured_cmd(None, tmp_path)
    assert "--start_hms" not in cmd


def test_start_backend_omits_start_hms_when_empty(tmp_path):
    cmd = _captured_cmd("", tmp_path)
    assert "--start_hms" not in cmd
