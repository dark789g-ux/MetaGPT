# Stanford Town · LLM Logs Viewer 设计

**日期**: 2026-05-12
**作者**: Ren / Claude
**状态**: Draft → 待用户评审

## 背景

Stanford Town 模拟过程中每个 step、每个 persona 会触发数十次 LLM 调用（perceive / retrieve / plan / reflect / converse 等）。目前这些 prompt 与 response 只存在于 LLM provider 内部日志，无法在回放界面观察。需要让用户在前端能看到每一次 LLM 的输入与输出，用于调试 prompt、检查模型行为、比对回放轨迹。

## 目标

- 实时查看正在运行的 sim 的 LLM 调用流。
- 回放历史 sim 的全部 LLM 调用。
- 不打扰现有回放页（独立 Tab）。
- 不引入新依赖（不上 channels / SSE）。

## 非目标

- prompt 模板还原、diff 对比、导出 CSV。
- 敏感字段脱敏（本地工具）。
- 后端分页 / 全文索引。
- 修改非 stanford_town 范围的 LLM 调用链路。

## 总体架构

```
┌─ run_st_game 子进程 ──────────────────┐         ┌─ Django 前端 ─────────┐
│ STAction._aask                        │         │ /llm_logs/<sim>/      │
│ STAction._run_gpt35_max_tokens        │         │   独立页面            │
│   ↓ 包一层 logger                     │  poll   │   每 1.5s 拉增量      │
│ append 一行 JSON                      │ ◀────── │   卡片流（默认折叠）  │
│   ↓                                   │         └───────────────────────┘
│ storage/<sim_code>/llm_logs.jsonl    │
└───────────────────────────────────────┘
```

