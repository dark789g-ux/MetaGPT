# Dashboard `start_time` + `cur_time` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add second-precision `start_time` + new `cur_time` columns to the Stanford Town dashboard's "已有存档" table (ISO format), and let users pick a starting `HH:MM:SS` when launching a sim.

**Architecture:** Internal datetimes stay in long-English format (`%B %d, %Y, %H:%M:%S`) to preserve reverie compatibility; ISO is display-only. A new `start_time` field is added to `meta.json` at sim creation; old archives fall back to `start_date + ", 00:00:00"` at read time. User-chosen HMS flows form → views → CLI → `run_st_game.py`, which rewrites the copied `meta.json`.

**Tech Stack:** Python 3.10+, Django (frontend server), pydantic (STRole), pytest, vanilla JS, Bootstrap 3.

**Spec:** [docs/superpowers/specs/2026-05-12-dashboard-start-time-cur-time-design.md](../specs/2026-05-12-dashboard-start-time-cur-time-design.md)

---

## File Map

| File | Change |
|---|---|
| `metagpt/ext/stanford_town/roles/st_role.py` | `check_start_time` validator accepts long-datetime input |
| `examples/stanford_town/frontend/translator/sim_utils.py` | new `_to_iso` helper; `list_simulations` returns ISO `start_time` + `cur_time`; `start_backend` accepts `start_hms` |
| `examples/stanford_town/run_st_game.py` | new `--start_hms` CLI flag; rewrites `meta.json` `start_time` + `curr_time` on launch |
| `examples/stanford_town/frontend/translator/views.py` | `start_simulation` reads + validates `start_hms`, passes to `start_backend`; `landing` view exposes `sim_curr_times` map |
| `examples/stanford_town/frontend/templates/landing/landing.html` | table column rename + new `cur_time` column; form `<input type="time">`; JS default from fork base's `curr_time` |
| `tests/metagpt/ext/stanford_town/roles/test_st_role_start_time.py` | NEW — validator unit tests |
| `tests/metagpt/ext/stanford_town/frontend/test_sim_utils_iso.py` | NEW — `_to_iso` + `list_simulations` format tests |
| `tests/metagpt/ext/stanford_town/frontend/test_sim_utils_start_hms.py` | NEW — `start_backend` HMS arg-passing test |

---

## Task 1: `STRole.check_start_time` accepts long-datetime input

**Files:**
- Modify: `metagpt/ext/stanford_town/roles/st_role.py:89-92`
- Test: `tests/metagpt/ext/stanford_town/roles/test_st_role_start_time.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `tests/metagpt/ext/stanford_town/roles/test_st_role_start_time.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/metagpt/ext/stanford_town/roles/test_st_role_start_time.py -v`
Expected: `test_check_start_time_accepts_full_datetime` FAILS (`ValueError: unconverted data remains: , 14:30:00` or similar). The other two pass already.

- [ ] **Step 3: Update the validator**

Replace lines 89-92 in `metagpt/ext/stanford_town/roles/st_role.py`:

```python
    @field_validator("start_time", mode="before")
    @classmethod
    def check_start_time(cls, start_time: str) -> datetime:
        # Accept either bare-date (legacy) or full long-English datetime (new).
        try:
            return datetime.strptime(start_time, "%B %d, %Y, %H:%M:%S")
        except ValueError:
            return datetime.strptime(f"{start_time}, 00:00:00", "%B %d, %Y, %H:%M:%S")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/metagpt/ext/stanford_town/roles/test_st_role_start_time.py -v`
Expected: all 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add metagpt/ext/stanford_town/roles/st_role.py tests/metagpt/ext/stanford_town/roles/test_st_role_start_time.py
git commit -m "feat(stanford_town): STRole.check_start_time accepts long-datetime input"
```

---

## Task 2: `sim_utils._to_iso` helper

