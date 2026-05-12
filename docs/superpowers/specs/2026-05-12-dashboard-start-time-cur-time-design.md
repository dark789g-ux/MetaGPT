# Dashboard: precise `start_time` and `cur_time` columns

Date: 2026-05-12
Scope: Stanford Town dashboard ("已有存档" table) + simulation-launch flow

## Problem

The dashboard's "已有存档" table shows `start_date` as a bare day-level string (e.g. `February 13, 2023`). Two limitations:

1. The displayed value lacks hour/minute/second precision, even though the underlying simulation already runs on a second-resolution clock (`curr_time` advances by `sec_per_step`).
2. The table does not show the simulation's most-recent in-world time, only its starting date.

In addition, the launch form does not let the user pick a starting time. The clock always begins at `00:00:00` on the fork base's date, regardless of intent (e.g. "simulate a lunch party starting at 12:30").

## Goals

- Rename the table column `start_date` → `start_time`, display it as ISO `YYYY-MM-DD HH:MM:SS`.
- Add a new table column `cur_time` (the simulation's most-recent in-world time), same ISO format.
- Add a launch-form control letting the user pick a starting `HH:MM:SS` (the calendar date is fixed by the fork base).
- Preserve backward compatibility: existing archives whose `meta.json` lacks the new field must still render.

## Non-goals

- Letting the user change the simulation's calendar **date**. The date stays fixed by the fork base because reverie's internal schedule/memory logic is bound to it.
- Changing reverie's internal datetime format. All on-disk and in-memory datetimes inside the simulator remain in `%B %d, %Y, %H:%M:%S` (long English). ISO formatting happens only at the dashboard display boundary.
- Modifying existing simulation archives on disk. Backward compatibility is provided by a read-time fallback, not a migration.

## Design

### Architecture

```
[landing.html form]                                  [landing.html table]
       │  HH:MM:SS                                          ▲
       ▼                                                    │ ISO format
[views.py /start_simulation/] ──validate──► [sim_utils.start_backend]
                                                   │
                                                   │ --start_hms HH:MM:SS
                                                   ▼
                                          [run_st_game.py]
                                                   │ rewrites copied meta.json
                                                   │   start_time + curr_time
                                                   ▼
                                          [STRole loads meta] ── runs sim ──┐
                                                                            │
[sim_utils.list_simulations] ◄────── reads meta.json ◄──────── meta updated ┘
```

### `meta.json` schema

```jsonc
{
  "fork_sim_code": "...",
  "start_date": "February 13, 2023",                // unchanged (reverie internals depend on it)
  "start_time": "February 13, 2023, 14:30:00",      // NEW: full datetime in long English format
  "curr_time": "February 13, 2023, 14:30:10",       // unchanged semantics; equals start_time at step 0
  "sec_per_step": 10,
  "maze_name": "the_ville",
  "persona_names": [...],
  "step": 0
}
```

- `start_time` is written at sim creation (in `run_st_game.py`) and never overwritten thereafter.
- `curr_time` continues to be persisted by reverie as the simulation steps forward.
- Old archives (no `start_time`) are read with the fallback `start_date + ", 00:00:00"` at display time. We do not migrate them.

### Components

| # | Component | Responsibility | File |
|---|---|---|---|
| C1 | `STRole.check_start_time` | Accept both bare-date and full-datetime strings | [metagpt/ext/stanford_town/roles/st_role.py:89-92](metagpt/ext/stanford_town/roles/st_role.py#L89-L92) |
| C2 | `run_st_game.py` `--start_hms` | New CLI arg; rewrites copied `meta.json`'s `start_time` and `curr_time` before STRole loads it | [examples/stanford_town/run_st_game.py](examples/stanford_town/run_st_game.py) |
| C3 | `views.py` `/start_simulation/` | Read `start_hms` from POST form; validate format and ranges; pass to `start_backend` | [examples/stanford_town/frontend/translator/views.py](examples/stanford_town/frontend/translator/views.py) |
| C4 | `sim_utils.start_backend` | New `start_hms` parameter → `--start_hms` CLI flag | [examples/stanford_town/frontend/translator/sim_utils.py:160](examples/stanford_town/frontend/translator/sim_utils.py#L160) |
| C5 | `sim_utils.list_simulations` | Read `start_time` (with fallback) + `curr_time`; format both as ISO `YYYY-MM-DD HH:MM:SS` | [examples/stanford_town/frontend/translator/sim_utils.py:69-81](examples/stanford_town/frontend/translator/sim_utils.py#L69-L81) |
| C6 | `landing.html` launch form | Add `<input type="time" step="1" name="start_hms">`; JS default value is the HMS portion of the selected fork base's `curr_time` | [examples/stanford_town/frontend/templates/landing/landing.html](examples/stanford_town/frontend/templates/landing/landing.html) |
| C7 | `landing.html` "已有存档" table | Rename column header `start_date` → `start_time`; add new column `cur_time`; both cells render the ISO-formatted values from C5 | same file |

### Component details

**C1 — STRole validator** ([st_role.py:89-92](metagpt/ext/stanford_town/roles/st_role.py#L89-L92))

Current code blindly appends `, 00:00:00` and parses with `%B %d, %Y, %H:%M:%S`. New code: if input already matches `%B %d, %Y, %H:%M:%S`, parse directly; else append `, 00:00:00` and parse. Detection is by attempting the full-datetime parse first and falling back on `ValueError`. No other call sites need to change.

**C2 — `run_st_game.py` `--start_hms`**

Add `start_hms: Optional[str] = None` parameter to `startup()` / `main()`.

After `copy_folder()` and after persona-subset rewrite, but before constructing `STRole` instances:

```python
meta_path = STORAGE_PATH.joinpath(sim_code, "reverie", "meta.json")
reverie_meta = json.loads(meta_path.read_text(encoding="utf-8"))

start_date = reverie_meta["start_date"]
if start_hms:
    # User-provided override: reset both start_time and curr_time
    full_dt = f"{start_date}, {start_hms}"
    reverie_meta["start_time"] = full_dt
    reverie_meta["curr_time"] = full_dt
else:
    # Preserve fork-continuation: start_time = the moment this sim's clock begins,
    # which equals the inherited curr_time. Only write start_time if missing.
    reverie_meta.setdefault("start_time", reverie_meta["curr_time"])

meta_path.write_text(json.dumps(reverie_meta, indent=2), encoding="utf-8")
```

Then pass `start_time=reverie_meta["start_time"]` (instead of `start_date`) when building `STRole`. C1 ensures the validator accepts the new full-datetime shape.

**C3 — `views.py` validation**

```python
HMS_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d:[0-5]\d$")

start_hms = request.POST.get("start_hms", "").strip()
if start_hms and not HMS_RE.match(start_hms):
    return JsonResponse({"ok": False, "error": "start_hms must be HH:MM:SS"}, status=400)
```

Empty string is treated as "not provided" and falls through (preserves current behaviour).

**C4 — `sim_utils.start_backend`**

Add `start_hms: Optional[str] = None` parameter. When non-empty, append `["--start_hms", start_hms]` to `cmd`. No other changes.

**C5 — `sim_utils.list_simulations` formatting**

New helper:

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

In the row-build loop:

```python
raw_start = meta.get("start_time")  # NEW field, has HMS
if raw_start:
    start_iso = _to_iso(raw_start, with_time=True)
else:
    # Old archive: fall back to start_date + 00:00:00
    start_iso = _to_iso(meta.get("start_date", ""), with_time=False)

cur_iso = _to_iso(meta.get("curr_time", ""), with_time=True)

rows.append({
    ...
    "start_time": start_iso,
    "cur_time": cur_iso,
    ...
})
```

The old `"start_date"` key in the row dict is removed (the template no longer reads it).

**C6 — Launch form input**

In the existing `<div class="row">` containing `Sim code`, `Fork from`, `Rounds`, add a fourth column for the time input. (Or insert it as a new row beneath — visual choice for the implementer; both bootstrap-3 layouts work.)

```html
<div class="form-group col-md-3">
  <label>Start time <small class="text-muted">(HH:MM:SS)</small></label>
  <input type="time" name="start_hms" id="start-hms" step="1" class="form-control" value="00:00:00">
</div>
```

JS: on `fork-select` change, extract HMS from the selected fork base's `curr_time` and set the input's value. The existing `SIM_PERSONAS` map only contains personas; we expose a parallel `SIM_CURR_TIMES` map from the view (`{sim_code: "February 13, 2023, 14:30:10"}`) and parse the HMS substring client-side.

For fork bases freshly at step 0, the HMS is `00:00:00`. For mid-sim forks, the default tracks where they left off (preserves "continue from where it was" semantics for users who don't touch the field).

**C7 — Dashboard table**

```html
<th>start_time</th>
<th>cur_time</th>
...
<td><small>{{ s.start_time }}</small></td>
<td><small>{{ s.cur_time }}</small></td>
```

Replace the existing `start_date` column header and cell. Insert `cur_time` between `start_time` and `step`.

### Data flow (end to end)

1. User opens dashboard. `list_simulations` formats each archive's `start_time` / `curr_time` into ISO; old archives use the bare-date fallback for start_time.
2. User picks a fork base in the form. JS sets the `Start time` input to the HMS of that base's current time.
3. User edits HMS (or leaves the default) and submits.
4. `views.py` validates HMS, passes it to `start_backend`, which spawns `run_st_game.py --start_hms HH:MM:SS`.
5. `run_st_game.py` copies the fork base, rewrites the new sim's `meta.json` (`start_time` and `curr_time` both = `start_date + ", " + HMS`), and constructs STRoles.
6. Reverie runs; persists `curr_time` updates as usual.
7. After the run (or refresh), the dashboard reflects the new archive with its new `start_time` (fixed at creation) and `cur_time` (latest persisted).

## Error handling

| Scenario | Handling |
|---|---|
| `start_hms` not provided (empty) | No `--start_hms` passed; `run_st_game.py` preserves fork base's `curr_time` (current behaviour) and writes `start_time` if missing |
| `start_hms` malformed (e.g. `14:30`, `abc`) | `views.py` returns 400 with `"start_hms must be HH:MM:SS"`; toast displays the error |
| Hours/minutes/seconds out of range | Same regex rejects them (`[01]\d\|2[0-3]`, `[0-5]\d`) |
| Old archive: `meta.json` missing `start_time` | `_to_iso` fallback uses `start_date + 00:00:00`; row still renders |
| Old archive: `meta.json` missing `curr_time` | `_to_iso("")` returns `""`; `cur_time` cell is blank, no crash |
| `meta.json` unparseable | Existing try/except in `list_simulations` skips the entry (no change) |

## Testing

| Type | Test |
|---|---|
| Unit | `STRole.check_start_time` accepts `"February 13, 2023"` and `"February 13, 2023, 14:30:00"` and produces equivalent datetimes |
| Unit | `_to_iso("February 13, 2023, 14:30:00", with_time=True) == "2023-02-13 14:30:00"`; `_to_iso("", ...)` returns `""`; malformed input returns `""` |
| Unit | `list_simulations` over a fixture dir with one old-shape `meta.json` (no `start_time`) and one new-shape — both rows produce ISO `start_time` values |
| Unit | HMS regex: `14:30:00` matches; `25:00:00`, `14:30`, `14:30:60`, `abc` reject |
| Manual | Dashboard renders existing `test001/002/003` archives with ISO-formatted `start_time` (`00:00:00`) and `cur_time` |
| Manual | Launch new sim with `start_hms=14:30:00`. Inspect `storage/<new>/reverie/meta.json` → `start_time` = `"February 13, 2023, 14:30:00"`, `curr_time` = same. First `movement/0.json` shows agents at 14:30:00; second step at 14:30:10 |
| Manual | Fork from a mid-sim base, leave HMS input default. The default reflects the base's current HMS; new sim's `curr_time` matches |
| Manual | Submit malformed HMS → toast shows error, no sim spawned |

## Risks and open questions

- **Form-row layout**: adding a 4th column to the existing `Sim code / Fork from / Rounds` row makes columns narrow on smaller viewports. If implementation finds the row too cramped, move the input to a new row — purely cosmetic.
- **Internal clock drift**: when the user resets HMS via override, the new sim's `curr_time` jumps to the chosen time even if the fork base's was different. This is the intended override semantic; flagging it here so the implementer doesn't second-guess.
- **`SIM_CURR_TIMES` payload size**: exposing one more per-sim string in the rendered HTML is negligible (handful of bytes per sim).
