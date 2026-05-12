#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""One-click launcher for Stanford Town frontend (Django) and backend (run_st_game).

Layout assumptions (created by the vendor-in step):

    examples/stanford_town/
        frontend/manage.py
        run_st_game.py
        storage/, temp_storage/, compressed_storage/

The frontend now runs against the same Python interpreter as MetaGPT itself
(no dedicated venv). Make sure `pip install -r requirements.txt` has installed
Django and django-cors-headers in that interpreter.

Quick start
-----------
    # Frontend only — open http://localhost:8000/simulator_home
    python launch_stanford_town.py

    # Frontend + backend (single command)
    python launch_stanford_town.py \\
        --idea "Host an open lunch party at 13:00 pm" \\
        --sim-code test_sim --n-round 30

    # Backend only (frontend already running in another shell)
    python launch_stanford_town.py --backend-only \\
        --idea "..." --sim-code test_sim

    # When the backend finishes, the frontend is *kept running* so you can
    # immediately replay the simulation in the browser. Press Ctrl+C to stop
    # the frontend (or pass --strict-shutdown to revert to "any-exits-all-stop").
"""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ST_ROOT = ROOT / "examples" / "stanford_town"
FRONTEND_DIR = ST_ROOT / "frontend"
BACKEND_SCRIPT = ST_ROOT / "run_st_game.py"

IS_WINDOWS = os.name == "nt"


# ---------------------------------------------------------------------------
# Pretty output
# ---------------------------------------------------------------------------
def _stream(proc: subprocess.Popen, tag: str) -> None:
    """Forward a child process's combined stdout to our stdout, prefixed."""
    assert proc.stdout is not None
    for raw in iter(proc.stdout.readline, b""):
        try:
            line = raw.decode("utf-8", errors="replace").rstrip()
        except Exception:
            line = repr(raw)
        print(f"[{tag}] {line}", flush=True)
    proc.stdout.close()


def _spawn(cmd: list[str], cwd: Path, tag: str, extra_env: dict | None = None) -> subprocess.Popen:
    """Start a child process with merged stdout/stderr and a tagged log thread."""
    env = os.environ.copy()
    # Bypass the global proxy that's set on this machine but often offline.
    env["HTTP_PROXY"] = ""
    env["HTTPS_PROXY"] = ""
    env["NO_PROXY"] = "*"
    # Force unbuffered Python output so our line-by-line forwarding stays live.
    env["PYTHONUNBUFFERED"] = "1"
    if extra_env:
        env.update(extra_env)

    creationflags = 0
    if IS_WINDOWS:
        # Put the child in its own process group so we can send CTRL_BREAK_EVENT.
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

    print(f"[{tag}] $ {' '.join(cmd)}  (cwd={cwd})", flush=True)
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )
    threading.Thread(target=_stream, args=(proc, tag), daemon=True).start()
    return proc


def _terminate(procs: list[subprocess.Popen]) -> None:
    """Best-effort graceful shutdown of all child processes."""
    for p in procs:
        if p.poll() is not None:
            continue
        try:
            if IS_WINDOWS:
                p.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                p.terminate()
        except Exception:
            pass

    deadline = time.monotonic() + 5.0
    for p in procs:
        remaining = max(0.1, deadline - time.monotonic())
        try:
            p.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            try:
                p.kill()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
def _check_layout(need_frontend: bool, need_backend: bool) -> None:
    if not ST_ROOT.is_dir():
        sys.exit(f"[launch] Stanford Town root not found: {ST_ROOT}")

    if need_backend and not BACKEND_SCRIPT.is_file():
        sys.exit(f"[launch] Backend entry not found: {BACKEND_SCRIPT}")

    if need_frontend:
        if not FRONTEND_DIR.is_dir():
            sys.exit(
                f"[launch] Frontend directory missing: {FRONTEND_DIR}\n"
                "         Did you finish the vendor-in step?"
            )
        try:
            import django  # noqa: F401
            import corsheaders  # noqa: F401
        except ImportError as exc:
            sys.exit(
                f"[launch] Frontend dependency missing in current Python ({sys.executable}): {exc.name}\n"
                "         Install MetaGPT requirements first:\n"
                f"           {sys.executable} -m pip install -r requirements.txt"
            )


# ---------------------------------------------------------------------------
# Process commands
# ---------------------------------------------------------------------------
def _frontend_cmd(host: str, port: int) -> list[str]:
    return [
        sys.executable,
        "manage.py",
        "runserver",
        f"{host}:{port}",
        "--noreload",
    ]