**Files:**
- Modify: `examples/stanford_town/frontend/translator/sim_utils.py` (add helper near top)
- Test: `tests/metagpt/ext/stanford_town/frontend/test_sim_utils_iso.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `tests/metagpt/ext/stanford_town/frontend/test_sim_utils_iso.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/metagpt/ext/stanford_town/frontend/test_sim_utils_iso.py -v`
Expected: all 4 FAIL with `AttributeError: module ... has no attribute '_to_iso'`.

- [ ] **Step 3: Add `_to_iso` to sim_utils.py**

Insert after the `_SIM_CODE_RE` constant (around line 26) in `examples/stanford_town/frontend/translator/sim_utils.py`:

```python
def _to_iso(s: str, with_time: bool) -> str:
    """Long-English datetime → ISO 'YYYY-MM-DD HH:MM:SS'. Returns '' on parse failure."""
    if not s:
        return ""
    fmt = "%B %d, %Y, %H:%M:%S" if with_time else "%B %d, %Y"
    try:
        dt = datetime.strptime(s, fmt)
    except ValueError:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M:%S")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/metagpt/ext/stanford_town/frontend/test_sim_utils_iso.py -v`
Expected: all 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add examples/stanford_town/frontend/translator/sim_utils.py tests/metagpt/ext/stanford_town/frontend/test_sim_utils_iso.py
git commit -m "feat(stanford_town): add _to_iso helper for ISO datetime formatting"
```

---

## Task 3: `list_simulations` exposes ISO `start_time` + `cur_time`

**Files:**
- Modify: `examples/stanford_town/frontend/translator/sim_utils.py:69-81`
- Test: append to `tests/metagpt/ext/stanford_town/frontend/test_sim_utils_iso.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/metagpt/ext/stanford_town/frontend/test_sim_utils_iso.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/metagpt/ext/stanford_town/frontend/test_sim_utils_iso.py -v -k list_simulations`
Expected: all 3 FAIL with `KeyError: 'start_time'` or `KeyError: 'cur_time'`.

- [ ] **Step 3: Update the row dict in `list_simulations`**

Replace lines 69-81 of `examples/stanford_town/frontend/translator/sim_utils.py`:

```python
        raw_start_time = meta.get("start_time", "")
        if raw_start_time:
            start_iso = _to_iso(raw_start_time, with_time=True)
        else:
            start_iso = _to_iso(meta.get("start_date", ""), with_time=False)
        cur_iso = _to_iso(meta.get("curr_time", ""), with_time=True)

        rows.append({
            "sim_code": entry.name,
            "fork_sim_code": meta.get("fork_sim_code", ""),
            "start_time": start_iso,
            "cur_time": cur_iso,
            "curr_time": meta.get("curr_time", ""),  # raw long-English for JS default
            "step": meta.get("step", 0),
            "personas": meta.get("persona_names", []),
            "is_base": entry.name.startswith("base_"),
            "mtime": meta_path.stat().st_mtime,
            "movement_steps": movement_steps,
            "has_compressed": has_compressed,
            "replay_url": replay_url,
        })
```

Note: the row drops `"start_date"` (template no longer reads it) but keeps raw `"curr_time"` so the form's JS can extract HMS for the default value.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/metagpt/ext/stanford_town/frontend/test_sim_utils_iso.py -v`
Expected: all 7 PASS (4 from Task 2 + 3 new).

- [ ] **Step 5: Commit**

```bash
git add examples/stanford_town/frontend/translator/sim_utils.py tests/metagpt/ext/stanford_town/frontend/test_sim_utils_iso.py
git commit -m "feat(stanford_town): list_simulations returns ISO start_time + cur_time"
```

---

## Task 4: `sim_utils.start_backend` accepts `start_hms`

**Files:**
- Modify: `examples/stanford_town/frontend/translator/sim_utils.py:160-227`
- Test: `tests/metagpt/ext/stanford_town/frontend/test_sim_utils_start_hms.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/metagpt/ext/stanford_town/frontend/test_sim_utils_start_hms.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/metagpt/ext/stanford_town/frontend/test_sim_utils_start_hms.py -v`
Expected: all 3 FAIL with `TypeError: start_backend() got an unexpected keyword argument 'start_hms'`.

