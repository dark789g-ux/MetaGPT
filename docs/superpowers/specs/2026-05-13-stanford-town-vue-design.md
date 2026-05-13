# Stanford Town Vue — 设计文档

- **日期**：2026-05-13
- **作者**：Ren（与 Claude 协作起草）
- **状态**：草案，待审阅
- **目标交付物**：一个独立可发布的代码仓库 `stanford-town-vue`，使用 Vue3 + Ant Design + FastAPI + SQLite 复刻 `examples/stanford_town` 的全部功能，零 MetaGPT 外部依赖。

---

## 1. 背景与目标

`examples/stanford_town` 当前实现：
- 基于 MetaGPT 框架的多 Agent 行为仿真（复现 Park et al. 2023 "Generative Agents"）。
- 后端：MetaGPT `Team` / `Role` / `Environment` / `Action` + 三层记忆系统 + LLM 调用。
- 前端：Django 4.2 + Bootstrap 3 + 原生 JS + Pixi.js 渲染 2D 瓦片地图。
- 存储：`storage/{sim_code}/` 下大量 JSON 文件。
- 4 个功能页：仪表盘、实时仿真 viewer、回放 viewer、LLM 日志 + 人格状态。

### 本项目目标

1. **技术栈替换**：Django → FastAPI，Bootstrap → Ant Design Vue，原生 JS → Vue 3 + Pinia + TypeScript，JSON 文件 → SQLite（保留 JSON 双向 I/O）。
2. **完全独立仓库**：新代码 `pip install` 后无需依赖 `metagpt` 包，相关代码全部 vendor 进新仓库。
3. **1:1 功能复刻**：4 个页面全部对齐原版，地图 Pixi.js 高保真。
4. **可扩展底座**：未来可独立演进，不再被上游 MetaGPT 变更约束。

### 非目标

- 不重写 Agent 算法（沿用 MetaGPT 已实现的 Role/Action 体系，vendor 即可）。
- 不保留 embedding 语义检索（简化为 recency + importance + keyword 三维评分；后续可加回）。
- 不支持除 OpenAI / DeepSeek / Anthropic 之外的 LLM provider（其他可后续扩展）。
- 不做多用户、不做云部署、不做认证授权（单机本地工具）。

---

## 2. 总览与仓库结构

