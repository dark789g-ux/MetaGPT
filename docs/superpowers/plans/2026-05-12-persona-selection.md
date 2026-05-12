# Persona Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users pick which personas (a subset of the fork base's persona_names) participate in a new Stanford Town simulation, and choose which one receives the `idea` as inner voice.

**Architecture:** Extend `run_st_game.py` with two optional CLI flags (`--personas`, `--inner_voice`). The Django landing view ships a `{sim_code: [persona…]}` map into the template; the form's JS renders a checkbox/radio block that rebuilds on fork change. View validates and forwards to the CLI. `run_st_game.py` rewrites the new sim's `meta.json["persona_names"]` to the chosen subset after `copy_folder`, and matches `inner_voice` by name when instantiating STRole. Backward compatible: missing flags = full set, idx 0 inner voice.

**Tech Stack:** Python 3.11 / Django 4.x (existing) / vanilla JS (Bootstrap 3 grid, no framework) / pytest for unit-testable pieces.

**Spec:** [`docs/superpowers/specs/2026-05-12-persona-selection-design.md`](../specs/2026-05-12-persona-selection-design.md)

---

## File Structure

**New files:** none.

**Modified files:**

| File | Responsibility |
|------|----------------|
| [`examples/stanford_town/frontend/translator/sim_utils.py`](../../../examples/stanford_town/frontend/translator/sim_utils.py) | Add `validate_personas(...)`; extend `start_backend(...)` with `personas` and `inner_voice` kwargs and append to CLI |
| [`examples/stanford_town/frontend/translator/views.py`](../../../examples/stanford_town/frontend/translator/views.py) | `landing()` exposes `sim_personas` map; `start_simulation()` parses + validates + forwards the new fields |
| [`examples/stanford_town/frontend/templates/landing/landing.html`](../../../examples/stanford_town/frontend/templates/landing/landing.html) | New persona/inner-voice block and the JS that drives it; form serializer adds the new fields |
| [`examples/stanford_town/run_st_game.py`](../../../examples/stanford_town/run_st_game.py) | Accept `--personas` / `--inner_voice`; after `copy_folder`, rewrite meta.json subset; pick inner voice by name match |

**New test files:**
- `tests/metagpt/ext/stanford_town/frontend/test_sim_utils_personas.py` — pure-function tests for `validate_personas`

UI/integration verification is manual (see Task 8); the project has no Django test fixtures wired and adding them is out of scope.

---

## Task 1: `validate_personas` helper (TDD)

**Files:**
- Modify: `examples/stanford_town/frontend/translator/sim_utils.py`
- Test: `tests/metagpt/ext/stanford_town/frontend/test_sim_utils_personas.py` (new)

- [ ] **Step 1: Create test file with failing tests**

Create `tests/metagpt/ext/stanford_town/frontend/__init__.py` (empty) so pytest discovers the directory, then `tests/metagpt/ext/stanford_town/frontend/test_sim_utils_personas.py`:

```python
"""Unit tests for sim_utils.validate_personas."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# The frontend Django app lives outside the package tree; add it to sys.path
# so we can import sim_utils without spinning up Django.
FRONTEND_DIR = Path(__file__).resolve().parents[4] / "examples" / "stanford_town" / "frontend"
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/metagpt/ext/stanford_town/frontend/test_sim_utils_personas.py -v`
Expected: All 7 tests fail with `AttributeError: module 'translator.sim_utils' has no attribute 'validate_personas'`.

- [ ] **Step 3: Implement `validate_personas` in sim_utils.py**

Add this function in `examples/stanford_town/frontend/translator/sim_utils.py` immediately after the existing `validate_new_sim_code` (after line 100):

```python
def validate_personas(
    personas: list[str] | None,
    inner_voice: str | None,
    fork_sim_code: str,
    storage_dir: Path,
) -> str | None:
    """Return an error string, or None when the persona selection is valid.

    `personas is None` means the caller did not request subset selection — the
    legacy "all personas from fork base, idx 0 as inner voice" path is taken
    and this function short-circuits.
    """
    if personas is None:
        return None
    if not personas:
        return "personas must not be empty."

    meta_path = storage_dir / fork_sim_code / "reverie" / "meta.json"
    if not meta_path.is_file():
        return f"fork base '{fork_sim_code}' has no meta.json."
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"failed to read fork base meta.json: {exc}"

    known = set(meta.get("persona_names", []))
    unknown = [p for p in personas if p not in known]
    if unknown:
        return f"unknown personas: {', '.join(unknown)}"

    if inner_voice is None or inner_voice not in personas:
        return "inner_voice must be one of the selected personas."

    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/metagpt/ext/stanford_town/frontend/test_sim_utils_personas.py -v`
