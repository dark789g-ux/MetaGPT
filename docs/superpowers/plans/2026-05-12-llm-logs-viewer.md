# LLM Logs Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture every LLM call from Stanford Town simulations to a JSONL file and expose a Django page that streams/filters those records.

**Architecture:** Wrap the single LLM chokepoint (`STAction._aask` / `_run_gpt35_max_tokens`) with a contextvars-based logger that appends one JSON line per call to `storage/<sim_code>/llm_logs.jsonl`. Frontend is a new Django page that polls a byte-offset tail API every 1.5s; replay and live use the same file.

**Tech Stack:** Python 3.10+, asyncio, contextvars, Django 2.2 (existing frontend stack), vanilla JS + Bootstrap (existing base.html), pytest.

**Spec:** [docs/superpowers/specs/2026-05-12-llm-logs-viewer-design.md](../specs/2026-05-12-llm-logs-viewer-design.md)

---

## File Structure

**Create:**
- `metagpt/ext/stanford_town/utils/llm_logger.py` — context vars + `log_call` + file writer
- `tests/ext/stanford_town/utils/__init__.py` (if missing)
- `tests/ext/stanford_town/utils/test_llm_logger.py` — unit tests
- `examples/stanford_town/frontend/templates/llm_logs/llm_logs.html` — viewer page
- `examples/stanford_town/frontend/templates/llm_logs/` — directory

**Modify:**
- `metagpt/ext/stanford_town/actions/st_action.py:69-90` — wrap `_aask`, `_run_gpt35_max_tokens`
- `metagpt/ext/stanford_town/roles/st_role.py` — set sim_code/step/persona context in `_observe`
- `examples/stanford_town/run_st_game.py:58-77` — set sim_code on startup
- `examples/stanford_town/frontend/translator/views.py` — `llm_logs_page` + `llm_logs_tail`
- `examples/stanford_town/frontend/frontend_server/urls.py` — two routes
- `examples/stanford_town/frontend/templates/home/home.html:5-7` — entry link
- `qa/replay_ui_code_map.md` — register new page

---

## Task 1: llm_logger module — context + log_call

**Files:**
- Create: `metagpt/ext/stanford_town/utils/llm_logger.py`
- Create: `tests/ext/stanford_town/utils/__init__.py`
- Create: `tests/ext/stanford_town/utils/test_llm_logger.py`

- [ ] **Step 1: Write failing tests**

Create `tests/ext/stanford_town/utils/__init__.py` (empty file).

Create `tests/ext/stanford_town/utils/test_llm_logger.py`:

```python
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
```

- [ ] **Step 2: Verify tests fail**

Run: `pytest tests/ext/stanford_town/utils/test_llm_logger.py -v`
Expected: FAIL — `llm_logger` module not found.

- [ ] **Step 3: Implement llm_logger.py**

Create `metagpt/ext/stanford_town/utils/llm_logger.py`:

```python
"""Append-only JSONL logger for every LLM call inside a Stanford Town sim.

The logger sits inside STAction's LLM chokepoint and writes one line per call
to <STORAGE_PATH>/<sim_code>/llm_logs.jsonl. Step / persona / action are kept
in contextvars so the call sites do not have to thread them through.

Behavior:
- If set_sim_code has not been called, log_call is a no-op (safe for unit tests
  and for code paths that exercise STAction outside a sim).
- File is opened, written, flushed, and closed per call; stanford_town runs at
  ~one LLM call per few seconds so the sync overhead is negligible.
"""
from __future__ import annotations

import itertools
import json
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from metagpt.ext.stanford_town.utils.const import STORAGE_PATH
from metagpt.logs import logger

_sim_code: ContextVar[Optional[str]] = ContextVar("st_llm_sim_code", default=None)
_step: ContextVar[Optional[int]] = ContextVar("st_llm_step", default=None)
_persona: ContextVar[Optional[str]] = ContextVar("st_llm_persona", default=None)
_action: ContextVar[Optional[str]] = ContextVar("st_llm_action", default=None)

_seq = itertools.count()


def _reset_for_tests() -> None:
    """Reset module-level state. Tests only."""
    global _seq
    _seq = itertools.count()
    _sim_code.set(None)
    _step.set(None)
    _persona.set(None)
    _action.set(None)


def set_sim_code(sim_code: str) -> None:
    _sim_code.set(sim_code)


def set_step(step: int) -> None:
    _step.set(step)


def set_persona(persona: Optional[str]) -> None:
    _persona.set(persona)


def set_action(action_cls_name: Optional[str]) -> None:
    _action.set(action_cls_name)


def log_call(
    *,
    prompt: str,
    response: Optional[str],
    model: Optional[str],
    params: dict,
    usage: Optional[dict],
    cost_usd: Optional[float],
    latency_ms: int,
    retry_idx: int,
    used_fail_default: bool,
    error: Optional[str],
) -> None:
    sim_code = _sim_code.get()
    if not sim_code:
        return

    record: dict[str, Any] = {
        "seq": next(_seq),
        "ts": datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds"),
        "step": _step.get(),
        "persona": _persona.get(),
        "action": _action.get(),
        "model": model,
        "params": params,
        "prompt": prompt,
        "response": response,
        "usage": usage,
        "cost_usd": cost_usd,
        "latency_ms": latency_ms,
        "retry_idx": retry_idx,
        "used_fail_default": used_fail_default,
        "error": error,
    }

    out_dir = Path(STORAGE_PATH) / sim_code
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        with (out_dir / "llm_logs.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False))
            f.write("\n")
            f.flush()
    except Exception as exc:  # never let logging take down a sim
        logger.warning(f"llm_logger.log_call failed: {exc}")
```

