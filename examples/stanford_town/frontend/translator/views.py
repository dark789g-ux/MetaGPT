"""
Author: Joon Sung Park (joonspk@stanford.edu)
File: views.py
"""
import os
import string
import random
import json
import time
from os import listdir
import os

import datetime
from datetime import datetime as _dt
from pathlib import Path

from django.shortcuts import render, redirect, HttpResponseRedirect
from django.http import HttpResponse, JsonResponse
from global_methods import *

from django.templatetags.static import static
from .models import *
from . import sim_utils

def landing(request):
  root = sim_utils.st_root()
  sims = sim_utils.list_simulations(root / "storage", root / "compressed_storage")
  fork_options = [s["sim_code"] for s in sims if s["is_base"]] or [s["sim_code"] for s in sims]
  context = {
    "simulations": sims,
    "fork_options": fork_options,
    "all_sim_codes": [s["sim_code"] for s in sims],
    "default_n_round": 30,
    "default_investment": 30.0,
  }
  return render(request, "landing/landing.html", context)


def start_simulation(request):
  if request.method != "POST":
    return JsonResponse({"ok": False, "error": "POST required."}, status=405)

  root = sim_utils.st_root()
  storage = root / "storage"

  rerun_from = (request.POST.get("rerun_from") or "").strip()
  idea = (request.POST.get("idea") or "").strip()
  sim_code = (request.POST.get("sim_code") or "").strip()
  fork_sim_code = (request.POST.get("fork_sim_code") or "").strip()
  personas_raw = (request.POST.get("personas") or "").strip()
  inner_voice = (request.POST.get("inner_voice") or "").strip() or None
  personas: list[str] | None
  if personas_raw:
    personas = [p.strip() for p in personas_raw.split(",") if p.strip()]
  else:
    personas = None

  try:
    n_round = int(request.POST.get("n_round") or 30)
  except ValueError:
    return JsonResponse({"ok": False, "error": "n_round must be an integer."}, status=400)

  investment_raw = (request.POST.get("investment") or "").strip()
  try:
    investment = float(investment_raw) if investment_raw else None
  except ValueError:
    return JsonResponse({"ok": False, "error": "investment must be a number."}, status=400)

  if rerun_from:
    fork_sim_code = rerun_from
    if not sim_code:
      sim_code = f"{rerun_from}_rerun_{_dt.now().strftime('%Y%m%d_%H%M%S')}"

  if not idea:
    return JsonResponse({"ok": False, "error": "idea is required."}, status=400)

  err = sim_utils.validate_new_sim_code(sim_code, fork_sim_code, storage)
  if err:
    return JsonResponse({"ok": False, "error": err}, status=400)

  err = sim_utils.validate_personas(personas, inner_voice, fork_sim_code, storage)
  if err:
    return JsonResponse({"ok": False, "error": err}, status=400)

  try:
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
  except Exception as exc:
    return JsonResponse({"ok": False, "error": f"failed to spawn backend: {exc}"}, status=500)

  # Wait briefly for the subprocess to write temp_storage/curr_*.json. The home
  # view depends on these files; without them it renders error_start_backend.html.
  # If the child dies during warm-up, fail fast and surface the log path.
  temp_dir = root / "temp_storage"
  curr_sim_code_file = temp_dir / "curr_sim_code.json"
  curr_step_file = temp_dir / "curr_step.json"
  ready = False
  child_exit = None
  deadline = time.monotonic() + 30.0
  while time.monotonic() < deadline:
    if curr_sim_code_file.is_file() and curr_step_file.is_file():
      ready = True
      break
    if proc.poll() is not None:
      child_exit = proc.returncode
      break
    time.sleep(0.3)

  if child_exit is not None:
    return JsonResponse({
      "ok": False,
      "error": f"backend exited during startup (code {child_exit}); see logs",
      "pid": proc.pid,
      "sim_code": sim_code,
      "log_dir": str(log_dir),
    }, status=500)

  resp = {
    "ok": True,
    "pid": proc.pid,
    "sim_code": sim_code,
    "fork_sim_code": fork_sim_code,
    "replay_url": f"/replay/{sim_code}/0/",
    "log_dir": str(log_dir),
  }
  if ready:
    resp["redirect_url"] = "/simulator_home"
  else:
    resp["warning"] = "backend still warming up; navigate manually."
  return JsonResponse(resp)