- [ ] **Step 3: Update `start_backend` signature and command building**

In `examples/stanford_town/frontend/translator/sim_utils.py`, modify `start_backend`:

Change the signature to add `start_hms` (insert just after `inner_voice`):

```python
def start_backend(
    *,
    idea: str,
    sim_code: str,
    fork_sim_code: str,
    n_round: int,
    investment: float | None,
    st_root: Path,
    log_dir: Path,
    personas: list[str] | None = None,
    inner_voice: str | None = None,
    start_hms: str | None = None,
) -> tuple[subprocess.Popen, Path]:
```

In the body, after the existing `if inner_voice: cmd += [...]` block:

```python
    if start_hms:
        cmd += ["--start_hms", start_hms]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/metagpt/ext/stanford_town/frontend/test_sim_utils_start_hms.py -v`
Expected: all 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add examples/stanford_town/frontend/translator/sim_utils.py tests/metagpt/ext/stanford_town/frontend/test_sim_utils_start_hms.py
git commit -m "feat(stanford_town): start_backend forwards --start_hms CLI flag"
```

---

## Task 5: `run_st_game.py` `--start_hms` rewrites `meta.json`

**Files:**
- Modify: `examples/stanford_town/run_st_game.py`

This task has no unit test (it's an asyncio CLI entry that spawns reverie); verified by Task 10's manual smoke test.

- [ ] **Step 1: Add `start_hms` parameter to `startup()` and `main()`**

In `examples/stanford_town/run_st_game.py:25-34`, append `start_hms` to `startup()`:

```python
async def startup(
    idea: str,
    fork_sim_code: str,
    sim_code: str,
    temp_storage_path: str,
    investment: float = 30.0,
    n_round: int = 500,
    personas: Optional[str] = None,
    inner_voice: Optional[str] = None,
    start_hms: Optional[str] = None,
):
```

Same addition to `main()` at line 112-121, and pass `start_hms=start_hms` to the `startup(...)` call inside `asyncio.run(...)` at line 135.

- [ ] **Step 2: Rewrite `meta.json` after copy/persona-edit, before STRole construction**

In `examples/stanford_town/run_st_game.py`, between the existing persona-subset block (ends at line 53) and the `iv = inner_voice or ...` line (line 55), insert:

```python
    # Settle start_time + curr_time in the freshly-copied meta.json.
    # When the caller provides --start_hms, override both with start_date + HMS;
    # otherwise preserve fork-continuation semantics by writing start_time =
    # the inherited curr_time (only if missing, so re-runs stay idempotent).
    meta_path = STORAGE_PATH.joinpath(sim_code, "reverie", "meta.json")
    reverie_meta = json.loads(meta_path.read_text(encoding="utf-8"))
    start_date = reverie_meta["start_date"]
    if start_hms:
        full_dt = f"{start_date}, {start_hms}"
        reverie_meta["start_time"] = full_dt
        reverie_meta["curr_time"] = full_dt
    else:
        reverie_meta.setdefault("start_time", reverie_meta["curr_time"])
    meta_path.write_text(json.dumps(reverie_meta, indent=2), encoding="utf-8")
    logger.info(f"meta.json settled: start_time={reverie_meta['start_time']}, curr_time={reverie_meta['curr_time']}")
```

- [ ] **Step 3: Update STRole construction to use the new `start_time`**

In `examples/stanford_town/run_st_game.py:69`, change:

```python
            start_time=reverie_meta.get("start_date"),
```

to:

```python
            start_time=reverie_meta.get("start_time", reverie_meta.get("start_date")),
