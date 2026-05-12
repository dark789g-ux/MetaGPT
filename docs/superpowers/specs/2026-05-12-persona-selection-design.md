---
title: Persona Selection for "启动新模拟"
date: 2026-05-12
status: design
---

# Persona Selection for "启动新模拟"

## 1. Goal

Let the user, on the Stanford Town landing page, choose which personas from the
fork base will participate in a new simulation, and which one of them is the
"inner voice" recipient of the `idea` field.

Today, [`run_st_game.py:33-49`](../../../examples/stanford_town/run_st_game.py#L33-L49)
instantiates every persona listed in the fork base's `reverie/meta.json`, and
the persona at index 0 always receives `has_inner_voice=True`. The new flow
must (a) allow a subset of personas and (b) allow choosing the inner-voice
persona explicitly.

Supports two use cases the user surfaced:
- **Cheap/debug runs** — pick 2-3 personas to keep cost down
- **Scenario casting** — pick the personas the `idea` is actually about

## 2. UI Design

A new block sits between the existing fork/rounds row and the Investment row in
[`landing.html`](../../../examples/stanford_town/frontend/templates/landing/landing.html).

```
Personas (from <fork_sim_code>)   [全选] [全不选]
 ☑ Isabella Rodriguez   ◉ inner voice
 ☑ Maria Lopez          ○
 ☑ Klaus Mueller        ○
 ☐ Tom Moreno           ○ (disabled while unchecked)
```

- Checkbox column = participation set
- Radio column = inner voice
- Radio for an unchecked row is disabled
- Defaults on fork change: all checked, inner voice = first persona
- If user unchecks the current inner voice, JS reassigns inner voice to the
  first still-checked persona
- If zero personas are checked, the submit button is disabled with a hint

## 3. Data Flow

```
landing view ──► template
   context["sim_personas"] = {sim_code: [persona_names...]}   (from existing list_simulations())

template JS
   var SIM_PERSONAS = {{ sim_personas|safe }};
   on fork change: rebuild checkbox/radio list from SIM_PERSONAS[fork]

form submit
   POST /start_simulation/
     idea, sim_code, fork_sim_code, n_round, investment      (existing)
     personas       = "Isabella Rodriguez,Maria Lopez"        (new, comma-joined)
     inner_voice    = "Isabella Rodriguez"                    (new)

start_simulation view
   validate (see §5)
   sim_utils.start_backend(..., personas=[...], inner_voice="...")

start_backend
   CLI: python run_st_game.py <idea> <fork> <sim_code>
        --n_round N --investment I
        --personas "A,B" --inner_voice "A"

run_st_game.py:startup
   copy_folder(fork → sim_code)                              (unchanged)
   meta = get_reverie_meta(sim_code)   # read NEW sim, not fork
   if personas given:
     validate subset is ⊆ meta["persona_names"]
     meta["persona_names"] = selected
     write meta back to storage/<sim_code>/reverie/meta.json
   iv = inner_voice or meta["persona_names"][0]
   for role_name in meta["persona_names"]:
     has_inner_voice = (role_name == iv)
     ...build STRole
```

Persona directories under `storage/<sim_code>/personas/` are copied as-is from
the fork base. Unselected personas keep their dirs on disk but are never
instantiated; this is harmless and avoids destructive logic.

## 4. Backwards Compatibility

`--personas` and `--inner_voice` are both optional. When absent (e.g. running
`python run_st_game.py "idea" base_xx new_xx` directly from a shell),
`run_st_game.py` falls back to the original behavior: all personas, idx 0 is
inner voice. The Django view always passes both, so this fallback is purely
for command-line use.

The `rerun` button on existing simulations (the `↻ 重跑` flow in landing.html)
does **not** open a persona picker. It re-runs with the base's full persona
set and idx 0 as inner voice — matching the spirit of "run the same thing
again". Achieved by simply not sending `personas` / `inner_voice` in that POST.

## 5. Validation

| Layer | Rule | Failure mode |
|-------|------|--------------|
| Frontend JS | ≥1 persona checked | Submit disabled, inline hint |
| Frontend JS | inner voice ∈ checked set | Auto-reassigned to first checked |
| Django view | if `personas` absent → no validation, fall through to legacy full-set behavior (rerun path) | — |
| Django view | if `personas` present, must be non-empty | 400 `"personas must not be empty."` |
| Django view | if present, each name ∈ fork base's `meta["persona_names"]` | 400 `"unknown personas: X, Y"` |
| Django view | if `personas` present, `inner_voice` must be present and ∈ submitted `personas` | 400 `"inner_voice must be one of the selected personas."` |
| `run_st_game.py` | same subset check (defense in depth for direct CLI use) | `SystemExit` → child returncode≠0 → existing 30s warm-up loop in views returns 500 with `log_dir` |

A new helper `sim_utils.validate_personas(personas, inner_voice, fork_sim_code, storage_dir) -> str | None`
lives next to `validate_new_sim_code` and returns the error string (or None).

## 6. Files Touched

- `examples/stanford_town/frontend/translator/views.py`
  - `landing()`: add `sim_personas` to context
  - `start_simulation()`: parse `personas`, `inner_voice`; call `validate_personas`; forward to `start_backend`
- `examples/stanford_town/frontend/translator/sim_utils.py`
  - new `validate_personas(...)`
  - `start_backend(...)` gains `personas: list[str] | None`, `inner_voice: str | None`, appends to CLI when set
- `examples/stanford_town/frontend/templates/landing/landing.html`
  - new persona/inner-voice block in the form
  - JS: render from `SIM_PERSONAS[fork]`, handle 全选/全不选, inner-voice auto-reassign, submit disabled state
  - form submit serializer joins selected persona names with `,`
- `examples/stanford_town/run_st_game.py`
  - `main` / `startup` gain `personas`, `inner_voice` params
  - read meta from new sim (not fork); rewrite `persona_names` if subset given; pick inner voice by name match

No new files. No new URL routes.

## 7. Manual Verification

UI feature, no unit tests. Run the dev server and check:

1. Landing renders with persona block under fork dropdown
2. Switching fork rebuilds the persona list from `SIM_PERSONAS`
3. Default: all checked, inner voice = first
4. Uncheck current inner voice → radio jumps to next checked persona
5. Uncheck all → submit disabled
6. Submit a 2-persona subset:
   - `storage/<sim_code>/reverie/meta.json` has `persona_names` of length 2
   - `logs/<sim_code>/<ts>/launch.log` contains `--personas` and `--inner_voice`
   - In the town view, only those 2 agents are present on the map
7. CLI sanity: `python run_st_game.py "idea" base_xx new_xx` (no new flags) still runs full persona set, idx 0 inner voice
8. Existing replay routes (`/replay/<sim>/0/`) unaffected for subset sims