唯一埋点：`STAction._aask` 与 `_run_gpt35_max_tokens`（[metagpt/ext/stanford_town/actions/st_action.py:69-80](metagpt/ext/stanford_town/actions/st_action.py#L69-L80)）。

实时 / 回放共用一份 JSONL，区别只是"文件是否还在增长"。

## 数据格式

`storage/<sim_code>/llm_logs.jsonl`，每行一条：

```json
{
  "seq": 1287,
  "ts": "2026-05-12T14:32:08.412+08:00",
  "step": 142,
  "persona": "Isabella Rodriguez",
  "action": "GenDailySchedule",
  "model": "deepseek-chat",
  "params": {"temperature": 0.7, "max_tokens": 1500},
  "prompt": "...",
  "response": "...",
  "usage": {"prompt_tokens": 812, "completion_tokens": 134, "total_tokens": 946},
  "cost_usd": 0.00021,
  "latency_ms": 2843,
  "retry_idx": 0,
  "used_fail_default": false,
  "error": null
}
```

字段说明：

- `seq`：进程内单调计数器，从 0 开始，用于稳定排序与去重。
- `ts`：ISO 8601 带时区。
- `step / persona / action`：通过 `contextvars` 注入，详见下文。
- `params`：实际生效的 temperature / max_tokens（注意 `_run_gpt35_max_tokens` 会临时改 max_tokens，需记录改完之后的值）。
- `usage / cost_usd`：从 MetaGPT 已有 `CostManager` 取；provider 未接入则为 `null`。
- `retry_idx`：`_run_gpt35_max_tokens` 内 retry 循环的当前索引；普通 `_aask` 为 0。
- `used_fail_default`：是否最终落到 `_func_fail_default_resp`。普通 `_aask` 路径恒为 `false`。
- `error`：异常字符串；正常完成为 `null`。

## 后端实现

### 新增 `metagpt/ext/stanford_town/utils/llm_logger.py`

公开接口：

```python
def set_sim_code(sim_code: str) -> None: ...
def set_step(step: int) -> None: ...
def set_persona(persona: str | None) -> None: ...
def set_action(action_cls_name: str | None) -> None: ...

def log_call(
    *,
    prompt: str,
    response: str | None,
    model: str | None,
    params: dict,
    usage: dict | None,
    cost_usd: float | None,
    latency_ms: int,
    retry_idx: int,
    used_fail_default: bool,
    error: str | None,
) -> None: ...
```

实现要点：

- 三个上下文用 `contextvars.ContextVar`，跨 `await` 安全。
- `sim_code` 决定写盘路径：`<storage_path>/<sim_code>/llm_logs.jsonl`。`storage_path` 复用现有 `metagpt/ext/stanford_town/utils/const.py` 中的常量。
- `seq` 用模块级 `itertools.count()`。
- 写盘：单次 `open(path, "a", encoding="utf-8")` + `json.dumps(ensure_ascii=False)` + `write(line + "\n")` + `flush()`。同步写，stanford_town 节奏慢，不会成为瓶颈。
- 父目录可能在首次 set_sim_code 时尚不存在，需 `mkdir(parents=True, exist_ok=True)`。

### 改动点

1. **`STAction._aask`**（[st_action.py:69](metagpt/ext/stanford_town/actions/st_action.py#L69)）
   包一层：`t0 = time.time()`；try/except 调用 `self.llm.aask`；finally 调 `log_call(... retry_idx=0, used_fail_default=False ...)`。`model` 从 `self.config.llm.model` 取，`params` 从 `self.config.llm.temperature/max_token` 取。

2. **`STAction._run_gpt35_max_tokens`**（[st_action.py:72](metagpt/ext/stanford_town/actions/st_action.py#L72)）
   在 retry 循环里每次都 `log_call`，`retry_idx=idx`。最终走到 `_func_fail_default_resp` 时再补一条 `used_fail_default=True` 的记录（`prompt` 为空，`response` 为 fail default）。

3. **`STAction._aask` 入口** set 当前 `action`（用 `self.cls_name`）。这条放进 `_aask` / `_run_gpt35_max_tokens` 自身即可，不需要改各 action 子类。

4. **reverie 主循环**：
   - 启动时 `set_sim_code(self.sim_code)`。
   - 每个 step 开头 `set_step(self.step)`。
   - 每个 persona 进入认知阶段时 `set_persona(persona.name)`，离开时 `set_persona(None)`。
   具体落点在 `metagpt/ext/stanford_town/reverie.py`（搜 `for persona_name in self.personas` 与 step 推进处）。

### 故意不做

- 不做日志切片：一个 sim 一个文件。
- 不做异步队列写盘：直接同步 append。
- 不做敏感字段脱敏：本地工具。

## 前端实现

### 路由

新增（`examples/stanford_town/frontend/translator/views.py` + `frontend_server/urls.py`）：

| URL | View | 模板 |
|---|---|---|
| `GET /llm_logs/<sim_code>/` | `llm_logs_page` | `templates/llm_logs/llm_logs.html` |
| `GET /llm_logs/<sim_code>/tail?offset=<bytes>&limit=<n>` | `llm_logs_tail` | (JSON) |

### `llm_logs_tail` 行为

- 打开 `storage/<sim_code>/llm_logs.jsonl`，`seek(offset)`，按行读取直到 EOF。
- 每行 `json.loads`，组成 `entries: list`。
- 返回：
  ```json
  {
    "next_offset": 123456,
    "eof": true,
    "is_live": false,
    "entries": [ ... ]
  }
  ```
- `is_live` 判定：读取 `examples/stanford_town/temp_storage/curr_sim_code.json`，若其中 `sim_code` 等于本次请求的 sim_code 且 jsonl 文件 mtime 在 30 秒内，则为 `true`。
- `limit`：可选；当 `offset == -1` 时表示"从尾部反向取 limit 条"，用于首次加载（默认 200）。
- 文件不存在：返回 `entries:[], next_offset:0, eof:true, is_live:false`，不报错。

### 页面布局

复用 `base.html` + Bootstrap，原生 JS 实现，单文件 `llm_logs.html`：

```
┌─────────────────────────────────────────────────────────────────┐
│  Stanford Town · LLM Logs · sim_code=xxx          [🟢 LIVE]     │
├─────────────────────────────────────────────────────────────────┤
│  Filters:                                                       │
│   Step [____] – [____]  Persona [▼ All]  Action [▼ All]        │
│   ☐ Only failed/retried   Search prompt: [___________]  [Clear] │
│   [Pause autoscroll] [Jump to bottom] [Load earlier]            │
├──────────┬──────────────────────────────────────────────────────┤
│ #1287    │ ▸ GenDailySchedule · Isabella · step 142  · 2843ms  │
│          │   model=deepseek-chat  T=0.7  tokens 812/134  $0.00 │
│ ─────────│                                                      │
│ #1288    │ ▼ DecideToTalk · Klaus · step 142 · 612ms           │
│          │   ┌─ PROMPT ─────────────────────────┐ [copy]       │
│          │   │ <full prompt, mono, scrollable>  │              │
│          │   └──────────────────────────────────┘              │
│          │   ┌─ RESPONSE ───────────────────────┐ [copy]       │
│          │   │ <full response>                  │              │
│          │   └──────────────────────────────────┘              │
│          │   usage: 412/28  ·  latency: 612ms  ·  retry 0      │
└──────────┴──────────────────────────────────────────────────────┘
```

### 交互

- **默认折叠**：每条只显示一行摘要（`action · persona · step · latency` + `model · params · tokens · cost`）。点击展开 prompt/response。
- **过滤即时生效**：纯前端 filter，不重新请求；条件变化只重渲染列表。Search 用 `String.includes` 做 substring 匹配。
- **LIVE 指示**：`is_live === true` 时绿点 + 1.5s 轮询；`false` 时灰点 + 停止轮询。
- **Step 链接**：摘要里的 `step 142` 是超链接，新 tab 打开 `/replay/<sim_code>/142/`。
- **Pause autoscroll / Jump to bottom**：长日志必备。
- **首次加载**：调 `tail?offset=-1&limit=200`，渲染最近 200 条。点 "Load earlier" 触发 `tail?offset=<更早的 offset>` 往前加载。
- **入口**：在 [home.html:5-7](examples/stanford_town/frontend/templates/home/home.html#L5-L7) 标题区加一个小链接 `📋 LLM Logs`，`target="_blank"` 打开 `/llm_logs/<sim_code>/`。

### 故意不做

- 无 SPA 框架；无后端分页；无全文索引；无 prompt diff；无导出。

## 测试

- **后端单元测试**（pytest）：
  - `test_llm_logger_writes_jsonl`：set 上下文 + log_call 后，目标文件多一行且字段齐全。
  - `test_llm_logger_handles_missing_dir`：sim_code 目录不存在时自动创建。
  - `test_llm_logger_seq_monotonic`：连续 log_call 的 seq 递增。
  - `test_st_action_aask_logs_on_success_and_error`：mock LLM provider，验证 `_aask` 成功 / 抛错都各产生一条记录。
- **后端集成测试**：跑一个最小 sim（1 persona × 2 step），结束后断言 jsonl 文件非空且每条都能 `json.loads`。
- **前端**：人工冒烟。
  - 跑一个实时 sim，打开 `/llm_logs/<sim>/`，看到绿点 + 条目持续追加。
  - sim 结束后刷新，看到灰点，所有条目仍可见，过滤生效。
  - 点摘要里 step 链接，正确跳到对应 `/replay/<sim>/<step>/`。

## 风险与开放问题

- **`contextvars` 跨进程**：reverie 是同进程 asyncio，`contextvars` 够用。如果未来 reverie 改用多进程并行 persona，需要切换为显式参数传递。
- **`cost_usd` 字段**：依赖 LLM provider 是否接 `CostManager`。DeepSeek 当前接入情况待确认；未接入时该字段为 `null`，前端不展示这一列即可。
- **JSONL 体积**：单个 sim 长跑可能到几百 MB；前端首次只拉 200 条，后续按需加载，浏览器端不会一次性持有全量。
- **写盘原子性**：单进程同步 append + `flush()`，前端按 byte offset 增量读，最坏情况是读到半行；前端 `JSON.parse` 失败时跳过该行、下次轮询用上次成功 offset 重读即可。

## 落地范围

- 新增文件：
  - `metagpt/ext/stanford_town/utils/llm_logger.py`
  - `examples/stanford_town/frontend/templates/llm_logs/llm_logs.html`
  - `tests/ext/stanford_town/utils/test_llm_logger.py`
- 修改文件：
  - `metagpt/ext/stanford_town/actions/st_action.py`（包 _aask / _run_gpt35_max_tokens）
  - `metagpt/ext/stanford_town/reverie.py`（注入 sim_code / step / persona 上下文）
  - `examples/stanford_town/frontend/translator/views.py`（两个新 view）
  - `examples/stanford_town/frontend/frontend_server/urls.py`（两条新 url）
  - `examples/stanford_town/frontend/templates/home/home.html`（标题加入口链接）
  - `qa/replay_ui_code_map.md`（新页面登记）