```

This relies on the Task 1 validator change to parse the full-datetime shape.

- [ ] **Step 4: Quick syntax check**

Run: `python -c "import ast; ast.parse(open('examples/stanford_town/run_st_game.py').read())"`
Expected: no output (no syntax error).

- [ ] **Step 5: Commit**

```bash
git add examples/stanford_town/run_st_game.py
git commit -m "feat(stanford_town): run_st_game --start_hms rewrites meta.json on launch"
```

---

## Task 6: `views.py` `start_simulation` reads + validates `start_hms`

**Files:**
- Modify: `examples/stanford_town/frontend/translator/views.py` (`landing` and `start_simulation`)

- [ ] **Step 1: Add the HMS regex constant**

At the top of `examples/stanford_town/frontend/translator/views.py`, after the existing imports (around line 23, after `from . import sim_utils`), add:

```python
import re as _re

_HMS_RE = _re.compile(r"^([01]\d|2[0-3]):[0-5]\d:[0-5]\d$")
```

- [ ] **Step 2: Expose `sim_curr_times` from the `landing` view**

In `examples/stanford_town/frontend/translator/views.py:29-36`, replace the `context` dict in `landing`:

```python
  context = {
    "simulations": sims,
    "fork_options": fork_options,
    "all_sim_codes": [s["sim_code"] for s in sims],
    "sim_personas": {s["sim_code"]: s["personas"] for s in sims},
    "sim_curr_times": {s["sim_code"]: s.get("curr_time", "") for s in sims},
    "default_n_round": 30,
    "default_investment": 30.0,
  }
```

- [ ] **Step 3: Read and validate `start_hms` in `start_simulation`**

In `examples/stanford_town/frontend/translator/views.py`, after line 57 (where `personas` is parsed) and before the `try: n_round = ...` block, insert:

```python
  start_hms = (request.POST.get("start_hms") or "").strip()
  if start_hms and not _HMS_RE.match(start_hms):
    return JsonResponse({"ok": False, "error": "start_hms must be HH:MM:SS"}, status=400)
```

- [ ] **Step 4: Pass `start_hms` to `start_backend`**

In the `start_backend(...)` call (lines 87-97), append `start_hms=start_hms or None,` before the closing paren:

```python
    proc, log_dir = sim_utils.start_backend(
      idea=idea,
      sim_code=sim_code,
      fork_sim_code=fork_sim_code,
      n_round=n_round,
      investment=investment,
      st_root=root,
      log_dir=Path(__file__).resolve().parent.parent / "logs",
      personas=personas,
      inner_voice=inner_voice,
      start_hms=start_hms or None,
    )
```

- [ ] **Step 5: Smoke-test the regex inline**

Run: `python -c "import re; r = re.compile(r'^([01]\d|2[0-3]):[0-5]\d:[0-5]\d$'); print([bool(r.match(s)) for s in ['14:30:00','00:00:00','23:59:59','25:00:00','14:30','abc','14:60:00','14:30:60']])"`
Expected: `[True, True, True, False, False, False, False, False]`

- [ ] **Step 6: Commit**

```bash
git add examples/stanford_town/frontend/translator/views.py
git commit -m "feat(stanford_town): start_simulation accepts and validates start_hms"
```

---

## Task 7: `landing.html` — table column rename + new `cur_time` column

**Files:**
- Modify: `examples/stanford_town/frontend/templates/landing/landing.html:90-119`

- [ ] **Step 1: Update the table header**

In `examples/stanford_town/frontend/templates/landing/landing.html`, replace lines 92-101 with:

```html
        <thead>
          <tr>
            <th>sim_code</th>
            <th>fork base</th>
            <th>start_time</th>
            <th>cur_time</th>
            <th class="text-right">step</th>
            <th class="text-right">moves</th>
            <th>personas</th>
            <th style="width: 240px;">操作</th>
          </tr>
        </thead>