Expected: All 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/metagpt/ext/stanford_town/frontend/__init__.py tests/metagpt/ext/stanford_town/frontend/test_sim_utils_personas.py examples/stanford_town/frontend/translator/sim_utils.py
git commit -m "feat(stanford_town): add validate_personas helper for sim launch"
```

---

## Task 2: Extend `start_backend` to forward persona CLI args

**Files:**
- Modify: `examples/stanford_town/frontend/translator/sim_utils.py` (function `start_backend`, lines 124-185)

This task has no automated test — `start_backend` spawns a subprocess, which is awkward to mock and the build step (CLI string) is what we verify in Task 8. Keeping it small.

- [ ] **Step 1: Update `start_backend` signature and CLI assembly**

In `examples/stanford_town/frontend/translator/sim_utils.py`, replace the existing `start_backend` signature and the `cmd = [...]` block (around lines 124-150) with:

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
) -> tuple[subprocess.Popen, Path]:
    # One run = one timestamped directory under logs/<sim_code>/, holding
    # launch.log / stdout.log / llm.log / error.log. The returned Path points
    # at that directory; callers display it to the user.
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = log_dir / sim_code / ts
    run_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(st_root / "run_st_game.py"),
        idea,
        fork_sim_code,
        sim_code,
        "--n_round", str(n_round),
    ]
    if investment is not None:
        cmd += ["--investment", str(investment)]
    if personas:
        cmd += ["--personas", ",".join(personas)]
    if inner_voice:
        cmd += ["--inner_voice", inner_voice]
```

(The rest of the function — env, Popen, stdout demux — is unchanged.)

- [ ] **Step 2: Smoke check that the module still imports**

Run: `python -c "import sys; sys.path.insert(0, 'examples/stanford_town/frontend'); from translator import sim_utils; print(sim_utils.start_backend.__doc__ or 'ok')"`
Expected: prints `ok` (or the docstring) with no exception.

- [ ] **Step 3: Commit**

```bash
git add examples/stanford_town/frontend/translator/sim_utils.py
git commit -m "feat(stanford_town): forward persona selection to run_st_game CLI"
```

---

## Task 3: Wire persona fields through `start_simulation` view

**Files:**
- Modify: `examples/stanford_town/frontend/translator/views.py` (function `start_simulation`, lines 39-126)

- [ ] **Step 1: Parse new POST fields**

In `examples/stanford_town/frontend/translator/views.py`, inside `start_simulation`, immediately after the `fork_sim_code = ...` line (line 49), add:

```python
  personas_raw = (request.POST.get("personas") or "").strip()
  inner_voice = (request.POST.get("inner_voice") or "").strip() or None
  personas: list[str] | None
  if personas_raw:
    personas = [p.strip() for p in personas_raw.split(",") if p.strip()]
  else:
    personas = None
```

- [ ] **Step 2: Validate after `validate_new_sim_code`**

In the same function, immediately after the existing `validate_new_sim_code` block (after line 72), insert:

```python
  err = sim_utils.validate_personas(personas, inner_voice, fork_sim_code, storage)
  if err:
    return JsonResponse({"ok": False, "error": err}, status=400)
```

- [ ] **Step 3: Forward to `start_backend`**

Update the `sim_utils.start_backend(...)` call (around lines 75-83) so the kwargs block ends with `personas=personas, inner_voice=inner_voice`:

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
    )
```

- [ ] **Step 4: Smoke check Django import**

Run: `python -c "import os, sys; sys.path.insert(0, 'examples/stanford_town/frontend'); os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'frontend_server.settings.local'); import django; django.setup(); from translator import views; print('ok')"`
Expected: prints `ok`. (If `DJANGO_SETTINGS_MODULE` errors out locally, skip — Task 8 catches integration issues.)

- [ ] **Step 5: Commit**

```bash
git add examples/stanford_town/frontend/translator/views.py
git commit -m "feat(stanford_town): accept persona selection in start_simulation"
```

---

## Task 4: Expose `sim_personas` map to landing template

**Files:**
- Modify: `examples/stanford_town/frontend/translator/views.py` (function `landing`, lines 25-36)

- [ ] **Step 1: Add `sim_personas` to context**

Replace the `context = {...}` block in `landing` (lines 29-35) with:

```python
  context = {
    "simulations": sims,
    "fork_options": fork_options,
    "all_sim_codes": [s["sim_code"] for s in sims],
    "sim_personas": {s["sim_code"]: s["personas"] for s in sims},
    "default_n_round": 30,
    "default_investment": 30.0,
  }