- [ ] **Step 4: Verify tests pass**

Run: `pytest tests/ext/stanford_town/utils/test_llm_logger.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add metagpt/ext/stanford_town/utils/llm_logger.py tests/ext/stanford_town/utils/__init__.py tests/ext/stanford_town/utils/test_llm_logger.py
git commit -m "feat(stanford_town): add llm_logger module for jsonl call capture"
```

---

## Task 2: Wrap STAction._aask

**Files:**
- Modify: `metagpt/ext/stanford_town/actions/st_action.py:69-70`
- Test: extend `tests/ext/stanford_town/utils/test_llm_logger.py` (or new file)

- [ ] **Step 1: Write failing test**

Append to `tests/ext/stanford_town/utils/test_llm_logger.py`:

```python
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from metagpt.ext.stanford_town.actions.st_action import STAction


class _DummyAction(STAction):
    name: str = "Dummy"

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
```

- [ ] **Step 2: Verify tests fail**

Run: `pytest tests/ext/stanford_town/utils/test_llm_logger.py -v -k "aask_logs"`
Expected: FAIL — logs file does not exist (no wrapping yet).

- [ ] **Step 3: Wrap `_aask` in `st_action.py`**

Replace lines 69-70 in `metagpt/ext/stanford_town/actions/st_action.py`:

```python
    async def _aask(self, prompt: str) -> str:
        import time as _time
        from metagpt.ext.stanford_town.utils import llm_logger as _llm_logger

        _llm_logger.set_action(self.cls_name)
        t0 = _time.monotonic()
        response: Optional[str] = None
        error: Optional[str] = None
        try:
            response = await self.llm.aask(prompt)
            return response
        except Exception as exc:
            error = repr(exc)
            raise
        finally:
            cfg_llm = getattr(self.config, "llm", None)
            params = {
                "temperature": getattr(cfg_llm, "temperature", None),
                "max_tokens": getattr(cfg_llm, "max_token", None),
            }
            _llm_logger.log_call(
                prompt=prompt,
                response=response,
                model=getattr(cfg_llm, "model", None),
                params=params,
                usage=None,
                cost_usd=None,
                latency_ms=int((_time.monotonic() - t0) * 1000),
                retry_idx=0,
                used_fail_default=False,
                error=error,
            )
```

Note: `usage` and `cost_usd` stay `None` for now; Task 5 fills them.

- [ ] **Step 4: Verify tests pass**

Run: `pytest tests/ext/stanford_town/utils/test_llm_logger.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add metagpt/ext/stanford_town/actions/st_action.py tests/ext/stanford_town/utils/test_llm_logger.py
git commit -m "feat(stanford_town): log every STAction._aask call to llm_logger"
```

---

## Task 3: Wrap _run_gpt35_max_tokens with retry_idx & used_fail_default

**Files:**
- Modify: `metagpt/ext/stanford_town/actions/st_action.py:72-90`
- Test: extend `tests/ext/stanford_town/utils/test_llm_logger.py`

- [ ] **Step 1: Write failing test**

Append to `tests/ext/stanford_town/utils/test_llm_logger.py`:

```python
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
```

Set `_DummyAction.fail_default_resp = "DEFAULT"` at class level — add to its definition above:

```python
class _DummyAction(STAction):
    name: str = "Dummy"
    fail_default_resp: str = "DEFAULT"
    ...
```

- [ ] **Step 2: Verify test fails**

Run: `pytest tests/ext/stanford_town/utils/test_llm_logger.py::test_run_gpt35_max_tokens_logs_each_retry_and_fail_default -v`
Expected: FAIL — `retry_idx` always 0 / no `used_fail_default=True` record.