```

- [ ] **Step 2: Update the table row body**

In the same file, replace the existing `<td><small>{{ s.start_date }}</small></td>` line (around line 110) with two cells:

```html
            <td><small>{{ s.start_time }}</small></td>
            <td><small>{{ s.cur_time }}</small></td>
```

- [ ] **Step 3: Manual visual check**

Start Django dev server (if not already running) and load the dashboard:

```
cd examples/stanford_town/frontend
python manage.py runserver
```

Visit http://127.0.0.1:8000/ → "已有存档" table should show:
- `start_time` column with values like `2023-02-13 00:00:00` for existing archives (Task 3 fallback)
- `cur_time` column with values like `2023-02-13 03:14:20` for sims that have advanced, blank for fresh ones
- 8 column headers, matching cells in each row

If layout breaks or columns missing, fix before commit.

- [ ] **Step 4: Commit**

```bash
git add examples/stanford_town/frontend/templates/landing/landing.html
git commit -m "feat(stanford_town): dashboard table shows ISO start_time + cur_time"
```

---

## Task 8: `landing.html` — form input + JS default from fork base's `curr_time`

**Files:**
- Modify: `examples/stanford_town/frontend/templates/landing/landing.html` (form + JS)

- [ ] **Step 1: Add the time input to the form**

In `examples/stanford_town/frontend/templates/landing/landing.html`, replace the existing row containing `Sim code / Fork from / Rounds` (lines 23-47) with a 4-column layout:

```html
        <div class="row">
          <div class="form-group col-md-3">
            <label>Sim code（新存档名，必须唯一）</label>
            <input type="text" name="sim_code" class="form-control"
              placeholder="例如：tea_test" required>
          </div>
          <div class="form-group col-md-4">
            <label>
              Fork from
              <small class="text-muted">
                <input type="checkbox" id="show-all-forks"> 显示全部存档
              </small>
            </label>
            <select name="fork_sim_code" id="fork-select" class="form-control" required>
              {% for code in fork_options %}
                <option value="{{ code }}">{{ code }}</option>
              {% endfor %}
            </select>
          </div>
          <div class="form-group col-md-3">
            <label>Start time <small class="text-muted">(HH:MM:SS)</small></label>
            <input type="time" name="start_hms" id="start-hms" step="1"
              class="form-control" value="00:00:00">
          </div>
          <div class="form-group col-md-2">
            <label>Rounds</label>
            <input type="number" name="n_round" class="form-control"
              value="{{ default_n_round }}" min="1">
          </div>
        </div>
```

- [ ] **Step 2: Expose `SIM_CURR_TIMES` to JS**

In the `<script>` block of the same file, after the existing `var SIM_PERSONAS = ...;` line (around line 148), add:

```javascript
  var SIM_CURR_TIMES = {{ sim_curr_times|safe }};

  // Extract "HH:MM:SS" from a long-English datetime like "February 13, 2023, 14:30:00".
  function extractHMS(curr_time) {
    if (!curr_time) return "00:00:00";
    var m = curr_time.match(/(\d{2}:\d{2}:\d{2})$/);
    return m ? m[1] : "00:00:00";
  }

  function updateStartHmsDefault() {
    var fork = document.getElementById("fork-select").value;
    var input = document.getElementById("start-hms");
    if (input) input.value = extractHMS(SIM_CURR_TIMES[fork]);
  }
```

- [ ] **Step 3: Wire the default-value updater to fork-select changes**

In the same script block, the existing `fork-select` change listener (around line 277-278) is:

```javascript
  document.getElementById("fork-select").addEventListener("change", rebuildPersonaList);
  document.getElementById("show-all-forks").addEventListener("change", rebuildPersonaList);
```

Add `updateStartHmsDefault` to both:

```javascript
  document.getElementById("fork-select").addEventListener("change", function () {
    rebuildPersonaList();
    updateStartHmsDefault();
  });
  document.getElementById("show-all-forks").addEventListener("change", function () {
    rebuildPersonaList();
    updateStartHmsDefault();
  });
