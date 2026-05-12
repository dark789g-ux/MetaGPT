import json
from pathlib import Path

import pytest

from metagpt.ext.stanford_town.utils import llm_logger


@pytest.fixture(autouse=True)
def _isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_logger, "STORAGE_PATH", tmp_path)
    llm_logger._reset_for_tests()
    yield


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_log_call_writes_jsonl(tmp_path):
    llm_logger.set_sim_code("sim_x")
    llm_logger.set_step(7)
    llm_logger.set_persona("Isabella")
    llm_logger.set_action("GenDailySchedule")

    llm_logger.log_call(
        prompt="P",
        response="R",
        model="deepseek-chat",
        params={"temperature": 0.7, "max_tokens": 1500},
        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        cost_usd=0.0001,
        latency_ms=42,
        retry_idx=0,
        used_fail_default=False,
        error=None,
    )

    path = tmp_path / "sim_x" / "llm_logs.jsonl"
    assert path.exists()
    rows = _read_jsonl(path)
    assert len(rows) == 1
    row = rows[0]
    assert row["seq"] == 0
    assert row["step"] == 7
    assert row["persona"] == "Isabella"
    assert row["action"] == "GenDailySchedule"
    assert row["model"] == "deepseek-chat"
    assert row["prompt"] == "P"
    assert row["response"] == "R"
    assert row["params"] == {"temperature": 0.7, "max_tokens": 1500}
    assert row["usage"]["total_tokens"] == 15
    assert row["cost_usd"] == 0.0001
    assert row["latency_ms"] == 42
    assert row["retry_idx"] == 0
    assert row["used_fail_default"] is False
    assert row["error"] is None
    assert "ts" in row


def test_log_call_creates_missing_dir(tmp_path):
    llm_logger.set_sim_code("brand_new_sim")
    llm_logger.log_call(
        prompt="p", response="r", model=None, params={}, usage=None,
        cost_usd=None, latency_ms=0, retry_idx=0, used_fail_default=False, error=None,
    )
    assert (tmp_path / "brand_new_sim" / "llm_logs.jsonl").exists()


def test_seq_monotonic(tmp_path):
    llm_logger.set_sim_code("sim_y")
    for _ in range(3):
        llm_logger.log_call(
            prompt="p", response="r", model=None, params={}, usage=None,
            cost_usd=None, latency_ms=0, retry_idx=0, used_fail_default=False, error=None,
        )
    rows = _read_jsonl(tmp_path / "sim_y" / "llm_logs.jsonl")
    assert [r["seq"] for r in rows] == [0, 1, 2]


def test_no_sim_code_is_noop(tmp_path):
    # No set_sim_code called -> log_call must not raise and must not write anywhere.
    llm_logger.log_call(
        prompt="p", response="r", model=None, params={}, usage=None,
        cost_usd=None, latency_ms=0, retry_idx=0, used_fail_default=False, error=None,
    )
    assert list(tmp_path.iterdir()) == []
