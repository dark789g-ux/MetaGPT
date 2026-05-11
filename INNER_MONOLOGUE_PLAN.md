# 让 DeepSeek 思考链成为 Stanford Town 的"内心独白"

> 实施计划。范围：`metagpt/ext/stanford_town/` + `metagpt/configs` / `metagpt/provider` 极少量框架级改动。

## 背景与动机

DeepSeek 思考模式（`deepseek-v4-flash` 等模型默认启用）会在最终答案 `content` 之前先输出一段 `reasoning_content`（思维链）。当前的 Stanford Town 在思考模式下要么把 CoT 当浪费的 token 丢掉（甚至导致 `content` 为空），要么干脆关闭思考模式。

本计划把 `reasoning_content` 接入 agent 的 `thought_list`，让 LLM 的内部思考真正成为 agent 的"内心独白"——既被持久化、被检索、又会反过来影响后续 prompt。这是对生成式 agents 论文中"internal thoughts"概念最贴近的工程还原。

参考文档：
- [DeepSeek 思考模式](https://api-docs.deepseek.com/zh-cn/guides/thinking_mode)
- 项目内 `.claude/skills/deepseek-api-docs/SKILL.md`

## 目标 / 非目标

**目标**

1. DeepSeek `reasoning_content` 不再被丢弃，而是结构化沉淀进 `AgentMemory.thought_list`，并影响后续 prompt。
2. 框架级改动尽量薄、可复用，不破坏其他 MetaGPT 模块。
3. 选择性启用，避免 token 成本爆炸。

**非目标**

- 不改写 Stanford Town 的 prompt 体系；那些 `_run_gpt35_max_tokens` 小调用（WakeUp、GenPronunciatio 等）继续走 `thinking: disabled`。
- 不引入嵌入服务，继续走桩模式（`is_embedding_disabled()` 已存在）。
- 不重构 MetaGPT 多 LLM 路由系统。

## 整体架构

```
[LLM 层]   BaseLLM.reasoning_content         ── 已存在，不动
   ↓
[捕获层]   STAction.last_reasoning           ── 新增（每次 _aask 后赋值）
   ↓
[沉淀层]   commit_reasoning_thought()        ── 新增模块
   ↓ 走现有 add_thought
[存储层]   AgentMemory.thought_list          ── 复用
           + sidecar 文件 reasoning/<id>.txt ── 新增
   ↓
[检索层]   new_agent_retrieve                ── 复用（桩模式下取全量）
   ↓
[影响层]   规划类 prompt 增加 "Recent internal thoughts" 段 ── 新增
```

## 关键设计决策

### 1. 选择性捕获（白名单制，默认安全）

只对 **reflect + planning** 这 5 个 action 启用 reasoning 提交：

| Action | 类别 | 文件 |
|---|---|---|
| `AgentInsightAndGuidance` | reflect | `actions/run_reflect_action.py` |
| `AgentPlanThoughtOnConvo` | reflect | `actions/run_reflect_action.py` |
| `AgentMemoryOnConvo` | reflect | `actions/run_reflect_action.py` |
| `GenDailySchedule` | planning | `actions/gen_daily_schedule.py` |
| `GenHourlySchedule` | planning | `actions/gen_hourly_schedule.py` |

机制：`STAction` 增加类属性 `commit_reasoning_as_thought: ClassVar[bool] = False`，被选中的 5 个类显式覆写为 `True`。其它 action 一律不提交。

### 2. 摘要 + sidecar 双轨存储

DeepSeek CoT 一次往往 500–2000 token，verbatim 入 `nodes.json` 会膨胀到不可接受的体积。采用双轨：

- **入库摘要**：`BasicMemory.description` 存压缩后的摘要（≤ 200 字符），走纯字符串截断（路径 A：取首句 + 末句 + 中间省略号），不额外调用 LLM。
- **完整原文**：写到 sidecar `examples/stanford_town/storage/<sim_code>/personas/<name>/reasoning/<memory_id>.txt`，不进 `nodes.json`，便于事后审阅但不污染前端。

### 3. ContextVar 传递 role

`STAction._aask(prompt)` 当前签名不带 role，但 commit hook 需要 role 引用。用 `contextvars.ContextVar` 而不是实例属性：

- 三个 role 在 `asyncio.gather` 里并行跑，实例属性会互相污染。
- ContextVar 有天然的协程隔离。
- 改动面更小，无需修改所有 action 的 `_aask` 调用签名。

每个 action 的 `run(role, ...)` 入口包一层 `async with self.with_role(role):`。

### 4. 显式 prompt 注入

reflect 路径的 `AgentInsightAndGuidance` 输入本来就是检索结果，新增的 inner_monologue thoughts 会自然出现，**无需改 prompt**。

planning 路径需要主动注入：

- `GenDailySchedule` / `GenHourlySchedule` 的 `create_prompt_input` 调用 `role.memory.thought_list` 取最近 N 条 `cause_by` 含 `reasoning_via:` 标记的 thought，渲染成多行字符串。
- 对应 prompt 模板（`daily_planning_v6.txt` / 对应 hourly 模板）增加新占位符 `!<INPUT N>!`，渲染区命名为 `Recent internal thoughts:`，明确与外部观察区分，避免 agent 混淆自我 CoT 和环境观察。

## 实施阶段

### Phase 1：捕获层

**改动**：`metagpt/ext/stanford_town/actions/st_action.py`

- 新增类属性 `last_reasoning: Optional[str] = None`
- 新增类属性 `commit_reasoning_as_thought: ClassVar[bool] = False`
- 新增上下文管理器 `with_role(role)` 基于 `contextvars.ContextVar`
- 修改 `_aask`：调用 `self.llm.aask` 后，从 `self.llm.reasoning_content` 抓取并赋值 `self.last_reasoning`；若 `commit_reasoning_as_thought` 为真且 ContextVar 非空，调用 `commit_reasoning_thought(role, action_name, reasoning)`

**验证**：手动跑一个最小 action（GenDailySchedule），日志里看到 `last_reasoning` 被赋值，`commit_reasoning_thought` 被调用。

### Phase 2：沉淀层

**新文件**：`metagpt/ext/stanford_town/memory/inner_monologue.py`

模块导出：

- `commit_reasoning_thought(role, action_name, reasoning)` —— 顶层入口
  - 调用 `_compress_reasoning(reasoning)` 取摘要
  - 调用 `role.memory.add_thought(...)` 入 thought_list
    - `created = role.scratch.curr_time`
    - `expiration = created + timedelta(days=30)`
    - `subject = role.name`
    - `predicate = "reasoning_via"`
    - `object = action_name`
    - `description = 摘要`
    - `keywords` = 用现有简单方式（按空格分词后取前 5 个非停用词）或留空
    - `poignancy = 3`（默认中等重要性，避免再调一次 LLM 评分）
    - `embedding_pair = (摘要, get_embedding(摘要))` —— 桩模式下返回 `[0.0]`，沿用现有路径
    - `filling = []`
  - 调用 `_persist_full_reasoning(role, memory_id, reasoning)` 写 sidecar
- `_compress_reasoning(text, max_chars=200)` —— 路径 A 截断
  - 提取首句和末句（按 `. ` / `。` 切分）
  - 中间用 `…` 省略
  - 总长截到 `max_chars`
- `_persist_full_reasoning(role, memory_id, full_reasoning)` —— sidecar 写文件
  - 路径：`<memory_dir>/../reasoning/<memory_id>.txt`（与 `bootstrap_memory/` 同级）
  - `mkdir(parents=True, exist_ok=True)` 兼容首次写入
  - UTF-8 写入

**验证**：手动构造一个 role 实例，调用 `commit_reasoning_thought`，检查 `thought_list` 长度 +1、`description` 长度 ≤ 200、sidecar 文件存在。

### Phase 3：白名单标记

**改动**：5 个 action 类各加一行类属性

```python
class GenDailySchedule(STAction):
    name: str = "GenDailySchedule"
    commit_reasoning_as_thought: ClassVar[bool] = True
    ...
```

涉及文件：

- `metagpt/ext/stanford_town/actions/gen_daily_schedule.py`
- `metagpt/ext/stanford_town/actions/gen_hourly_schedule.py`
- `metagpt/ext/stanford_town/actions/run_reflect_action.py`（3 个类）

### Phase 4：role 上下文注入

**改动面**：5 个白名单 action 类的 `run()` 入口

```python
async def run(self, role: "STRole", ...):
    async with self.with_role(role):
        # 原有逻辑
        ...
```

或者更省事的方式：在 STAction 提供一个装饰器 `@with_role_from_first_arg`，自动把第一个 role 参数注册到 ContextVar。装饰器版本只需 5 个类各加一行 `@with_role_from_first_arg`，但需要严格约定第一个参数是 role。两种实现都可，倾向上下文管理器（更显式、更易调试）。

### Phase 5：消费层 — prompt 注入

**改动**：

1. `actions/gen_daily_schedule.py::run.create_prompt_input`
   - 新增本地辅助 `recent_inner_thoughts(role, n=5)`：从 `role.memory.thought_list` 取 `predicate == "reasoning_via"` 的最近 N 条，渲染为：
     ```
     - [GenDailySchedule] I'll wake at 7am to prep…
     - [AgentInsightAndGuidance] Hosting a party means…
     ```
   - 加入 `prompt_input` 列表

2. `prompts/daily_planning_v6.txt`
   - 在合适位置（"Persona's lifestyle" 之后、"Daily plan requirement" 之前）插入：
     ```
     Recent internal thoughts (your own prior reasoning, NOT external events):
     !<INPUT N>!
     ```
   - N 是新占位符索引

3. 相同处理应用到 `gen_hourly_schedule.py` + 其使用的 `prompts/*.txt`（预计是 `daily_planning_v6.txt` 之外的 hourly 模板，提交前确认具体文件名）

4. **空状态保护**：当 `recent_inner_thoughts` 返回空（首次启动尚无历史），渲染为 `(no prior internal thoughts yet)`，避免 prompt 留空污染。

### Phase 6：配置开启思考模式

**改动**：`~/.metagpt/config2.yaml`

```yaml
llm:
  api_type: "openai"
  base_url: "https://api.deepseek.com"
  api_key: "..."
  model: "deepseek-v4-flash"
  extra_body:
    thinking:
      type: "enabled"   # 改回 enabled
  reasoning_max_token: 2000  # 配合 _cons_kwargs 给思考留预算
```

**配套框架改动**：`metagpt/provider/openai_api.py::_cons_kwargs`

- 当 `extra_body.thinking.type == "enabled"` 时，自动把 `kwargs["max_tokens"] += self.config.reasoning_max_token`
- 这样 Stanford Town 那些 `max_tokens=500` 的大调用（GenDailySchedule）会得到 `500 + 2000 = 2500` 的总预算，思考够用、答案也有预算
- 那些 `_run_gpt35_max_tokens(max_tokens=5/15/30)` 的小调用，由于不在白名单内、且我们后续会让它们独立设置 `extra_body.thinking.type=disabled`（per-call override，见下面备注），不受影响

**备注（per-call thinking toggle）**：本计划暂不引入 per-call extras 通道。`_run_gpt35_max_tokens` 内部小调用沿用全局 `extra_body` 配置。如果开了全局 thinking，这些小调用的 token 预算会被自动放大（因为 `_cons_kwargs` 加 reasoning_max_token），不至于失败但会增加成本。如果 Phase 7 验证时这部分成本不可接受，再单独立项做 per-call override。

## 端到端验证

1. **环境状态**：删掉 `examples/stanford_town/storage/test_sim/`，确保从干净状态起步。
2. **跑 20 round**：
   ```powershell
   python examples\stanford_town\run_st_game.py "Host a open lunch party at 13:00 pm" "base_the_ville_isabella_maria_klaus" "test_sim" --investment 10 --n_round 20
   ```
3. **检查项**：
   - `examples/stanford_town/storage/test_sim/personas/<name>/bootstrap_memory/nodes.json` 中至少存在若干 `predicate: "reasoning_via"` 的 thought 节点
   - `examples/stanford_town/storage/test_sim/personas/<name>/reasoning/*.txt` 存在对应数量的 sidecar
   - 第二天的 `GenDailySchedule` 日志输出的 prompt 中包含 `Recent internal thoughts:` 段且非空
   - 对话或反思中能观察到 agent 引用先前 reasoning 中的关键词（人工抽样判断）
4. **成本量化**：对比思考模式开/关的 `cost_manager` 输出，记录 token 总量倍数。预期 5–8x。
5. **回滚开关**：把 `~/.metagpt/config2.yaml` 改回 `extra_body.thinking.type: "disabled"` 即关停整个机制；新加的 5 个白名单 action 类属性在思考关闭时不会触发 commit（因为 `last_reasoning` 为空）。

## 改动清单

| 文件 | 改动 | 估计行数 |
|---|---|---|
| `metagpt/ext/stanford_town/actions/st_action.py` | 加 `last_reasoning` / `commit_reasoning_as_thought` / `with_role` ContextVar / `_aask` hook | ~40 行 |
| **新文件** `metagpt/ext/stanford_town/memory/inner_monologue.py` | `commit_reasoning_thought` + `_compress_reasoning` + `_persist_full_reasoning` | ~80 行 |
| `metagpt/ext/stanford_town/actions/gen_daily_schedule.py` | 类属性 + run 包 with_role + prompt_input 加 recent_inner_thoughts | ~15 行 |
| `metagpt/ext/stanford_town/actions/gen_hourly_schedule.py` | 同上 | ~15 行 |
| `metagpt/ext/stanford_town/actions/run_reflect_action.py` | 3 个类各加属性 + run 包 with_role | ~15 行 |
| `metagpt/ext/stanford_town/prompts/daily_planning_v6.txt` | 加 `Recent internal thoughts:` 段 | ~3 行 |
| `metagpt/ext/stanford_town/prompts/<hourly 模板>` | 同上 | ~3 行 |
| `metagpt/provider/openai_api.py` | thinking enabled 时 max_tokens 自动加 reasoning_max_token | ~5 行 |
| `~/.metagpt/config2.yaml` | 启用 thinking + 设 reasoning_max_token | 2 行 |

总计 < 180 行，框架级 < 10 行。

## 风险与缓解

| 风险 | 缓解措施 |
|---|---|
| **token 成本爆炸** | 白名单只 5 个 action；Phase 7 量化；如超 10x 把白名单收窄到只剩 2 个反思 action |
| **CoT 摘要丢信息** | sidecar 保留全文供事后审阅；后续如需改进可在 inner_monologue 模块切换到 LLM summarize（路径 B），无需改其他代码 |
| **prompt 污染**（agent 把 CoT 误当外部观察） | 注入段加显式标题 `Recent internal thoughts (your own prior reasoning, NOT external events):` |
| **ContextVar 在 asyncio.gather 跨边界丢失** | Python 标准库的 ContextVar 在 `asyncio.create_task` / `gather` 中**自动复制**当前上下文，每个 task 独立。这是标准行为，不需要额外处理；但提交前用日志验证一次三个 role 的 ContextVar 互不污染 |
| **sidecar 目录膨胀** | 单次 reasoning 文件几 KB，500 round × 5 action × 3 role ≈ 7500 文件、< 50MB，可接受；可后续加压缩归档 |
| **AGENTS.md 合规** | 全程 async；不引入新依赖；保持 py3.9 兼容（ContextVar 是标准库）；用 `logger` 不用 `print`；新代码遵循 pydantic v2；prompt 模板修改保持 `!<INPUT N>!` 风格 |

## 提交顺序建议

1. Phase 1 + Phase 2（捕获层 + 沉淀层），不接入任何 action，先跑通"机制存在但未启用"
2. Phase 3 + Phase 4，接入 5 个 action，但 Phase 6 的 thinking 还没开 → 此时不会有任何 reasoning_content，仍然零行为变化（安全）
3. Phase 5 prompt 注入（同样在 thinking 关闭下零影响）
4. Phase 6 + 端到端验证 —— 此时才真正启用思考模式，所有前置改动开始产生效果

每个 Phase 单独提交一次，每次提交都保证仓库可运行（前 3 个 Phase 是 no-op 改动）。这样如果 Phase 6 验证不通过，可单独回滚思考开关而不影响代码改动。