```

And call it once on initial load — right after `rebuildPersonaList();` at the end of those setup lines (around line 280):

```javascript
  rebuildPersonaList();
  updateStartHmsDefault();
```

- [ ] **Step 4: Make sure `start_hms` is included in the rerun-from prompt path**

The rerun-from path (lines 350-365) currently builds its own payload without `start_hms`. Leave it unchanged for now — rerun keeps "continue from fork base's curr_time" semantics, which matches "omit `start_hms`" on the backend.

- [ ] **Step 5: Manual UI verification**

Reload the dashboard. Verify:
- "Start time" input appears between "Fork from" and "Rounds"
- Default value reflects the selected fork base's HMS (most bases at step 0 will show `00:00:00`; a mid-sim fork shows its current HMS)
- Changing the fork-select dropdown updates the time input

- [ ] **Step 6: Commit**

```bash
git add examples/stanford_town/frontend/templates/landing/landing.html
git commit -m "feat(stanford_town): launch form lets user pick start time (HH:MM:SS)"
```

---

## Task 9: End-to-end manual smoke test

No code changes. Just verify the full flow works.

- [ ] **Step 1: Dashboard renders existing archives correctly**

Visit http://127.0.0.1:8000/. In the "已有存档" table:
- `start_time` column shows ISO format for all existing archives (e.g. `2023-02-13 00:00:00`)
- `cur_time` column shows ISO format where archives have advanced (`2023-02-13 03:14:20`-style); blank for fresh bases
- No broken/empty cells

- [ ] **Step 2: Launch a new sim with a custom start_hms**

- Idea: `Host a coffee chat`
- Sim code: `test_starttime_smoke`
- Fork from: `base_the_ville_isabella_maria_klaus`
- Start time: `14:30:00`
- Rounds: `2`

Submit. Wait for the redirect or warning toast.

- [ ] **Step 3: Inspect the new `meta.json`**

```powershell
Get-Content examples/stanford_town/storage/test_starttime_smoke/reverie/meta.json
```

Expected fields:
- `"start_date": "February 13, 2023"`
- `"start_time": "February 13, 2023, 14:30:00"`
- `"curr_time": "February 13, 2023, 14:30:00"` (will advance as sim runs)

- [ ] **Step 4: Inspect the first movement step**

Wait for `storage/test_starttime_smoke/movement/0.json` to appear, then check the dashboard reloads — the new row should show `start_time: 2023-02-13 14:30:00` and `cur_time: 2023-02-13 14:30:xx`.

- [ ] **Step 5: Submit malformed HMS**

Open the form again, manually edit the time input value to `25:00:00` (some browsers will clamp; if so use DevTools to set `start_hms` to `abc` and submit). Expected: red toast with `start_hms must be HH:MM:SS`, no sim spawned.

- [ ] **Step 6: Cleanup smoke-test archive**

```powershell
Remove-Item -Recurse -Force examples/stanford_town/storage/test_starttime_smoke
```

- [ ] **Step 7: Done — no commit needed for the smoke test itself**

---

## Self-Review Summary

- **Spec coverage:** all 7 components (C1–C7) mapped to tasks 1–8. Backward compat handled in Task 3. Error handling for malformed HMS in Task 6. Old archive fallback exercised in Task 3 tests + Task 9 step 1.
- **Placeholders:** none. Every code change shown verbatim; every command has expected output.
- **Type consistency:** `start_hms` is `Optional[str]` everywhere (`views.py`, `sim_utils.start_backend`, `run_st_game.py`). `_to_iso` returns `str`. Row dict keys match between `sim_utils.list_simulations` (Task 3) and `landing.html` (Tasks 7–8): `start_time`, `cur_time`, `curr_time` (raw), `sim_code`, `personas`.
- **Reverie internals untouched:** Task 1's validator change is the only edit inside `metagpt/ext/stanford_town/`; all downstream code keeps reading long-English `curr_time` exactly as before.
