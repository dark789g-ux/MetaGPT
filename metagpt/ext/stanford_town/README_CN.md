## Stanford Town Game

### 前置
GA（ [generative_agents](https://github.com/joonspk-research/generative_agents) ）的前端代码已经 vendor 进本仓库，路径为 `examples/stanford_town/frontend/`，无需再单独 clone GA 仓库。

目录布局：

```
examples/stanford_town/
├── storage/              # 后端写入 + 前端读取（共享）
├── temp_storage/         # 后端写入 + 前端读取（共享）
├── compressed_storage/   # GA 自带的 demo 仿真（前端 demo 模式用）
├── frontend/             # Django 前端（vendored from GA）
└── run_st_game.py        # 后端入口
```

`metagpt/ext/stanford_town/utils/const.py` 中的 `STORAGE_PATH` / `TEMP_STORAGE_PATH` 已经指向上面的共享目录，因此后端默认写入位置与前端默认读取位置天然对齐，**无需再传 `--temp_storage_path`**。

可用的初始仿真存档（位于 `examples/stanford_town/storage/`，可作为 `fork_sim_code`）：
- `base_the_ville_isabella_maria_klaus` — 3 人小镇（Isabella / Maria / Klaus）
- `base_the_ville_n25` — 25 人小镇

如需更多 GA 论文中的真实仿真存档（July1_*, ~378 MB），请自行从 [GA 仓库](https://github.com/joonspk-research/generative_agents) 拷贝至 `examples/stanford_town/storage/`。

### 后端服务启动
执行入口为：

```bash
cd examples/stanford_town
python run_st_game.py "Host a open lunch party at 13:00 pm" "base_the_ville_isabella_maria_klaus" "test_sim"
```

`idea`为用户给第一个 Agent 的内心独白，并通过这个心声进行传播，看最后多智能体是否达到举办、参加活动的目标。

### 前端服务启动
首次启动前需安装前端依赖（独立 venv，避免污染主项目）：

```powershell
cd examples/stanford_town/frontend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install "Django==4.2.*" django-cors-headers numpy
```

启动前端：

```powershell
cd examples/stanford_town/frontend
.\.venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000
```

`manage.py` 会自动将工作目录切换到 `examples/stanford_town/`，因此 GA 前端的相对路径 `storage/` `temp_storage/` `compressed_storage/` 会直接命中上述共享目录。

访问 `http://localhost:8000/simulator_home` 进入当前仿真界面，`http://localhost:8000/replay/<sim_code>/<step>/` 重放指定仿真。

### 与 GA 上游的差异

vendor 进来的前端相对原始 GA 仓库做了以下兼容性补丁，使其可在 Python 3.12 + Django 4.2 LTS 下运行：

- `manage.py`：启动时 `chdir` 到 `examples/stanford_town/`，让 storage 与后端共享
- `frontend_server/urls.py`：`url(...)` → `re_path(...)`（Django 4.0 移除了 `url`）
- `frontend_server/settings/{base,local}.py`：从 `INSTALLED_APPS` 移除 `storages`（`django-storages-redux` 仅支持 Django 2.x）
- `frontend_server/utils.py`：移除 `from storages.backends.s3boto import ...`（生产部署 S3 钩子，本地无用）
- `translator/views.py`：`from django.contrib.staticfiles.templatetags.staticfiles import static` → `from django.templatetags.static import static`（Django 3.0 移除）
- `templates/**/*.html`：`{% load staticfiles %}` → `{% load static %}`（同上）

如需对接原始 GA 后端 `reverie/`，请直接 clone GA 仓库；MetaGPT 这边只搬了前端。

## 致谢
复现工作参考了 [generative_agents](https://github.com/joonspk-research/generative_agents), 感谢相关作者们。

### 引用
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