def demo(request, sim_code, step, play_speed="1"):
  move_file = f"compressed_storage/{sim_code}/master_movement.json"
  meta_file = f"compressed_storage/{sim_code}/meta.json"
  step = int(step)
  play_speed_opt = {"1": 1, "2": 2, "3": 4,
                    "4": 8, "5": 16, "6": 32}
  if play_speed not in play_speed_opt: play_speed = 2
  else: play_speed = play_speed_opt[play_speed]

  # Loading the basic meta information about the simulation.
  meta = dict() 
  with open (meta_file) as json_file: 
    meta = json.load(json_file)

  sec_per_step = meta["sec_per_step"]
  start_datetime = datetime.datetime.strptime(meta["start_date"] + " 00:00:00", 
                                              '%B %d, %Y %H:%M:%S')
  for i in range(step): 
    start_datetime += datetime.timedelta(seconds=sec_per_step)
  start_datetime = start_datetime.strftime("%Y-%m-%dT%H:%M:%S")

  # Loading the movement file
  raw_all_movement = dict()
  with open(move_file) as json_file: 
    raw_all_movement = json.load(json_file)
 
  # Loading all names of the personas
  persona_names = dict()
  persona_names = []
  persona_names_set = set()
  for p in list(raw_all_movement["0"].keys()): 
    persona_names += [{"original": p, 
                       "underscore": p.replace(" ", "_"), 
                       "initial": p[0] + p.split(" ")[-1][0]}]
    persona_names_set.add(p)

  # <all_movement> is the main movement variable that we are passing to the 
  # frontend. Whereas we use ajax scheme to communicate steps to the frontend
  # during the simulation stage, for this demo, we send all movement 
  # information in one step. 
  all_movement = dict()

  # Preparing the initial step. 
  # <init_prep> sets the locations and descriptions of all agents at the
  # beginning of the demo determined by <step>. 
  init_prep = dict() 
  for int_key in range(step+1): 
    key = str(int_key)
    val = raw_all_movement[key]
    for p in persona_names_set: 
      if p in val: 
        init_prep[p] = val[p]
  persona_init_pos = dict()
  for p in persona_names_set: 
    persona_init_pos[p.replace(" ","_")] = init_prep[p]["movement"]
  all_movement[step] = init_prep

  # Finish loading <all_movement>
  for int_key in range(step+1, len(raw_all_movement.keys())): 
    all_movement[int_key] = raw_all_movement[str(int_key)]

  context = {"sim_code": sim_code,
             "step": step,
             "persona_names": persona_names,
             "persona_init_pos": json.dumps(persona_init_pos), 
             "all_movement": json.dumps(all_movement), 
             "start_datetime": start_datetime,
             "sec_per_step": sec_per_step,
             "play_speed": play_speed,
             "mode": "demo"}
  template = "demo/demo.html"

  return render(request, template, context)


def UIST_Demo(request): 
  return demo(request, "March20_the_ville_n25_UIST_RUN-step-1-141", 2160, play_speed="3")