```

- [ ] **Step 2: Commit**

```bash
git add examples/stanford_town/frontend/translator/views.py
git commit -m "feat(stanford_town): expose sim_personas map to landing template"
```

---

## Task 5: Landing template — markup for persona block

**Files:**
- Modify: `examples/stanford_town/frontend/templates/landing/landing.html`

- [ ] **Step 1: Insert the persona block after the Rounds row**

In `examples/stanford_town/frontend/templates/landing/landing.html`, locate the closing `</div>` of the first `.row` (the one ending at line 47, just before `<div class="row">` containing Investment on line 49). Insert this new block between them:

```html
        <div class="form-group">
          <label>
            Personas <small class="text-muted" id="personas-source">（来自 fork base）</small>
            <small style="margin-left: 1em;">
              <a href="#" id="personas-all">全选</a> ·
              <a href="#" id="personas-none">全不选</a>
            </small>
          </label>
          <div id="personas-list"
               style="border:1px solid #ddd; border-radius:4px; padding:0.5em 0.75em; max-height:180px; overflow:auto;">
            <!-- rows injected by JS -->
          </div>
          <p class="help-block" id="personas-hint" style="display:none; color:#a94442;">
            至少选择一位 persona。
          </p>
        </div>
```

- [ ] **Step 2: Add `SIM_PERSONAS` to the JS preamble**

Locate the existing JS preamble (currently lines 128-130):

```javascript
(function () {
  var ALL_SIMS = {{ all_sim_codes|safe }};
  var BASE_SIMS = {{ fork_options|safe }};
```

Replace with:

```javascript
(function () {
  var ALL_SIMS = {{ all_sim_codes|safe }};
  var BASE_SIMS = {{ fork_options|safe }};
  var SIM_PERSONAS = {{ sim_personas|safe }};
```

- [ ] **Step 3: Verify Django template still renders**

Run: `cd examples/stanford_town/frontend && python manage.py check`
Expected: `System check identified no issues (0 silenced).` (warnings OK; errors are not.)

- [ ] **Step 4: Commit**

```bash
git add examples/stanford_town/frontend/templates/landing/landing.html
git commit -m "feat(stanford_town): add persona selection block to landing form"
```

---

## Task 6: Landing template — JS for persona rendering, inner voice, submit serialization

**Files:**
- Modify: `examples/stanford_town/frontend/templates/landing/landing.html`

- [ ] **Step 1: Add the persona-list state + render functions**

Inside the same `<script>` IIFE in `landing.html`, immediately after the existing `rebuildForkOptions` function and its `change` listener (just after line 155), add:

```javascript
  // --- Persona selection state ---------------------------------------------
  // checked: Set of persona names currently ticked
  // innerVoice: name of the persona who receives the idea (must be in checked)
  var personaState = { checked: new Set(), innerVoice: null };

  function currentForkPersonas() {
    var fork = document.getElementById("fork-select").value;
    return (SIM_PERSONAS[fork] || []).slice();
  }

  function rebuildPersonaList() {
    var list = document.getElementById("personas-list");
    var src = document.getElementById("personas-source");
    var fork = document.getElementById("fork-select").value;
    src.textContent = "（来自 " + fork + "）";

    var names = currentForkPersonas();
    personaState.checked = new Set(names);
    personaState.innerVoice = names.length ? names[0] : null;

    list.innerHTML = "";
    if (!names.length) {
      list.innerHTML = '<div class="text-muted"><em>该 base 未声明 personas</em></div>';
      updateSubmitState();
      return;
    }
    names.forEach(function (name) {
      var row = document.createElement("div");
      row.style.display = "flex";
      row.style.alignItems = "center";
      row.style.gap = "0.75em";
      row.style.padding = "2px 0";
      row.innerHTML =
        '<label style="margin:0; flex:1; cursor:pointer;">' +
          '<input type="checkbox" class="persona-cb" data-name="' + name + '" checked> ' +
          name +
        '</label>' +
        '<label style="margin:0; cursor:pointer; color:#666;">' +
          '<input type="radio" name="iv-radio" class="persona-iv" data-name="' + name + '"' +
          (name === personaState.innerVoice ? ' checked' : '') + '> inner voice' +
        '</label>';
      list.appendChild(row);
    });
    updateSubmitState();
  }

  function updateSubmitState() {
    var hint = document.getElementById("personas-hint");
    var btn = document.querySelector('#start-form button[type="submit"]');
    var ok = personaState.checked.size > 0;
    hint.style.display = ok ? "none" : "";
    if (btn) btn.disabled = !ok;
    // Radio: disable for unchecked rows
    Array.prototype.forEach.call(document.querySelectorAll(".persona-iv"), function (r) {
      r.disabled = !personaState.checked.has(r.dataset.name);
    });
  }

  document.getElementById("personas-list").addEventListener("change", function (e) {
    var t = e.target;
    if (t.classList.contains("persona-cb")) {
      if (t.checked) personaState.checked.add(t.dataset.name);
      else personaState.checked.delete(t.dataset.name);
      // If we unchecked the current inner voice, reassign to first checked.
      if (!personaState.checked.has(personaState.innerVoice)) {
        var iter = personaState.checked.values().next();
        personaState.innerVoice = iter.done ? null : iter.value;
        Array.prototype.forEach.call(document.querySelectorAll(".persona-iv"), function (r) {
          r.checked = (r.dataset.name === personaState.innerVoice);
        });
      }
      updateSubmitState();
    } else if (t.classList.contains("persona-iv")) {
      personaState.innerVoice = t.dataset.name;
    }
  });

  document.getElementById("personas-all").addEventListener("click", function (e) {
    e.preventDefault();
    Array.prototype.forEach.call(document.querySelectorAll(".persona-cb"), function (cb) {
      cb.checked = true; personaState.checked.add(cb.dataset.name);
    });
    if (!personaState.innerVoice) {
      var first = currentForkPersonas()[0];
      personaState.innerVoice = first || null;
      var r = document.querySelector('.persona-iv[data-name="' + first + '"]');
      if (r) r.checked = true;
    }
    updateSubmitState();
  });

  document.getElementById("personas-none").addEventListener("click", function (e) {
    e.preventDefault();
    Array.prototype.forEach.call(document.querySelectorAll(".persona-cb"), function (cb) {
      cb.checked = false;
    });
    personaState.checked.clear();
    personaState.innerVoice = null;
    Array.prototype.forEach.call(document.querySelectorAll(".persona-iv"), function (r) {
      r.checked = false;
    });
    updateSubmitState();
  });

  rebuildPersonaList();
```

- [ ] **Step 2: Hook fork-select changes to rebuild persona list**

Find the existing fork-select change listener (currently lines 153-155):

```javascript
  document.getElementById("show-all-forks").addEventListener("change", function (e) {
    rebuildForkOptions(e.target.checked);
  });
```

Immediately after it, add:

```javascript
  document.getElementById("fork-select").addEventListener("change", rebuildPersonaList);
  // The "show all forks" checkbox swaps the selected option; persona list must follow.
  document.getElementById("show-all-forks").addEventListener("change", rebuildPersonaList);
```

- [ ] **Step 3: Serialize personas + inner_voice on submit**

Find the submit handler (around lines 210-217):

```javascript
  document.getElementById("start-form").addEventListener("submit", function (e) {
    e.preventDefault();
    var fd = new FormData(e.target);
    var payload = {};
    fd.forEach(function (v, k) { payload[k] = v; });
    var btn = e.target.querySelector('button[type="submit"]') || e.submitter;
    postStart(payload, "已启动新模拟", btn);
  });
```

Replace with:

```javascript
  document.getElementById("start-form").addEventListener("submit", function (e) {
    e.preventDefault();
    if (personaState.checked.size === 0) {
      updateSubmitState();
      return;
    }
    var fd = new FormData(e.target);
    var payload = {};
    fd.forEach(function (v, k) { payload[k] = v; });
    payload.personas = Array.from(personaState.checked).join(",");
    payload.inner_voice = personaState.innerVoice || "";
    var btn = e.target.querySelector('button[type="submit"]') || e.submitter;
    postStart(payload, "已启动新模拟", btn);
  });
```

- [ ] **Step 4: Verify Django template still renders**

Run: `cd examples/stanford_town/frontend && python manage.py check`
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 5: Commit**

```bash
git add examples/stanford_town/frontend/templates/landing/landing.html
git commit -m "feat(stanford_town): drive persona selection UI and submit serialization"
```

---

## Task 7: `run_st_game.py` — accept CLI flags, rewrite meta.json, pick inner voice

**Files:**
- Modify: `examples/stanford_town/run_st_game.py`

- [ ] **Step 1: Update `startup` to accept and apply selection**

In `examples/stanford_town/run_st_game.py`, replace the existing `startup` function (lines 23-60) with:

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
):
    town = StanfordTown()
    logger.info("StanfordTown init environment")

    # copy `storage/{fork_sim_code}` to `storage/{sim_code}`
    copy_folder(str(STORAGE_PATH.joinpath(fork_sim_code)), str(STORAGE_PATH.joinpath(sim_code)))

    # Read the new sim's meta (a fresh copy of the fork base's) so we can edit
    # it in place if the caller asked for a persona subset.
    reverie_meta = get_reverie_meta(sim_code)

    if personas:
        selected = [p.strip() for p in personas.split(",") if p.strip()]
        unknown = set(selected) - set(reverie_meta["persona_names"])
        if unknown:
            raise SystemExit(f"unknown personas: {sorted(unknown)}")
        reverie_meta["persona_names"] = selected
        meta_path = STORAGE_PATH.joinpath(sim_code, "reverie", "meta.json")
        meta_path.write_text(json.dumps(reverie_meta, indent=2), encoding="utf-8")
        logger.info(f"persona subset applied: {selected}")

    iv = inner_voice or reverie_meta["persona_names"][0]
    if iv not in reverie_meta["persona_names"]:
        raise SystemExit(f"inner_voice '{iv}' not in personas {reverie_meta['persona_names']}")

    roles = []
    sim_path = STORAGE_PATH.joinpath(sim_code)
    sim_path.mkdir(exist_ok=True)
    for role_name in reverie_meta["persona_names"]:
        has_inner_voice = (role_name == iv)
        role = STRole(
            name=role_name,
            profile=role_name,
            sim_code=sim_code,
            step=reverie_meta.get("step", 0),
            start_time=reverie_meta.get("start_date"),
            curr_time=reverie_meta.get("curr_time"),
            sec_per_step=reverie_meta.get("sec_per_step"),
            has_inner_voice=has_inner_voice,
        )
        roles.append(role)

    # init temp_storage
    write_curr_sim_code({"sim_code": sim_code}, temp_storage_path)
    write_curr_step({"step": reverie_meta.get("step", 0)}, temp_storage_path)

    await town.hire(roles)

    town.invest(investment)
    town.run_project(idea)

    await town.run(n_round)
```

- [ ] **Step 2: Add `json` import and update `main` signature**

At the top of `examples/stanford_town/run_st_game.py`, find the imports (after `import asyncio`). Add `import json` if not already present:

```python
import asyncio
import json
from typing import Optional
```

Then replace the existing `main` function (lines 63-90) with:

```python
def main(
    idea: str,
    fork_sim_code: str,
    sim_code: str,
    temp_storage_path: Optional[str] = None,
    investment: float = 30.0,
    n_round: int = 500,
    personas: Optional[str] = None,
    inner_voice: Optional[str] = None,
):
    """
    Args:
        idea: idea works as an `inner voice` to the first agent.
        fork_sim_code: old simulation name to start with, choose one inside `generative_agents/environment/frontend_server/storage/`
        sim_code: new simulation name to save simulation result
        temp_storage_path: generative_agents temp_storage path inside `environment/frontend_server` to interact.
        investment: the investment of running agents
        n_round: rounds to run agents
        personas: optional comma-separated subset of the fork base's persona_names; when set, the new sim's meta.json is rewritten to this subset.
        inner_voice: optional persona name to receive the idea; must be in `personas` when both are given. Defaults to the first persona in meta.
    """

    asyncio.run(
        startup(
            idea=idea,
            fork_sim_code=fork_sim_code,
            sim_code=sim_code,
            temp_storage_path=temp_storage_path,
            investment=investment,
            n_round=n_round,
            personas=personas,
            inner_voice=inner_voice,
        )
    )
```

- [ ] **Step 3: Smoke check the module imports**

Run: `python -c "import sys; sys.path.insert(0, 'examples/stanford_town'); import run_st_game; print(run_st_game.main.__doc__[:40])"`
Expected: prints the first line of the docstring with no exception.

- [ ] **Step 4: Commit**

```bash
git add examples/stanford_town/run_st_game.py
git commit -m "feat(stanford_town): support --personas/--inner_voice in run_st_game"
```

---

## Task 8: Manual end-to-end verification

No automated harness; this is the gate.

- [ ] **Step 1: Start the frontend dev server**

Run (in a separate terminal):
```bash
cd examples/stanford_town/frontend
python manage.py runserver
```
Open <http://127.0.0.1:8000/>.

- [ ] **Step 2: Persona block renders for default fork**

Expected: under the Rounds row, a "Personas（来自 base_…）" block lists the personas of the currently selected fork, all checkboxes checked, the first row's "inner voice" radio selected.

- [ ] **Step 3: Fork change rebuilds the list**

Change the "Fork from" dropdown. Expected: the persona list rebuilds; "（来自 …）" label updates; all checked; first row inner voice.

- [ ] **Step 4: Inner-voice reassignment on uncheck**

Uncheck the currently-checked inner voice row. Expected: that row's radio is now disabled; the radio jumps to the first remaining checked persona.

- [ ] **Step 5: Submit disabled when empty**

Click "全不选". Expected: the red hint "至少选择一位 persona。" appears; the 启动模拟 button is disabled. Click "全选" → button re-enables.

- [ ] **Step 6: Run a 2-persona subset**

Pick a base with ≥3 personas, uncheck one, change inner voice to a non-default persona, fill `idea` and a fresh `sim_code` (e.g. `subset_smoke_<ts>`), click 启动模拟. Expected:
- Toast: "🟢 已启动新模拟 <code>subset_smoke_…</code>, 正在进入小镇…"
- File `examples/stanford_town/logs/<sim_code>/<ts>/launch.log` contains `--personas` and `--inner_voice` flags
- File `examples/stanford_town/storage/<sim_code>/reverie/meta.json` has `persona_names` matching your subset
- In `/simulator_home`, only the chosen personas are present on the map

- [ ] **Step 7: 400 on invalid input (manual)**

Open browser devtools console, run:
```javascript
fetch("/start_simulation/", {method:"POST", body: new URLSearchParams({
  idea:"x", sim_code:"bogus_"+Date.now(), fork_sim_code:"base_the_ville_isabella_maria_klaus",
  personas:"Isabella Rodriguez,Ghost", inner_voice:"Isabella Rodriguez", n_round:"1"
})}).then(r=>r.json()).then(console.log);
```
Expected: response `{ok:false, error:"unknown personas: Ghost"}` with status 400.

- [ ] **Step 8: CLI backward compatibility**

Stop the dev server. From a shell:
```bash
cd examples/stanford_town
python run_st_game.py "x" base_the_ville_isabella_maria_klaus cli_compat_smoke --n_round 1
```
Let it run a few seconds, then Ctrl-C. Expected: it starts without complaining about missing `personas`/`inner_voice`, and `storage/cli_compat_smoke/reverie/meta.json` shows the FULL persona list (untouched).

Clean up: `rm -rf examples/stanford_town/storage/cli_compat_smoke examples/stanford_town/storage/subset_smoke_*` (or whatever sim_codes you created).

- [ ] **Step 9: Commit the verification note (only if any docs were updated)**

If you discovered a bug and fixed it inline, that fix already lives in its own commit. Otherwise nothing to do here. No empty commit.

---

## Self-Review Notes

**Spec coverage cross-check:**

| Spec section | Implemented in task |
|--------------|---------------------|
| §1 Goal: subset selection + inner-voice picker | Tasks 5/6 (UI), 7 (backend) |
| §2 UI layout + defaults + auto-reassign | Tasks 5, 6 |
| §3 Data flow (sim_personas map → CLI flags → meta rewrite) | Tasks 4, 6, 2, 7 |
| §4 Backward compat (missing flags = legacy) | Task 7 (default `None`); Task 8 step 8 verifies |
| §4 Rerun path keeps full set | Task 6 leaves `.rerun-btn` handler untouched, so it never sends `personas`/`inner_voice` |
| §5 Validation table | Task 1 (validate_personas), Task 3 (view wiring), Task 7 (CLI defense in depth) |
| §6 File list | Matches exactly |
| §7 Manual verification | Task 8 |

**Placeholder scan:** none — every code step has full code, every run step has exact command + expected output.

**Type/name consistency:** `personas` is `list[str] | None` in Python layer; CLI delivers it as comma-joined string; `run_st_game.py` accepts `Optional[str]` and splits internally. `inner_voice` is `str | None` end-to-end. `sim_personas` template var maps to `SIM_PERSONAS` in JS. State object `personaState = {checked: Set, innerVoice: string}` is used consistently across handlers.