- [ ] **Step 3: Modify `_run_gpt35_max_tokens`**

Replace `_run_gpt35_max_tokens` body (lines 72-90) in `metagpt/ext/stanford_town/actions/st_action.py`:

```python
    async def _run_gpt35_max_tokens(self, prompt: str, max_tokens: int = 50, retry: int = 3):
        from metagpt.ext.stanford_town.utils import llm_logger as _llm_logger

        strict_prompt = prompt.rstrip() + GPT35_STRICT_SUFFIX
        effective_max_tokens = max(max_tokens, GPT35_MIN_MAX_TOKENS)
        for idx in range(retry):
            try:
                tmp_max_tokens_rsp = getattr(self.config.llm, "max_token", 1500)
                setattr(self.config.llm, "max_token", effective_max_tokens)
                self.llm.use_system_prompt = False

                # _aask logs itself; we tag the latest log record's retry_idx after the fact
                # by writing a second pseudo-record only when validation fails. Simpler: rely on
                # the per-attempt _aask log + a marker record on fail_default below.
                _llm_logger.set_action(self.cls_name)
                llm_resp = await self._aask(strict_prompt)

                setattr(self.config.llm, "max_token", tmp_max_tokens_rsp)
                logger.info(f"Action: {self.cls_name} llm _run_gpt35_max_tokens raw resp: {llm_resp}")
                if self._func_validate(llm_resp, prompt):
                    return self._func_cleanup(llm_resp, prompt)
                # validation failed → record retry index marker
                _llm_logger.log_call(
                    prompt="", response=llm_resp, model=getattr(self.config.llm, "model", None),
                    params={"max_tokens": effective_max_tokens},
                    usage=None, cost_usd=None, latency_ms=0,
                    retry_idx=idx, used_fail_default=False,
                    error="func_validate returned False",
                )
            except Exception as exp:
                logger.warning(f"Action: {self.cls_name} _run_gpt35_max_tokens exp: {exp}")
                _llm_logger.log_call(
                    prompt="", response=None, model=getattr(self.config.llm, "model", None),
                    params={"max_tokens": effective_max_tokens},
                    usage=None, cost_usd=None, latency_ms=0,
                    retry_idx=idx, used_fail_default=False,
                    error=repr(exp),
                )
                time.sleep(5)
        _llm_logger.log_call(
            prompt="", response=self.fail_default_resp,
            model=getattr(self.config.llm, "model", None),
            params={}, usage=None, cost_usd=None, latency_ms=0,
            retry_idx=retry, used_fail_default=True, error=None,
        )
        return self.fail_default_resp
```

- [ ] **Step 4: Verify all tests pass**

Run: `pytest tests/ext/stanford_town/utils/test_llm_logger.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add metagpt/ext/stanford_town/actions/st_action.py tests/ext/stanford_town/utils/test_llm_logger.py
git commit -m "feat(stanford_town): record retry_idx and used_fail_default in llm logs"
```

---

## Task 4: Inject sim_code / step / persona context in run_st_game and STRole

**Files:**
- Modify: `examples/stanford_town/run_st_game.py` (around line 76, after `write_curr_sim_code`)
- Modify: `metagpt/ext/stanford_town/roles/st_role.py:172` (`_observe` entry)

- [ ] **Step 1: Set sim_code in run_st_game.py**

In `examples/stanford_town/run_st_game.py`, add this import near the top with the other metagpt imports:

```python
from metagpt.ext.stanford_town.utils import llm_logger
```

And right after the existing `write_curr_sim_code({"sim_code": sim_code}, temp_storage_path)` line (currently line 76), add:

```python
    llm_logger.set_sim_code(sim_code)
```

- [ ] **Step 2: Set step/persona in STRole._observe**

In `metagpt/ext/stanford_town/roles/st_role.py`, add to the existing imports:

```python
from metagpt.ext.stanford_town.utils import llm_logger
```

Modify `_observe` (line 172) — insert at the very top of the method, before the `if not self.rc.env: return 0`:

```python
    async def _observe(self) -> int:
        llm_logger.set_step(self.step)
        llm_logger.set_persona(self.name)
        if not self.rc.env:
            return 0
        ...  # rest unchanged
```

- [ ] **Step 3: Smoke test — run minimal sim, inspect jsonl**

Run from the project root (replace `<fork>` with an existing sim under `examples/stanford_town/storage/`):

```bash
python examples/stanford_town/run_st_game.py "test idea" <fork> smoke_sim --n_round=2 --investment=5
```

Expected: file `examples/stanford_town/storage/smoke_sim/llm_logs.jsonl` exists and contains JSON lines where `step`, `persona`, and `action` are populated (not null).

Quick check:

```bash
head -3 examples/stanford_town/storage/smoke_sim/llm_logs.jsonl | python -c "import sys, json; [print(json.loads(l)['action'], json.loads(l)['persona'], json.loads(l)['step']) for l in sys.stdin]"
```

- [ ] **Step 4: Commit**

```bash
git add examples/stanford_town/run_st_game.py metagpt/ext/stanford_town/roles/st_role.py
git commit -m "feat(stanford_town): inject sim_code/step/persona into llm_logger context"
```

---

## Task 5: Capture token usage and cost (best-effort)

**Files:**
- Modify: `metagpt/ext/stanford_town/actions/st_action.py` (the `_aask` wrapper from Task 2)

- [ ] **Step 1: Inspect available cost manager**

Run: `grep -rn "CostManager\|update_cost\|total_prompt_tokens" metagpt/utils/cost_manager.py | head -20`

Read the file to find a snapshot/read method (likely `self.llm.cost_manager` with attributes like `total_prompt_tokens` / `total_completion_tokens` and `total_cost`).

- [ ] **Step 2: Capture deltas around the _aask call**

Update the `_aask` wrapper from Task 2 to snapshot before/after:

```python
    async def _aask(self, prompt: str) -> str:
        import time as _time
        from metagpt.ext.stanford_town.utils import llm_logger as _llm_logger

        _llm_logger.set_action(self.cls_name)
        t0 = _time.monotonic()
        response: Optional[str] = None
        error: Optional[str] = None

        cm = getattr(self.llm, "cost_manager", None)
        pre_prompt_tokens = getattr(cm, "total_prompt_tokens", 0) if cm else 0
        pre_completion_tokens = getattr(cm, "total_completion_tokens", 0) if cm else 0
        pre_cost = getattr(cm, "total_cost", 0.0) if cm else 0.0

        try:
            response = await self.llm.aask(prompt)
            return response
        except Exception as exc:
            error = repr(exc)
            raise
        finally:
            cfg_llm = getattr(self.config, "llm", None)
            params = {
                "temperature": getattr(cfg_llm, "temperature", None),
                "max_tokens": getattr(cfg_llm, "max_token", None),
            }
            usage = None
            cost_usd = None
            if cm:
                dp = getattr(cm, "total_prompt_tokens", 0) - pre_prompt_tokens
                dc = getattr(cm, "total_completion_tokens", 0) - pre_completion_tokens
                if dp or dc:
                    usage = {"prompt_tokens": dp, "completion_tokens": dc, "total_tokens": dp + dc}
                d_cost = getattr(cm, "total_cost", 0.0) - pre_cost
                if d_cost:
                    cost_usd = round(d_cost, 6)
            _llm_logger.log_call(
                prompt=prompt, response=response,
                model=getattr(cfg_llm, "model", None),
                params=params, usage=usage, cost_usd=cost_usd,
                latency_ms=int((_time.monotonic() - t0) * 1000),
                retry_idx=0, used_fail_default=False, error=error,
            )
```

- [ ] **Step 3: Run existing tests**

Run: `pytest tests/ext/stanford_town/utils/test_llm_logger.py -v`
Expected: 7 passed (existing tests pass `usage=None`-equivalent path since mock LLM has no `cost_manager`).

- [ ] **Step 4: Commit**

```bash
git add metagpt/ext/stanford_town/actions/st_action.py
git commit -m "feat(stanford_town): record token usage and cost delta per LLM call"
```

---

## Task 6: Backend — `/llm_logs/<sim_code>/tail` JSON API

**Files:**
- Modify: `examples/stanford_town/frontend/translator/views.py`
- Modify: `examples/stanford_town/frontend/frontend_server/urls.py`

- [ ] **Step 1: Add tail view**

Append to `examples/stanford_town/frontend/translator/views.py`:

```python
import json as _json
import time as _time
from pathlib import Path as _Path

from django.http import JsonResponse, Http404
from django.conf import settings as _settings
from django.shortcuts import render as _render


def _llm_logs_path(sim_code: str) -> _Path:
    # Mirrors metagpt.ext.stanford_town.utils.const.STORAGE_PATH
    return _Path(_settings.BASE_DIR).parent / "storage" / sim_code / "llm_logs.jsonl"


def _curr_sim_code() -> str | None:
    try:
        p = _Path(_settings.BASE_DIR).parent / "temp_storage" / "curr_sim_code.json"
        return _json.loads(p.read_text(encoding="utf-8")).get("sim_code")
    except Exception:
        return None


def llm_logs_tail(request, sim_code: str):
    try:
        offset = int(request.GET.get("offset", "0"))
    except ValueError:
        offset = 0
    try:
        limit = int(request.GET.get("limit", "0")) or None
    except ValueError:
        limit = None

    path = _llm_logs_path(sim_code)
    if not path.exists():
        return JsonResponse({"next_offset": 0, "eof": True, "is_live": False, "entries": []})

    size = path.stat().st_size

    # offset = -1 → tail mode: return the last `limit` (default 200) entries
    if offset < 0:
        n = limit or 200
        with path.open("rb") as f:
            f.seek(0, 2)
            end = f.tell()
            block = 65536
            data = b""
            pos = end
            while pos > 0 and data.count(b"\n") <= n + 1:
                read = min(block, pos)
                pos -= read
                f.seek(pos)
                data = f.read(read) + data
            lines = data.splitlines()[-n:]
            start_offset = end - sum(len(l) + 1 for l in lines)
    else:
        start_offset = min(offset, size)
        with path.open("rb") as f:
            f.seek(start_offset)
            lines = f.read().splitlines()

    entries = []
    for raw in lines:
        if not raw.strip():
            continue
        try:
            entries.append(_json.loads(raw.decode("utf-8")))
        except _json.JSONDecodeError:
            # half-written tail line: stop here so the client reads it next poll
            break

    consumed = sum(len(_json.dumps(e, ensure_ascii=False).encode("utf-8")) + 1 for e in entries)
    next_offset = start_offset + consumed if offset >= 0 else size

    mtime = path.stat().st_mtime
    is_live = (_curr_sim_code() == sim_code) and (_time.time() - mtime < 30)

    return JsonResponse(
        {"next_offset": next_offset, "eof": next_offset >= size, "is_live": is_live, "entries": entries},
        json_dumps_params={"ensure_ascii": False},
    )


def llm_logs_page(request, sim_code: str):
    return _render(request, "llm_logs/llm_logs.html", {"sim_code": sim_code})
```

Note on path: confirm `_settings.BASE_DIR` resolves to `examples/stanford_town/frontend/`. If not, hard-code via `Path(__file__).resolve().parents[2] / "storage"` instead. Verify in Step 2.

- [ ] **Step 2: Verify path resolution**

Run from `examples/stanford_town/frontend/`:

```bash
python -c "from frontend_server.settings.base import BASE_DIR; from pathlib import Path; print(Path(BASE_DIR).parent / 'storage')"
```

Expected: prints `…/examples/stanford_town/storage`. If wrong, switch to `Path(__file__).resolve().parents[2] / "storage"` in `_llm_logs_path` and `_curr_sim_code`.

- [ ] **Step 3: Register routes**

Modify `examples/stanford_town/frontend/frontend_server/urls.py` urlpatterns — add two lines before `path('admin/', ...)`:

```python
    re_path(r'^llm_logs/(?P<sim_code>[\w-]+)/$', translator_views.llm_logs_page, name='llm_logs_page'),
    re_path(r'^llm_logs/(?P<sim_code>[\w-]+)/tail$', translator_views.llm_logs_tail, name='llm_logs_tail'),
```

- [ ] **Step 4: Smoke test tail API**

Start the Django dev server (per existing project convention, e.g. `python launch_stanford_town.py` or `python manage.py runserver --noreload`).

Run from another shell, using the `smoke_sim` from Task 4:

```bash
curl 'http://127.0.0.1:8000/llm_logs/smoke_sim/tail?offset=-1&limit=5' | python -m json.tool | head -40
```

Expected: JSON with `entries` array of up to 5 records, each containing `seq`, `step`, `persona`, `prompt`, `response`.

- [ ] **Step 5: Commit**

```bash
git add examples/stanford_town/frontend/translator/views.py examples/stanford_town/frontend/frontend_server/urls.py
git commit -m "feat(stanford_town): add /llm_logs/<sim>/tail JSON API and page route"
```

---

## Task 7: Frontend — llm_logs.html viewer page

**Files:**
- Create: `examples/stanford_town/frontend/templates/llm_logs/llm_logs.html`

- [ ] **Step 1: Create the template**

Create directory `examples/stanford_town/frontend/templates/llm_logs/` and file `llm_logs.html`:

