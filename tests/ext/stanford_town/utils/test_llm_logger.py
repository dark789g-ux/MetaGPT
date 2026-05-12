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


import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from metagpt.ext.stanford_town.actions.st_action import STAction


class _DummyAction(STAction):
    name: str = "Dummy"
    fail_default_resp: str = "DEFAULT"

    def _func_validate(self, llm_resp, prompt):
        return True

    def _func_cleanup(self, llm_resp, prompt):
        return llm_resp

    def _func_fail_default_resp(self):
        return "DEFAULT"


def _make_action_with_mock_llm(response="OK", raises=None):
    action = _DummyAction()
    llm = SimpleNamespace(
        aask=AsyncMock(side_effect=raises) if raises else AsyncMock(return_value=response),
        use_system_prompt=True,
    )
    cfg_llm = SimpleNamespace(model="deepseek-chat", temperature=0.7, max_token=1500)
    object.__setattr__(action, "_llm_for_test", llm)
    type(action).llm = property(lambda self: self._llm_for_test)
    object.__setattr__(action, "_cfg_for_test", SimpleNamespace(llm=cfg_llm))
    type(action).config = property(lambda self: self._cfg_for_test)
    return action


def test_aask_logs_on_success(tmp_path):
    llm_logger.set_sim_code("sim_aask")
    action = _make_action_with_mock_llm(response="hello")
    result = asyncio.run(action._aask("hi"))
    assert result == "hello"
    rows = _read_jsonl(tmp_path / "sim_aask" / "llm_logs.jsonl")
    assert len(rows) == 1
    assert rows[0]["prompt"] == "hi"
    assert rows[0]["response"] == "hello"
    assert rows[0]["action"] == "_DummyAction"
    assert rows[0]["model"] == "deepseek-chat"
    assert rows[0]["error"] is None


def test_aask_logs_on_error(tmp_path):
    llm_logger.set_sim_code("sim_err")
    action = _make_action_with_mock_llm(raises=RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        asyncio.run(action._aask("hi"))
    rows = _read_jsonl(tmp_path / "sim_err" / "llm_logs.jsonl")
    assert len(rows) == 1
    assert rows[0]["response"] is None
    assert "boom" in rows[0]["error"]


def test_run_gpt35_max_tokens_logs_each_retry_and_fail_default(tmp_path, monkeypatch):
    llm_logger.set_sim_code("sim_retry")
    action = _make_action_with_mock_llm(raises=RuntimeError("fail"))
    monkeypatch.setattr("metagpt.ext.stanford_town.actions.st_action.time.sleep", lambda *_: None)
    result = asyncio.run(action._run_gpt35_max_tokens("prompt-x", max_tokens=64, retry=2))
    assert result == "DEFAULT"  # _func_fail_default_resp via fail_default_resp
    rows = _read_jsonl(tmp_path / "sim_retry" / "llm_logs.jsonl")
    # 2 retries (each producing a _aask log with retry_idx=0 inside _aask) + 1 fail_default record
    # _aask logs the call attempt; _run_gpt35_max_tokens adds a separate retry_idx record on top.
    # We assert at least one record has used_fail_default=True.
    assert any(r["used_fail_default"] for r in rows)
    # And the per-retry records carry retry_idx 0 and 1.
    retry_indices = sorted({r["retry_idx"] for r in rows if not r["used_fail_default"]})
    assert retry_indices == [0, 1]