def _backend_cmd(args: argparse.Namespace) -> list[str]:
    cmd = [
        sys.executable,
        str(BACKEND_SCRIPT),
        args.idea,
        args.fork_sim_code,
        args.sim_code,
    ]
    if args.investment is not None:
        cmd += ["--investment", str(args.investment)]
    if args.n_round is not None:
        cmd += ["--n_round", str(args.n_round)]
    return cmd


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="One-click launcher for Stanford Town (frontend + backend).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--frontend-only",
        action="store_true",
        help="Start only the Django frontend (default when --idea is not provided).",
    )
    mode.add_argument(
        "--backend-only",
        action="store_true",
        help="Start only the MetaGPT backend (frontend assumed running elsewhere).",
    )

    p.add_argument("--host", default="0.0.0.0", help="Frontend bind host (default: 0.0.0.0).")
    p.add_argument("--port", type=int, default=8000, help="Frontend bind port (default: 8000).")
    p.add_argument(
        "--strict-shutdown",
        action="store_true",
        help="Stop the frontend as soon as the backend exits. "
        "Default behaviour keeps the frontend running so you can replay the simulation.",
    )

    bk = p.add_argument_group("backend options (passed to run_st_game.py)")
    bk.add_argument("--idea", help='Inner voice for the first agent, e.g. "Host an open lunch party at 13:00 pm".')
    bk.add_argument(
        "--fork-sim-code",
        default="base_the_ville_isabella_maria_klaus",
        help="Bootstrap simulation to fork (default: base_the_ville_isabella_maria_klaus).",
    )
    bk.add_argument("--sim-code", help="New simulation name to write into storage/ (must be unique).")
    bk.add_argument("--n-round", type=int, default=30, help="Backend rounds to run (default: 30).")
    bk.add_argument("--investment", type=float, default=None, help="Token budget in USD (default: 30.0).")

    args = p.parse_args()

    # Decide which processes to launch.
    if args.backend_only:
        args._run_frontend, args._run_backend = False, True
    elif args.frontend_only:
        args._run_frontend, args._run_backend = True, False
    else:
        args._run_frontend = True
        args._run_backend = bool(args.idea)

    if args._run_backend:
        if not args.idea:
            p.error("--idea is required to start the backend (or pass --frontend-only).")
        if not args.sim_code:
            p.error("--sim-code is required to start the backend.")
        if args.sim_code == args.fork_sim_code:
            p.error("--sim-code must differ from --fork-sim-code (otherwise it copies onto itself).")

    return args


def main() -> int:
    args = parse_args()
    _check_layout(need_frontend=args._run_frontend, need_backend=args._run_backend)

    # Map each child process to its tag so we don't have to guess later.
    procs: dict[subprocess.Popen, str] = {}
    try:
        if args._run_frontend:
            front = _spawn(_frontend_cmd(args.host, args.port), cwd=FRONTEND_DIR, tag="FRONT")
            procs[front] = "FRONT"
            # Give Django a head start so backend's first writes are visible immediately.
            time.sleep(1.5)
            # When the backend is also being launched, /simulator_home is the live view.
            # Otherwise point users at the Dashboard (/) for archive replay & launching new sims.
            entry = "/simulator_home" if args._run_backend else "/"
            print(f"[launch] Frontend: http://localhost:{args.port}{entry}", flush=True)

        if args._run_backend:
            back = _spawn(_backend_cmd(args), cwd=ST_ROOT, tag="BACK")
            procs[back] = "BACK"
            print(
                f"[launch] Backend writing to: {ST_ROOT / 'storage' / args.sim_code}",
                flush=True,
            )

        if not procs:
            print("[launch] Nothing to do.", flush=True)
            return 0

        last_exit_rc = 0
        while procs:
            # Snapshot of children that finished since the last poll.
            exited = [(p, t) for p, t in procs.items() if p.poll() is not None]
            for p, tag in exited:
                rc = p.returncode
                last_exit_rc = rc or last_exit_rc
                print(f"[launch] {tag} exited with code {rc}.", flush=True)
                procs.pop(p, None)

            if exited:
                exited_tags = {t for _, t in exited}
                front_alive = any(t == "FRONT" for t in procs.values())
                back_alive = any(t == "BACK" for t in procs.values())

                # Frontend died: backend can't be observed -> always stop it too.
                if "FRONT" in exited_tags and back_alive:
                    print("[launch] Frontend exited; stopping backend too.", flush=True)
                    return last_exit_rc

                # Backend died: by default keep the frontend up for replay viewing.
                if "BACK" in exited_tags and front_alive:
                    if args.strict_shutdown:
                        print("[launch] --strict-shutdown set; stopping frontend too.", flush=True)
                        return last_exit_rc
                    sim_hint = args.sim_code or "<sim_code>"
                    print(
                        "[launch] Backend done. Frontend kept running — view your run at:\n"
                        f"[launch]   http://localhost:{args.port}/replay/{sim_hint}/0/   (start)\n"
                        f"[launch]   http://localhost:{args.port}/replay/{sim_hint}/<step>/   (any frame)\n"
                        "[launch] Press Ctrl+C to stop the frontend.",
                        flush=True,
                    )

            time.sleep(0.5)

        return last_exit_rc

    except KeyboardInterrupt:
        print("\n[launch] Ctrl+C received, stopping children...", flush=True)
        return 130
    finally:
        _terminate(list(procs.keys()))
        print("[launch] Done.", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
