## Stanford Town Game

### Layout
The GA ([generative_agents](https://github.com/joonspk-research/generative_agents)) frontend is now vendored under `examples/stanford_town/frontend/`; you no longer need to clone GA separately.

```
examples/stanford_town/
├── storage/              # written by backend, read by frontend (shared)
├── temp_storage/         # written by backend, read by frontend (shared)
├── compressed_storage/   # GA-shipped demo simulations (used by frontend demo mode)
├── frontend/             # vendored Django frontend
└── run_st_game.py        # backend entrypoint
```

`metagpt/ext/stanford_town/utils/const.py` already points `STORAGE_PATH` / `TEMP_STORAGE_PATH` at the directories above, so the backend writes and the frontend reads the same locations out of the box — **the `--temp_storage_path` argument is no longer needed**.

Bootstrap simulations available in `examples/stanford_town/storage/` (use as `fork_sim_code`):
- `base_the_ville_isabella_maria_klaus` — 3-persona town (Isabella / Maria / Klaus)
- `base_the_ville_n25` — 25-persona town

For the larger July1_* simulations from the GA paper (~378 MB), copy them manually from the [GA repo](https://github.com/joonspk-research/generative_agents) into `examples/stanford_town/storage/`.

### Backend service startup

```bash
cd examples/stanford_town
python run_st_game.py "Host a open lunch party at 13:00 pm" "base_the_ville_isabella_maria_klaus" "test_sim"
```

`idea` is the inner voice handed to the first agent and propagated from there; the multi-agent system is supposed to converge on hosting/attending the event.

### Frontend service startup
First-time setup (isolated venv to avoid polluting the main project):

```powershell
cd examples/stanford_town/frontend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install "Django==4.2.*" django-cors-headers numpy
```

Run:

```powershell
cd examples/stanford_town/frontend
.\.venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000
```

`manage.py` chdirs to `examples/stanford_town/` on startup so GA's relative paths (`storage/`, `temp_storage/`, `compressed_storage/`) resolve to the shared directories above.

- `http://localhost:8000/simulator_home` — current simulation viewer
- `http://localhost:8000/replay/<sim_code>/<step>/` — replay a recorded simulation

### Patches relative to upstream GA

The vendored frontend has the following compatibility patches so it runs on Python 3.12 + Django 4.2 LTS:

- `manage.py` — chdirs to `examples/stanford_town/` so storage is shared with the backend
- `frontend_server/urls.py` — `url(...)` → `re_path(...)` (Django 4.0 removed `url`)
- `frontend_server/settings/{base,local}.py` — drop `storages` from `INSTALLED_APPS` (`django-storages-redux` is Django-2.x only)
- `frontend_server/utils.py` — drop `from storages.backends.s3boto import ...` (S3 deployment hook, unused locally)
- `translator/views.py` — `from django.contrib.staticfiles.templatetags.staticfiles import static` → `from django.templatetags.static import static` (removed in Django 3.0)
- `templates/**/*.html` — `{% load staticfiles %}` → `{% load static %}` (same as above)

If you need GA's original `reverie/` backend, clone the GA repo separately; only the frontend is vendored here.

## Acknowledgements
The reproduction work has referred the [generative_agents](https://github.com/joonspk-research/generative_agents), let's make a general statement here.  

### Citation
```bib
@inproceedings{Park2023GenerativeAgents,  
author = {Park, Joon Sung and O'Brien, Joseph C. and Cai, Carrie J. and Morris, Meredith Ringel and Liang, Percy and Bernstein, Michael S.},  
title = {Generative Agents: Interactive Simulacra of Human Behavior},  
year = {2023},  
publisher = {Association for Computing Machinery},  
address = {New York, NY, USA},  
booktitle = {In the 36th Annual ACM Symposium on User Interface Software and Technology (UIST '23)},  
keywords = {Human-AI interaction, agents, generative AI, large language models},  
location = {San Francisco, CA, USA},  
series = {UIST '23}
}
```