```html
{% extends "base.html" %}
{% load static %}

{% block content %}
<style>
  .log-row { border:1px solid #ddd; border-radius:6px; padding:8px 12px; margin-bottom:8px; background:#fafafa; }
  .log-row.expanded { background:#fff; }
  .log-summary { cursor:pointer; font-family:monospace; font-size:13px; display:flex; gap:12px; flex-wrap:wrap; }
  .log-summary .action { font-weight:600; color:#005599; }
  .log-summary .meta { color:#666; }
  .log-summary .latency-bad { color:#c00; }
  .log-body { display:none; margin-top:8px; }
  .log-row.expanded .log-body { display:block; }
  .log-section { background:#f4f4f4; border:1px solid #e0e0e0; border-radius:4px; padding:8px; margin-top:6px; }
  .log-section pre { margin:0; white-space:pre-wrap; word-break:break-word; max-height:400px; overflow:auto; font-size:12px; }
  .log-section .copy-btn { float:right; font-size:11px; }
  .live-dot { display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:6px; vertical-align:middle; }
  .live-dot.on { background:#4caf50; box-shadow:0 0 6px #4caf50; }
  .live-dot.off { background:#999; }
  .filters { background:#f0f0f0; padding:12px; border-radius:6px; margin-bottom:16px; }
  .filters label { margin-right:6px; font-weight:600; }
  .filters input, .filters select { margin-right:12px; }
</style>

<div style="max-width:1200px; margin:0 auto; padding:1em;">
  <h2>
    Stanford Town · LLM Logs
    <small class="text-muted">sim_code = <code>{{ sim_code }}</code></small>
    <span style="float:right; font-size:14px;">
      <span id="live-dot" class="live-dot off"></span><span id="live-text">offline</span>
    </span>
  </h2>

  <div class="filters">
    <label>Step</label>
    <input id="f-step-min" type="number" size="4" placeholder="min" style="width:70px">
    –
    <input id="f-step-max" type="number" size="4" placeholder="max" style="width:70px">

    <label>Persona</label>
    <select id="f-persona"><option value="">All</option></select>

    <label>Action</label>
    <select id="f-action"><option value="">All</option></select>

    <label><input id="f-failed" type="checkbox"> Only failed/retried</label>

    <label>Search</label>
    <input id="f-search" type="text" placeholder="prompt substring" style="width:220px">

    <button id="btn-clear" class="btn btn-default btn-sm">Clear</button>
    <button id="btn-pause" class="btn btn-default btn-sm">Pause autoscroll</button>
    <button id="btn-bottom" class="btn btn-default btn-sm">Jump to bottom</button>
    <button id="btn-earlier" class="btn btn-default btn-sm">Load earlier</button>
    <span id="count" style="margin-left:12px; color:#666;"></span>
  </div>

  <div id="log-list"></div>
</div>

<script>
(function () {
  const SIM = "{{ sim_code }}";
  const TAIL_URL = `/llm_logs/${SIM}/tail`;
  const POLL_MS = 1500;
  const INITIAL_LIMIT = 200;

  let entries = [];          // all loaded records, sorted by seq asc
  let earliestOffset = null; // byte offset of the earliest loaded entry
  let nextOffset = 0;        // next byte offset to fetch for tail
  let autoscroll = true;
  let polling = false;
  let pollTimer = null;

  const $ = (id) => document.getElementById(id);

  function fmtSummary(e) {
    const failed = e.used_fail_default || e.error || (e.retry_idx && e.retry_idx > 0);
    const tokens = e.usage ? `${e.usage.prompt_tokens}/${e.usage.completion_tokens}` : "?";
    const cost = e.cost_usd != null ? `$${e.cost_usd.toFixed(5)}` : "";
    const latencyClass = e.latency_ms > 3000 ? "latency-bad" : "";
    return `
      <span class="action">${e.action || "?"}</span>
      <span>· ${e.persona || "?"}</span>
      <span>· <a href="/replay/${SIM}/${e.step}/" target="_blank">step ${e.step}</a></span>
      <span class="meta ${latencyClass}">· ${e.latency_ms}ms</span>
      <span class="meta">· ${e.model || "?"}</span>
      <span class="meta">· tokens ${tokens}</span>
      <span class="meta">${cost}</span>
      ${failed ? '<span style="color:#c00;">· ⚠ failed/retry</span>' : ""}
    `;
  }

  function escapeHtml(s) {
    if (s == null) return "";
    return String(s).replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
  }

  function renderRow(e) {
    const row = document.createElement("div");
    row.className = "log-row";
    row.dataset.seq = e.seq;
    row.innerHTML = `
      <div class="log-summary">
        <span style="color:#999;">#${e.seq}</span>
        ${fmtSummary(e)}
      </div>
      <div class="log-body">
        <div class="log-section">
          <button class="btn btn-default btn-xs copy-btn" data-field="prompt">copy</button>
          <strong>PROMPT</strong>
          <pre>${escapeHtml(e.prompt)}</pre>
        </div>
        <div class="log-section">
          <button class="btn btn-default btn-xs copy-btn" data-field="response">copy</button>
          <strong>RESPONSE</strong>
          <pre>${escapeHtml(e.response)}</pre>
        </div>
        ${e.error ? `<div class="log-section" style="background:#fee;"><strong>ERROR</strong><pre>${escapeHtml(e.error)}</pre></div>` : ""}
        <div class="log-section" style="background:#eef;">
          <strong>META</strong>
          <pre>${escapeHtml(JSON.stringify({
            ts: e.ts, params: e.params, usage: e.usage, cost_usd: e.cost_usd,
            retry_idx: e.retry_idx, used_fail_default: e.used_fail_default
          }, null, 2))}</pre>
        </div>
      </div>
    `;
    row.querySelector(".log-summary").addEventListener("click", () => {
      row.classList.toggle("expanded");
    });
    row.querySelectorAll(".copy-btn").forEach(btn => {
      btn.addEventListener("click", (ev) => {
        ev.stopPropagation();
        const f = btn.dataset.field;
        navigator.clipboard.writeText(e[f] || "");
        btn.textContent = "copied";
        setTimeout(() => (btn.textContent = "copy"), 800);
      });
    });
    return row;
  }

  function passesFilter(e) {
    const sMin = $("f-step-min").value, sMax = $("f-step-max").value;
    if (sMin !== "" && e.step < +sMin) return false;
    if (sMax !== "" && e.step > +sMax) return false;
    const p = $("f-persona").value;
    if (p && e.persona !== p) return false;
    const a = $("f-action").value;
    if (a && e.action !== a) return false;
    if ($("f-failed").checked && !(e.used_fail_default || e.error || (e.retry_idx && e.retry_idx > 0))) return false;
    const q = $("f-search").value.trim().toLowerCase();
    if (q && !((e.prompt || "").toLowerCase().includes(q) || (e.response || "").toLowerCase().includes(q))) return false;
    return true;
  }

  function rerender() {
    const list = $("log-list");
    list.innerHTML = "";
    let shown = 0;
    for (const e of entries) {
      if (!passesFilter(e)) continue;
      list.appendChild(renderRow(e));
      shown++;
    }
    $("count").textContent = `${shown} / ${entries.length} entries`;
    if (autoscroll) window.scrollTo(0, document.body.scrollHeight);
  }

  function refreshDropdowns() {
    const personas = new Set(entries.map(e => e.persona).filter(Boolean));
    const actions = new Set(entries.map(e => e.action).filter(Boolean));
    const fillSelect = (id, values) => {
      const sel = $(id);
      const cur = sel.value;
      sel.innerHTML = '<option value="">All</option>' + [...values].sort().map(v => `<option>${v}</option>`).join("");
      sel.value = cur;
    };
    fillSelect("f-persona", personas);
    fillSelect("f-action", actions);
  }

  function mergeEntries(newEntries) {
    if (!newEntries.length) return;
    const seen = new Set(entries.map(e => e.seq));
    for (const e of newEntries) if (!seen.has(e.seq)) entries.push(e);
    entries.sort((a, b) => a.seq - b.seq);
  }

  async function fetchTail() {
    try {
      const url = nextOffset === 0 && entries.length === 0
        ? `${TAIL_URL}?offset=-1&limit=${INITIAL_LIMIT}`
        : `${TAIL_URL}?offset=${nextOffset}`;
      const resp = await fetch(url);
      const data = await resp.json();
      mergeEntries(data.entries);
      if (earliestOffset === null && data.entries.length) {
        earliestOffset = (nextOffset === 0) ? 0 : earliestOffset;
      }
      nextOffset = data.next_offset;
      $("live-dot").className = "live-dot " + (data.is_live ? "on" : "off");
      $("live-text").textContent = data.is_live ? "live" : "offline";
      refreshDropdowns();
      rerender();
      polling = data.is_live;
    } catch (err) {
      console.error("tail fetch failed", err);
    } finally {
      if (polling) pollTimer = setTimeout(fetchTail, POLL_MS);
    }
  }

  // Wire up controls
  ["f-step-min","f-step-max","f-persona","f-action","f-failed","f-search"].forEach(id => {
    $(id).addEventListener("input", rerender);
    $(id).addEventListener("change", rerender);
  });
  $("btn-clear").addEventListener("click", () => {
    ["f-step-min","f-step-max","f-search"].forEach(id => $(id).value = "");
    ["f-persona","f-action"].forEach(id => $(id).value = "");
    $("f-failed").checked = false;
    rerender();
  });
  $("btn-pause").addEventListener("click", (ev) => {
    autoscroll = !autoscroll;
    ev.target.textContent = autoscroll ? "Pause autoscroll" : "Resume autoscroll";
  });
  $("btn-bottom").addEventListener("click", () => window.scrollTo(0, document.body.scrollHeight));
  $("btn-earlier").addEventListener("click", () => {
    // Not implemented in v1: doubling INITIAL_LIMIT would require a different API call.
    alert("Load earlier: not implemented in v1. Increase INITIAL_LIMIT or open the jsonl file directly.");
  });

  // Boot
  polling = true;
  fetchTail();
})();
</script>
{% endblock content %}
```