def home(request):
  f_curr_sim_code = "temp_storage/curr_sim_code.json"
  f_curr_step = "temp_storage/curr_step.json"

  if not check_if_file_exists(f_curr_step): 
    context = {}
    template = "home/error_start_backend.html"
    return render(request, template, context)

  with open(f_curr_sim_code) as json_file:
    sim_code = json.load(json_file)["sim_code"]

  persona_names = []
  persona_names_set = set()
  for i in find_filenames(f"storage/{sim_code}/personas", ""):
    x = i.split("/")[-1].strip()
    if x[0] != ".":
      persona_names += [[x, x.replace(" ", "_")]]
      persona_names_set.add(x)

  persona_init_pos = []
  file_count = []
  for i in find_filenames(f"storage/{sim_code}/environment", ".json"):
    x = i.split("/")[-1].strip()
    if x[0] != ".":
      file_count += [int(x.split(".")[0])]
  # Use the latest environment snapshot as the live step so refreshing the
  # town page re-enters the running sim at its current step (no more one-shot
  # curr_step.json consumption).
  step = max(file_count) if file_count else 0
  curr_json = f'storage/{sim_code}/environment/{str(step)}.json'
  with open(curr_json) as json_file:
    persona_init_pos_dict = json.load(json_file)
    for key, val in persona_init_pos_dict.items():
      if key in persona_names_set:
        persona_init_pos += [[key, val["x"], val["y"]]]

  context = {"sim_code": sim_code,
             "step": step,
             "persona_names": persona_names,
             "persona_init_pos": persona_init_pos,
             "mode": "simulate"}
  template = "home/home.html"
  return render(request, template, context)


def replay(request, sim_code, step):
  step = int(step)
  sim_dir = sim_utils.st_root() / "storage" / sim_code

  persona_names = []
  persona_names_set = set()
  personas_dir = sim_dir / "personas"
  if personas_dir.is_dir():
    for child in sorted(personas_dir.iterdir()):
      name = child.name
      if name.startswith("."):
        continue
      persona_names.append([name, name.replace(" ", "_")])
      persona_names_set.add(name)

  # Initial positions: use the latest environment snapshot at or before <step>.
  env_dir = sim_dir / "environment"
  env_steps = []
  if env_dir.is_dir():
    for f in env_dir.glob("*.json"):
      if f.stem.isdigit():
        env_steps.append(int(f.stem))
  persona_init_pos = []
  if env_steps:
    candidates = [s for s in env_steps if s <= step]
    use_step = max(candidates) if candidates else min(env_steps)
    env_file = env_dir / f"{use_step}.json"
    try:
      env_data = json.loads(env_file.read_text(encoding="utf-8"))
      for key, val in env_data.items():
        if key in persona_names_set:
          persona_init_pos.append([key, val["x"], val["y"]])
    except (OSError, json.JSONDecodeError):
      pass

  # Load every movement/<n>.json so the frontend can replay offline.
  all_movement = {}
  move_dir = sim_dir / "movement"
  if move_dir.is_dir():
    for f in move_dir.glob("*.json"):
      if not f.stem.isdigit():
        continue
      s = int(f.stem)
      try:
        data = json.loads(f.read_text(encoding="utf-8"))
      except (OSError, json.JSONDecodeError):
        continue
      data["<step>"] = s
      all_movement[s] = data

  # Backfill missing personas per step. The backend writes one persona at a
  # time, so a SIGTERM mid-step leaves the file with a subset of personas
  # (observed at step 293 of test_sim). Carry the prior frame forward so the
  # frontend doesn't crash on `frame[name]["movement"]`. First-step gaps fall
  # back to the persona's env position with a "(no frame)" description.
  if all_movement and persona_names:
    last_frame = {}
    for name, _ in persona_names:
      pos = next(((x, y) for n, x, y in persona_init_pos if n == name), None)
      if pos is not None:
        last_frame[name] = {
          "movement": [pos[0], pos[1]],
          "pronunciatio": "❓",
          "description": "(no frame) @ unknown",
          "chat": None,
        }
    for s in sorted(all_movement.keys()):
      frame_personas = all_movement[s].setdefault("persona", {})
      for name, _ in persona_names:
        if name in frame_personas:
          last_frame[name] = frame_personas[name]
        elif name in last_frame:
          frame_personas[name] = last_frame[name]

  max_step = max(all_movement.keys()) if all_movement else step

  context = {"sim_code": sim_code,
             "step": step,
             "persona_names": persona_names,
             "persona_init_pos": persona_init_pos,
             "all_movement": all_movement,
             "max_step": max_step,
             "mode": "replay"}
  return render(request, "home/home.html", context)