**仓库名**：`stanford-town-vue`，初始位于 `c:\Users\dark7\projects\MetaGPT\stanford-town-vue\`，后续可独立 `git init` 为单独仓库。

**整体形态**：
- 单进程 FastAPI 应用承载 REST API + WebSocket Hub + asyncio 仿真任务。
- 前端 Vue3+AntD SPA：开发期 vite proxy 到 :8000，生产期由 FastAPI staticfiles 托管 `frontend/dist`。
- SQLite 作为所有仿真数据的单一真实源，保留与原版 JSON 格式的双向 I/O。

### 目录树

```
stanford-town-vue/
├── backend/
│   ├── pyproject.toml
│   ├── app/                    FastAPI 应用层
│   │   ├── main.py             uvicorn entry / lifespan
│   │   ├── routes/             REST 路由模块（sims / llm_logs / personas / config / imports / llm_profiles / meta）
│   │   ├── ws/                 WebSocket hub + 事件协议
│   │   └── deps.py             依赖注入（DB session / settings）
│   ├── core/                   vendored MetaGPT 必需框架代码（裁剪后）
│   │   ├── action.py, role.py, team.py, schema.py, context.py
│   │   ├── llm/                openai / deepseek / anthropic 三个 provider
│   │   ├── config/             简化配置系统
│   │   ├── memory.py           Memory 基类
│   │   ├── environment/        Env 抽象 + stanford_town_env + env_space
│   │   ├── utils/              common.py 等工具
│   │   ├── logs.py
│   │   └── const.py
│   ├── simulator/              vendored stanford_town 业务逻辑
│   │   ├── actions/            12 个 Action
│   │   ├── memory/             AgentMemory / Scratch / MemoryTree / retrieve
│   │   ├── plan/               st_plan / converse
│   │   ├── reflect/            reflect / generate_poig_score
│   │   ├── roles/              STRole
│   │   ├── town.py             StanfordTown(Team) 子类
│   │   └── prompts/            prompt 模板（~50 txt 文件）
│   ├── storage/                SQLAlchemy 模型 + Repo + JSON I/O
│   │   ├── models.py
│   │   ├── repos/              SimulationRepo / PersonaRepo / MemoryRepo / StepRepo / LlmLogRepo / LlmProfileRepo
│   │   ├── importer.py
│   │   └── exporter.py
│   ├── runner/                 SimulationManager + 内存 EventBus
│   │   ├── manager.py
│   │   └── events.py
│   ├── assets/                 maze tiles / matrix / sprites（从原版搬）
│   └── tests/
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── main.ts / App.vue / router.ts
│   │   ├── api/                axios + WS 客户端
│   │   ├── stores/             Pinia stores
│   │   ├── views/              路由级页面
│   │   ├── components/         按域分组
│   │   ├── pixi/               Pixi 引擎封装（与 Vue 解耦的 TS class）
│   │   └── types/              openapi-typescript 生成
├── docs/                       README / 部署 / 数据模型
├── scripts/                    dev.ps1 / build.ps1 / copy_assets.py
├── .gitignore
└── README.md
```

---

## 3. Vendor 范围

目标：vendor 后 `backend/` 不需要 `pip install metagpt`。

### A. `backend/simulator/`：整树复制
来源：`metagpt/ext/stanford_town/` 全量。

| 子目录 | 文件数 | 内容 |
|---|---|---|
| `actions/` | 12 | st_action, decide_to_talk, gen_daily_schedule, gen_hourly_schedule, gen_action_details, gen_iter_chat_utt, agent_chat_sum_rel, summarize_conv, task_decomp, wake_up, new_decomp_schedule, run_reflect_action, inner_voice_action, dummy_action |
| `memory/` | 4 | agent_memory（BasicMemory）/ scratch / spatial_memory（MemoryTree）/ retrieve |
| `plan/` | 2 | st_plan / converse |
| `reflect/` | 1 | reflect |
| `roles/` | 1 | st_role（STRole） |
| `utils/` | 4 | const / utils / llm_logger / mg_ga_transform |
| `prompts/` | ~50 | prompt 模板原样搬 |
| `stanford_town.py` | 1 | StanfordTown(Team) |

**改动**：所有 `from metagpt.xxx import ...` 改为 `from backend.core.xxx ...` 或 `from backend.simulator.xxx ...`。所有 `read_json_file / write_json_file` 替换为 Repo 调用。

### B. `backend/core/`：裁剪后的 MetaGPT 框架核心

| 模块 | 来源 | 备注 |
|---|---|---|
| `core/schema.py` | `metagpt/schema.py` | Message + 相关 BaseModel，剪枝只留 stanford_town 实际用到的类 |
| `core/context.py` | `metagpt/context.py` | Context |
| `core/team.py` | `metagpt/team.py` | Team 基类 |
| `core/role.py` | `metagpt/roles/role.py` | Role + RoleContext |
| `core/action.py` | `metagpt/actions/action.py` + `add_requirement.py` | Action 基类 + UserRequirement |
| `core/memory.py` | `metagpt/memory/memory.py` | Memory 基类 |
| `core/environment/` | `metagpt/environment/__init__.py` + `metagpt/environment/stanford_town/*` | Env 抽象 + StanfordTownEnv + env_space |
| `core/llm/` | `metagpt/provider/{openai_api, deepseek_api, anthropic_api}.py` + `metagpt/llm.py` | **仅 3 个 provider** |
| `core/config/` | `metagpt/config2.py` + `metagpt/configs/llm_config.py` | 简化版 |
| `core/utils/common.py` | `metagpt/utils/common.py` | 只拷用到的函数 |
| `core/logs.py` | `metagpt/logs.py` | logger |
| `core/const.py` | `metagpt/const.py` | 常量本地化 |

### C. 明确不 vendor
- `metagpt/rag/` / `document_store/` / `tools/` 等无关子系统
- OpenAI / DeepSeek / Anthropic 之外的所有 LLM provider
- 其它 SoftwareCompany / DataInterpreter / werewolf / aflow 等扩展

### D. 操作方式
**手动复制**（用户选择）。一次性搬过来后独立维护，上游 MetaGPT 后续变更不再自动同步。

### E. 已知挑战
1. `metagpt/schema.py` 较大，需剪枝。
2. `~/.metagpt/config2.yaml` 兼容读取——保留对此路径的兼容，但项目自带 `backend/config/default.yaml`。
3. `environment.stanford_town.env_space` 引用 gymnasium——保留此依赖。
4. asyncio：vendor 后需审一遍代码，确保没有顶层 `asyncio.run(...)` 与 uvicorn loop 冲突。

---

## 4. 数据层（SQLite + JSON I/O）

SQLite 是单一真实源。原版 JSON 文件只出现在导入/导出场景。

### 表设计（13 张表，按领域分组）

**仿真元数据**
- `simulations` — id, sim_code, fork_sim_code, status (idle|running|paused|completed|failed|interrupted|stopped), start_time_iso, curr_time_iso, sec_per_step, step, maze_name, idea, inner_voice, n_round, investment, created_at, error_message
- `simulation_config_snapshots` — sim_id, llm_profile_json, persona_filter_json（启动时刻配置快照）

**人格与空间**
- `personas` — id, sim_id, name, age, plan_text, scratch_json
- `spatial_memory_trees` — id, persona_id, tree_json

**记忆**
- `memory_nodes` — id, persona_id, node_id, node_type (event|thought|chat), node_count, type_count, depth, created (step int), expiration_step, subject, predicate, object, description, poignancy, keywords_json, filling_json
- `memory_keywords_to_event` / `memory_keywords_to_chat` / `memory_keywords_to_thought` — 倒排索引（persona_id, keyword, node_id）

**世界状态（每 step 一行）**
- `step_environments` — id, sim_id, step, payload_json（每个 persona 的 x,y,maze）
- `step_movements` — id, sim_id, step, persona_name, x, y, description, pronunciatio, chat_json, location_path

**LLM 日志**
- `llm_calls` — id, sim_id, persona_name, step, ts, model, provider, prompt, response, prompt_tokens, completion_tokens, latency_ms, error

**应用层**
- `llm_profiles` — id, name, provider, model, api_key (Fernet 加密), base_url, max_tokens, temperature, extra_json
- `app_settings` — k, v

### 索引
- `memory_nodes(persona_id, node_type, created)`
- `step_movements(sim_id, step)`
- `llm_calls(sim_id, ts)`

### Repo 层
按领域分文件，每个 Repo 暴露的方法 ≤ 10：
- `SimulationRepo` / `PersonaRepo` / `MemoryRepo`（最复杂）/ `StepRepo` / `LlmLogRepo` / `LlmProfileRepo`

**关键约束**：Repo 是仿真内核与存储的**唯一接口**。Vendor 后的 `scratch.py / spatial_memory.py / agent_memory.py / llm_logger.py / mg_ga_transform.py` 中所有文件 I/O 全部改为 Repo 调用。

### Embedding 简化
- **本期不实现 embedding 语义检索**。
- Vendor 的 `retrieve.py` 修改：去掉 embedding 相似度评分，保留 recency + importance + keyword overlap 三维。
- 每次 retrieve 时 Repo 把该 persona 全部 `memory_nodes` 加载到内存，Python 排序。
- 删除 `memory_embeddings` 表与 faiss 依赖。

### JSON I/O

**导入器** `storage/importer.py`：
- 入参：原版 `storage/<sim_code>/` 或 `compressed_storage/<sim_code>/` 路径。
- 解析：reverie/meta.json → simulations；personas/{name}/bootstrap_memory/{scratch, spatial_memory, associative_memory} → personas / spatial_memory_trees / memory_nodes；environment/*.json + movement/*.json → step_environments / step_movements；llm_logs.jsonl → llm_calls。

**导出器** `storage/exporter.py`：
- 出参：`<out_dir>/<sim_code>/`，完全等价于原版目录结构。
- 用途：与原版 Django 仿真器互换数据；CI 测试可比对 fixture。

### Migration
Alembic，初始 schema 一次 `revision --autogenerate`，后续走标准 migration。

---

## 5. 运行时（SimulationManager + EventBus + WS Hub）

### 组件图

```
┌────────────────────────────────────────────────┐
│              FastAPI 进程 (uvicorn)             │
│                                                │
│  ┌──────────────┐    ┌───────────────────┐     │
│  │ HTTP routes  │    │  WebSocket Hub    │     │
│  │ (REST API)   │    │  (per-sim rooms)  │     │
│  └──────┬───────┘    └─────────▲─────────┘     │
│         │ ctrl                  │ broadcast    │
│         ▼                       │              │
│  ┌─────────────────────┐  subscribe            │
│  │ SimulationManager   │──────────┐            │
│  │  - start/pause/stop │          │            │
│  │  - dict[sim_id→Task]│          │            │
│  └─────────┬───────────┘          │            │
│            │ spawn asyncio.Task   │            │
│            ▼                      │            │
│  ┌─────────────────────┐  ┌──────────────┐     │
│  │ simulator.town      │─▶│ EventBus     │     │
│  │ (vendored Stanford- │  │ asyncio Queue│     │
│  │  Town.run())        │  │ per sim      │     │
│  │ 写 DB (via Repo)    │  └──────▲───────┘     │
│  └─────────┬───────────┘         │             │
│            │                     │             │
│            ▼                     │             │
│       ┌──────────┐                              │
│       │  SQLite  │◀───────────────              │
│       └──────────┘                              │
└────────────────────────────────────────────────┘
```

### SimulationManager
单例。

```python
class SimulationManager:
    async def start(sim_code, params) -> sim_id   # 创建 DB 行 + spawn asyncio.Task
    async def pause(sim_id)
    async def resume(sim_id)
    async def stop(sim_id)
    def status(sim_id) -> dict
    def list_running() -> list
```

任务体 `_run(sim_id)`：
1. 实例化 vendored `StanfordTown` + `STRole`。
2. 注入 Repo 替代文件 I/O。
3. 每步末尾 `await event_bus.emit(sim_id, "step", payload)`。
4. `try/except` 包整个 loop——异常写 DB `status=failed` + `error_message`。
5. 监听 `paused` flag，暂停时 `await asyncio.sleep(0.5)` 自旋。

### EventBus
进程内 pub-sub（纯内存）。事件类型：
- `step` — `{step, curr_time, movements: [...]}`
- `status` — running ↔ paused / completed / failed
- `llm_call` — 可选，LLM 调用流式刷新
- `error` — 服务端错误推送
- `pong` — 心跳响应

### WebSocket Hub
URL：`/ws/sim/{sim_id}`

握手：
```
client → server: {"action": "subscribe", "since_step": N}
server → client: {"event": "snapshot", "sim": {...}, "current_step": M}
server → client: {"event": "step", "step": N+1, ...} (回放历史)
... 一直推到 current_step
server → client: {"event": "step", ...} (实时新增)
```

控制走 REST（pause/resume/stop），WS 单向接收。

### asyncio 兼容性
- vendor 后审一遍，移除任何 `asyncio.run(...)` 顶层硬调用。
- LLM 调用走 `httpx.AsyncClient`，non-blocking。
- 单 step 频率（~1s）下 GIL 与 CPU 阻塞不构成瓶颈。

### 回放与实时统一管道
回放和实时的传输路径**统一**——前端不区分数据来源，区别只在 UI 控制（仿真状态、速度调节是否可用）。

---

## 6. API 表面

错误体统一 `{detail: "...", code: "..."}`。

### REST

**仿真生命周期**
| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/sims` | 创建并启动；body：`{sim_code, fork_sim_code?, personas[], inner_voice?, idea?, n_round, start_hms, llm_profile_id?, sec_per_step?}` |
| `GET`  | `/api/sims` | 列表 dashboard，支持 `?status=` |
| `GET`  | `/api/sims/{id}` | 详情 |
| `POST` | `/api/sims/{id}/pause` |  |
| `POST` | `/api/sims/{id}/resume` |  |
| `POST` | `/api/sims/{id}/stop` | 取消 task，置为 stopped |
| `DELETE` | `/api/sims/{id}` | 软删（保留 DB 行） |

**仿真数据查询**
| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/sims/{id}/steps?from=X&to=Y` | 范围查询 step_movements + step_environments |
| `GET` | `/api/sims/{id}/steps/{step}` | 单步快照 |
| `GET` | `/api/sims/{id}/personas` | 人格列表 |
| `GET` | `/api/sims/{id}/personas/{name}/state?step=N` | scratch + spatial + 最近 K 条 memory_nodes |
| `GET` | `/api/sims/{id}/personas/{name}/memory?type=event&before_step=N` | 分页查 |

**LLM 日志**
| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/sims/{id}/llm-logs?offset=N&limit=100&persona=X&model=Y` | 分页 + 过滤 |
| `GET` | `/api/sims/{id}/llm-logs/{call_id}` | 单条详情 |

**JSON I/O**
| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/sims/import` | body：`{source_path}` |
| `POST` | `/api/sims/{id}/export` | body：`{target_dir}` |
| `GET` | `/api/sims/import/forks` | 列举可作为 fork 源的目录 |

**LLM 配置预设**
| 方法 | 路径 | 说明 |
|---|---|---|
| `GET / POST` | `/api/llm-profiles` | 列表 / 创建 |
| `PUT / DELETE` | `/api/llm-profiles/{id}` | 修改 / 删除 |
| `POST` | `/api/llm-profiles/{id}/test` | 连通性测试 |

**应用元数据**
| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/meta/personas` | 列举可选 personas（扫 assets） |
| `GET` | `/api/meta/maps` | 列举可用地图 |
| `GET` | `/api/config/effective` | 生效配置视图（密钥脱敏） |

### WebSocket
单一 endpoint `WS /ws/sim/{sim_id}`，见 §5。

### OpenAPI
FastAPI 自动生成。前端 `pnpm run gen:api` 调 openapi-typescript 生成 `frontend/src/types/api.ts`。

---

## 7. 前端架构

### 技术栈
Vue 3 + `<script setup>` + TypeScript + Vite + Vue Router 4 + Pinia + Ant Design Vue + Pixi.js v7 + axios + native WebSocket + openapi-typescript。

### 路由
```
/                          DashboardView           仿真列表 + 启动入口
/sims/new                  NewSimulationView       启动表单
/sims/:id/live             SimViewerView mode=live 实时 viewer
/sims/:id/replay           SimViewerView mode=replay 回放 viewer
/sims/:id/llm-logs         LlmLogsView
/sims/:id/personas/:name   PersonaStateView
/settings/llm-profiles     LlmProfilesView
/settings/imports          ImportExportView
```

Live 与 Replay 复用同一 `SimViewerView`，差别在 props 与工具栏。

### Pinia stores
- `useSimulationsStore` — dashboard 列表 + CRUD
- `useSimSessionStore` — 单仿真 session（步序列 buffer / 当前播放 step / 速度），Live/Replay 共用
- `useLlmLogsStore` — 分页 + 过滤 + tail
- `usePersonaStateStore` — 当前 persona 详情
- `useLlmProfilesStore`
- `useAppConfigStore`

### 组件结构
见 §6 章节中目录树。要点：
- `pixi/` 与 Vue 解耦：纯 TS class `Renderer`，对外 imperative API（`setStep / setSpeed / focusOnAgent`），`MapCanvas.vue` 只负责生命周期与 watch store。
- 资源加载：原版 maze assets 由后端 staticfiles 托管 `/static/maze/...`，前端 fetch 一次 + IndexedDB 缓存。

### 数据流（实时仿真）
```
WS client → Pinia (useSimSessionStore.appendStep)
         → MapCanvas.vue (watch store.currentStep)
         → Renderer.setStep(...)
         → AgentSprite.update(x, y, dir, chat)
```

### 启动表单字段
sim_code（必填，唯一校验） / fork_sim_code（下拉，可空） / personas（多选） / inner_voice（textarea） / idea（textarea） / start_hms（time picker，默认 07:00:00） / n_round（默认 200） / sec_per_step（默认 10） / llm_profile_id（下拉 + 新建按钮）/ LLM 临时覆盖（折叠面板）。

---

## 8. 配置与启动

### 配置优先级（高 → 低）
1. 启动表单临时 LLM 覆盖（仅单仿真生效）
2. UI 选中的 LLM Profile
3. `backend/config/default.yaml`（不含密钥）
4. 环境变量（`DEEPSEEK_API_KEY` 等）
5. `~/.metagpt/config2.yaml`（兼容已有 MetaGPT 用户）

`/api/config/effective` 返回合并视图，密钥脱敏。

### LLM Profile 加密
- `cryptography.Fernet`，主密钥取自 `STT_VUE_SECRET_KEY` 环境变量。
- 未设置时自动生成并写 `~/.stanford-town-vue/secret.key`（warn 用户备份）。

### 启动序列
```
1. uvicorn app.main:app
2. lifespan startup:
   a. 加载 default.yaml 与 ~/.metagpt/config2.yaml
   b. Alembic upgrade head
   c. 检查 master key，缺则生成
   d. 实例化 SimulationManager + EventBus（挂 app.state，单例）
   e. 扫描 simulations 表，status=running 的标记为 interrupted（不自动恢复）
3. 前端 dev: pnpm dev → vite proxy
4. 前端 prod: FastAPI staticfiles 托管 frontend/dist
```

### 首次启动 UX
检测无 LLM Profile 时引导：选 provider → 填 api_key/base_url → 选 model → 点测试 → 成功后回 Dashboard。

### 资源 bootstrap
启动时检查 `backend/assets/maze/the_ville/...` 是否就绪，缺则 README 指引（提供 `scripts/copy_assets.py`）。

### 开发与部署
**开发**
```
cd backend && pip install -e . && alembic upgrade head && uvicorn app.main:app --reload
cd frontend && pnpm install && pnpm dev   # 访问 http://localhost:5173
```

**生产**
```
cd frontend && pnpm build
cd backend && python -m app.bundle_frontend ../frontend/dist
uvicorn app.main:app --host 0.0.0.0 --port 8000   # 单端口
```

### 日志
- 后端 stdout：loguru。
- 仿真日志：`~/.stanford-town-vue/logs/sim_{id}.log`。
- LLM 调用：DB `llm_calls`。

---

## 9. 里程碑（分阶段交付）

### M1：脚手架 + Vendor 完成
- 新仓库目录 + pyproject + package.json + Vite + uvicorn
- 手动 vendor §3 全部代码，import 改写修通
- 编译性测试：`python -m simulator.town --help` 不报错
- Pinia/router 空壳 + Dashboard 静态页
- **演示**：后端起得来，前端空 Dashboard 可访问

### M2：数据层 + JSON 导入
- SQLAlchemy 13 张表 + Alembic initial migration
- importer：能导入一个 `compressed_storage/<sim>` 完整仿真
- exporter：导出回原版格式（CI 验证导入→导出 diff = 0）
- Repo 层就位
- **演示**：CLI 跑 import，sqlite browser 看到所有数据

### M3：API + WS + 仿真接入
- FastAPI routes 全部路径
- SimulationManager 跑通：vendor 后的 StanfordTown task，每步写 DB + emit
- WS hub：实时推 + 历史回放推
- **演示**：curl 起一个 5 round 小仿真，wscat 收 step 事件

### M4：Pixi 地图 + 回放 viewer
- `pixi/{Renderer, TileMap, AgentSprite, Camera}`
- `SimViewerView` Replay 模式：播放/暂停/调速/跳步
- Agent card 列表
- **演示**：浏览器完整看完一个论文 demo 仿真回放，视觉与原版一致

### M5：实时仿真 + 启动表单
- `NewSimulationView` 启动表单
- `SimViewerView` Live 模式 + WS 接入
- LLM Profile 管理页 + 首次引导
- 暂停/恢复/停止
- **演示**：UI 上点新建，3 persona 跑 20 round，实时看 agent 在地图移动对话

### M6：LLM 日志 + 人格状态 + Polish
- `LlmLogsView` + `LlmCallDetail`
- `PersonaStateView`（memory tree + scratch + spatial）
- 错误处理 polish
- README + 部署文档
- `scripts/copy_assets.py`
- **演示**：完整功能闭环，可作为独立仓库 push

### 风险与缓解
| 风险 | 缓解 |
|---|---|
| Vendor import 改写遗漏 | M1 写 `pytest` 试装载所有模块，CI 兜底 |
| 原版各 demo 字段微差 | importer 写宽松解析 + 单测每个 demo |
| Pixi v7 + Vite 配置 hiccup | M4 早期单独验证一个 hello world scene |
| asyncio.run 残留 | M1 vendor 后即跑空跑 sanity test |
| Embedding 简化后 retrieval 精度下降 | 本期不验证，留作后续可选 PR |

---

## 10. 决策摘要

| 决策点 | 选择 | 备注 |
|---|---|---|
| Agent 模拟核心 | Vendor MetaGPT 必需代码到新仓库 | 零外部依赖 |
| FastAPI 与仿真集成 | 单进程 in-process asyncio task | 简单、WS 推送直接 |
| 数据存储 | 全量 SQLite + 双向 JSON I/O | 单一真实源 + 兼容原版 |
| 地图渲染 | Pixi.js v7（与原版一致） | 1:1 视觉还原 |
| 前后端同步 | WebSocket 推送 | 实时与回放统一管道 |
| LLM 配置来源 | 默认 + UI 覆盖（5 层优先级） | 灵活 |
| LLM Provider | OpenAI / DeepSeek / Anthropic（vendor 3 个） | 其它后续按需扩展 |
| Embedding 检索 | 本期不实现，简化为 3 维评分 | 删除 faiss 依赖 |
| Vendor 操作 | 手动复制，一次性维护 | 上游 fork 后不再同步 |
| 部署形态 | 单机本地、单进程、单端口 | 不做认证 / 多用户 / 云 |