- [ ] **Step 2: Browser smoke test**

With the Django dev server running and `smoke_sim` in place from Task 4, open:

```
http://127.0.0.1:8000/llm_logs/smoke_sim/
```

Manual checks:
- Page loads, shows `sim_code = smoke_sim`.
- Several log rows appear with summaries.
- Clicking a row expands it and shows the PROMPT / RESPONSE blocks.
- Persona and Action dropdowns are populated.
- Step link opens `/replay/smoke_sim/<step>/` in a new tab.
- The live dot is grey (sim already finished) and text says "offline".

- [ ] **Step 3: Live smoke test**

Launch a fresh sim and open `/llm_logs/<new_sim>/` while it runs.
- Live dot should turn green.
- New rows append every few seconds.
- Clicking "Pause autoscroll" stops jumping to bottom.

- [ ] **Step 4: Commit**

```bash
git add examples/stanford_town/frontend/templates/llm_logs/llm_logs.html
git commit -m "feat(stanford_town): add /llm_logs/<sim>/ viewer page"
```

---

## Task 8: Wire entry link into home.html

**Files:**
- Modify: `examples/stanford_town/frontend/templates/home/home.html:5-7`

- [ ] **Step 1: Add the link**

In `examples/stanford_town/frontend/templates/home/home.html`, replace lines 5-7:

```html
<h1 style="text-align:center; margin-top:1em; margin-bottom:0.2em; font-weight:600">
  生成式智能体 · 模拟回放
  <a href="{% url 'llm_logs_page' sim_code %}" target="_blank"
     style="font-size:0.5em; font-weight:400; margin-left:1em;">📋 LLM Logs</a>
</h1>
```

- [ ] **Step 2: Smoke test**

Reload `/replay/smoke_sim/0/` — verify the "📋 LLM Logs" link appears next to the title and opens the viewer page in a new tab.

- [ ] **Step 3: Commit**

```bash
git add examples/stanford_town/frontend/templates/home/home.html
git commit -m "feat(stanford_town): link to LLM logs viewer from replay page"
```

---

## Task 9: Update replay UI code map docs

**Files:**
- Modify: `qa/replay_ui_code_map.md`

- [ ] **Step 1: Add a new section**

Insert after the existing `## URL → 模板路径` table, add this row to the table:

```
| `/llm_logs/<sim_code>/` | `translator.views.llm_logs_page` | `templates/llm_logs/llm_logs.html` | (inline `<script>` in template) |
```

And append a new section:

```markdown
## LLM Logs 页（独立 Tab）

- 页面模板：[examples/stanford_town/frontend/templates/llm_logs/llm_logs.html](examples/stanford_town/frontend/templates/llm_logs/llm_logs.html)
- 页面视图：`translator.views.llm_logs_page`
- 增量 API：`GET /llm_logs/<sim_code>/tail?offset=<bytes>` → `translator.views.llm_logs_tail`
- 数据源：`examples/stanford_town/storage/<sim_code>/llm_logs.jsonl`（append-only，单文件）
- 后端埋点：
  - 写入器：[metagpt/ext/stanford_town/utils/llm_logger.py](metagpt/ext/stanford_town/utils/llm_logger.py)
  - 包装点：[metagpt/ext/stanford_town/actions/st_action.py](metagpt/ext/stanford_town/actions/st_action.py) 的 `_aask` 与 `_run_gpt35_max_tokens`
  - 上下文注入：`run_st_game.py` 设 sim_code；`STRole._observe` 设 step/persona
- 入口链接：`templates/home/home.html` 标题区右侧 "📋 LLM Logs"
```

- [ ] **Step 2: Commit**

```bash
git add qa/replay_ui_code_map.md
git commit -m "docs(stanford_town): register LLM Logs viewer in replay UI code map"
```

---

## Final Validation Checklist

- [ ] `pytest tests/ext/stanford_town/utils/test_llm_logger.py -v` → all green
- [ ] Smoke sim writes a non-empty `llm_logs.jsonl` with populated `step`, `persona`, `action`
- [ ] `/llm_logs/<sim>/tail?offset=-1&limit=5` returns valid JSON
- [ ] `/llm_logs/<sim>/` page renders, live dot reflects status, filters work, step links navigate to replay
- [ ] Replay page shows "📋 LLM Logs" link in header
- [ ] No new pip dependencies added (`git diff requirements*.txt` is empty)
