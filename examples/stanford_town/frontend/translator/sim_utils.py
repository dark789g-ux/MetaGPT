"""Dashboard helpers: scan storage/, validate sim codes, spawn run_st_game.py."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

# Lines matching these patterns are mirrored to llm.log / error.log respectively.
# Kept intentionally loose — false positives are cheap, missed errors are not.
_LLM_RE = re.compile(
    rb"cost_manager|st_action|_run_gpt|prompt_tokens|completion_tokens|"
    rb"Max budget|Total running cost",
    re.IGNORECASE,
)
_ERR_RE = re.compile(
    rb"traceback|exception|\| ERROR\b|\| WARNING\b|^\s*File \"|"
    rb"ModuleNotFoundError|UserWarning",
    re.IGNORECASE | re.MULTILINE,
)

_SIM_CODE_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


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


def st_root() -> Path:
    # frontend/translator/sim_utils.py -> parents[2] == examples/stanford_town/
    return Path(__file__).resolve().parents[2]


def list_simulations(storage_dir: Path, compressed_dir: Path | None = None) -> list[dict]:
    if not storage_dir.is_dir():
        return []

    rows: list[dict] = []
    for entry in storage_dir.iterdir():
        if not entry.is_dir():
            continue
        meta_path = entry / "reverie" / "meta.json"
        if not meta_path.is_file():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        movement_dir = entry / "movement"
        movement_steps = 0
        if movement_dir.is_dir():
            for f in movement_dir.iterdir():
                if f.suffix == ".json" and f.stem.isdigit():
                    movement_steps += 1

        has_compressed = bool(
            compressed_dir
            and (compressed_dir / entry.name / "master_movement.json").is_file()
        )

        if has_compressed:
            replay_url = f"/demo/{entry.name}/0/2/"
        elif movement_steps > 0:
            replay_url = f"/replay/{entry.name}/0/"
        else:
            replay_url = ""

        rows.append({
            "sim_code": entry.name,
            "fork_sim_code": meta.get("fork_sim_code", ""),
            "start_date": meta.get("start_date", ""),
            "curr_time": meta.get("curr_time", ""),
            "step": meta.get("step", 0),
            "personas": meta.get("persona_names", []),
            "is_base": entry.name.startswith("base_"),
            "mtime": meta_path.stat().st_mtime,
            "movement_steps": movement_steps,
            "has_compressed": has_compressed,
            "replay_url": replay_url,
        })

    rows.sort(key=lambda r: r["mtime"], reverse=True)
    return rows


def validate_new_sim_code(sim_code: str, fork_sim_code: str, storage_dir: Path) -> str | None:
    if not sim_code:
        return "sim_code is required."
    if not _SIM_CODE_RE.match(sim_code):
        return "sim_code may only contain letters, digits, underscore and dash."
    if not fork_sim_code:
        return "fork_sim_code is required."
    if sim_code == fork_sim_code:
        return "sim_code must differ from fork_sim_code (otherwise it would copy onto itself)."
    if (storage_dir / sim_code).exists():
        return f"sim_code '{sim_code}' already exists in storage/."
    if not (storage_dir / fork_sim_code / "reverie" / "meta.json").is_file():
        return f"fork base '{fork_sim_code}' not found in storage/."
    return None


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


def _demux_stdout(pipe, stdout_fh, llm_fh, error_fh) -> None:
    """Mirror every line to stdout.log; route LLM/error lines to their own files."""
    try:
        for line in iter(pipe.readline, b""):
            stdout_fh.write(line)
            if _LLM_RE.search(line):
                llm_fh.write(line)
            if _ERR_RE.search(line):
                error_fh.write(line)
    finally:
        for fh in (stdout_fh, llm_fh, error_fh):
            try:
                fh.close()
            except Exception:
                pass
        try:
            pipe.close()
        except Exception:
            pass


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

    env = os.environ.copy()
    env["HTTP_PROXY"] = ""
    env["HTTPS_PROXY"] = ""
    env["NO_PROXY"] = "*"
    env["PYTHONUNBUFFERED"] = "1"

    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

    (run_dir / "launch.log").write_text(
        f"$ {' '.join(cmd)}\n", encoding="utf-8"
    )

    proc = subprocess.Popen(
        cmd,
        cwd=str(st_root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
        bufsize=0,
    )

    stdout_fh = open(run_dir / "stdout.log", "wb", buffering=0)
    llm_fh = open(run_dir / "llm.log", "wb", buffering=0)
    error_fh = open(run_dir / "error.log", "wb", buffering=0)
    threading.Thread(
        target=_demux_stdout,
        args=(proc.stdout, stdout_fh, llm_fh, error_fh),
        daemon=True,
    ).start()

    return proc, run_dir