def replay_persona_state(request, sim_code, step, persona_name): 
  sim_code = sim_code
  step = int(step)

  persona_name_underscore = persona_name
  persona_name = " ".join(persona_name.split("_"))
  memory = f"storage/{sim_code}/personas/{persona_name}/bootstrap_memory"
  if not os.path.exists(memory): 
    memory = f"compressed_storage/{sim_code}/personas/{persona_name}/bootstrap_memory"

  with open(memory + "/scratch.json") as json_file:  
    scratch = json.load(json_file)

  with open(memory + "/spatial_memory.json") as json_file:  
    spatial = json.load(json_file)

  with open(memory + "/associative_memory/nodes.json") as json_file:  
    associative = json.load(json_file)

  a_mem_event = []
  a_mem_chat = []
  a_mem_thought = []

  for count in range(len(associative.keys()), 0, -1): 
    node_id = f"node_{str(count)}"
    node_details = associative[node_id]

    if node_details["type"] == "event":
      a_mem_event += [node_details]

    elif node_details["type"] == "chat":
      a_mem_chat += [node_details]

    elif node_details["type"] == "thought":
      a_mem_thought += [node_details]
  
  context = {"sim_code": sim_code,
             "step": step,
             "persona_name": persona_name, 
             "persona_name_underscore": persona_name_underscore, 
             "scratch": scratch,
             "spatial": spatial,
             "a_mem_event": a_mem_event,
             "a_mem_chat": a_mem_chat,
             "a_mem_thought": a_mem_thought}
  template = "persona_state/persona_state.html"
  return render(request, template, context)


def path_tester(request):
  context = {}
  template = "path_tester/path_tester.html"
  return render(request, template, context)


def process_environment(request): 
  """
  <FRONTEND to BACKEND> 
  This sends the frontend visual world information to the backend server. 
  It does this by writing the current environment representation to 
  "storage/environment.json" file. 

  ARGS:
    request: Django request
  RETURNS: 
    HttpResponse: string confirmation message. 
  """
  # f_curr_sim_code = "temp_storage/curr_sim_code.json"
  # with open(f_curr_sim_code) as json_file:  
  #   sim_code = json.load(json_file)["sim_code"]

  data = json.loads(request.body)
  step = data["step"]
  sim_code = data["sim_code"]
  environment = data["environment"]

  with open(f"storage/{sim_code}/environment/{step}.json", "w") as outfile:
    outfile.write(json.dumps(environment, indent=2))

  return HttpResponse("received")


def update_environment(request): 
  """
  <BACKEND to FRONTEND> 
  This sends the backend computation of the persona behavior to the frontend
  visual server. 
  It does this by reading the new movement information from 
  "storage/movement.json" file.

  ARGS:
    request: Django request
  RETURNS: 
    HttpResponse
  """
  # f_curr_sim_code = "temp_storage/curr_sim_code.json"
  # with open(f_curr_sim_code) as json_file:  
  #   sim_code = json.load(json_file)["sim_code"]

  data = json.loads(request.body)
  step = data["step"]
  sim_code = data["sim_code"]

  response_data = {"<step>": -1}
  if (check_if_file_exists(f"storage/{sim_code}/movement/{step}.json")):
    with open(f"storage/{sim_code}/movement/{step}.json") as json_file: 
      response_data = json.load(json_file)
      response_data["<step>"] = step

  return JsonResponse(response_data)


def path_tester_update(request): 
  """
  Processing the path and saving it to path_tester_env.json temp storage for 
  conducting the path tester. 

  ARGS:
    request: Django request
  RETURNS: 
    HttpResponse: string confirmation message. 
  """
  data = json.loads(request.body)
  camera = data["camera"]

  with open(f"temp_storage/path_tester_env.json", "w") as outfile:
    outfile.write(json.dumps(camera, indent=2))

  return HttpResponse("received")









