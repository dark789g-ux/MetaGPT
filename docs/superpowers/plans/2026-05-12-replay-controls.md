# 回放界面控制增强 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 stanford_town 回放页面增加中文标题、手动"下一步"按钮、运行时速度切换（0.5×/1×/2×/4×），并把后端 URL 默认速度从 1× 调到 0.5×。

**Architecture:** 纯前端模板 + JS 改动 + 一行后端默认值变更。新增 JS 状态仅是两个变量 (`pending_movement_speed`、`manual_step_pending`)，在 Phaser `update()` 循环的 step 边界 (`execute_count == 0`) 上应用，避免中途切换造成 sprite 位置错位。

**Tech Stack:** Django templates、Phaser 3.55、Bootstrap 3（glyphicon）、jQuery（页面已加载）

**Spec:** `docs/superpowers/specs/2026-05-12-replay-controls-design.md`

**Note on testing:** 该模块无 JS / 模板测试基础设施 (`translator/tests.py` 为空模板)，本计划采用**结构化手动验收**而非自动化测试。每个改动任务后立即在浏览器验证。

---

## File Structure

- **Modify:** `examples/stanford_town/frontend/translator/views.py` — 第 129 行，URL `play_speed` 默认值 `"2"` → `"1"`
- **Modify:** `examples/stanford_town/frontend/templates/demo/demo.html` — 顶部加 `<h1>` 标题；控制区加速度按钮组 + 下一步按钮
- **Modify:** `examples/stanford_town/frontend/templates/demo/main_script.html` — `update()` 末尾加 step 边界逻辑；脚本末尾绑定按钮事件

---

## Task 1：后端默认速度下调

**Files:**
- Modify: `examples/stanford_town/frontend/translator/views.py:129`

- [ ] **Step 1：修改函数签名默认值**

把 `views.py:129`：

```python
def demo(request, sim_code, step, play_speed="2"):
```

改为：

```python
def demo(request, sim_code, step, play_speed="1"):
```

不修改 `play_speed_opt` 映射，不修改 `views.py:205` 中显式传 `play_speed="3"` 的快捷入口。

- [ ] **Step 2：本地启动 Django，验证默认值生效**

```powershell
cd examples/stanford_town/frontend
python manage.py runserver
```

浏览器打开 `http://127.0.0.1:8000/demo/<已有 sim_code>/<step>/`（不带 play_speed 参数），打开 DevTools 在 Sources 里找到内联脚本，确认 `let movement_speed = 1;`（Step 4 完成后此值会同时被速度按钮按 1× active 反映；本步骤仅验证后端注入值）。

- [ ] **Step 3：提交**

```bash
git add examples/stanford_town/frontend/translator/views.py
git commit -m "feat(stanford_town): lower default replay speed to 0.5x"
```

---

## Task 2：加页面标题

**Files:**
- Modify: `examples/stanford_town/frontend/templates/demo/demo.html`

- [ ] **Step 1：在 `{% block content %}` 顶部插入 `<h1>`**

定位 `demo.html` 第 4-5 行：

```django
{% block content %}
<br>
<br>
```

改为：

```django
{% block content %}
<h1 style="text-align:center; margin-top:1em; margin-bottom:0.2em; font-weight:600">
  生成式智能体 · 模拟回放
</h1>
<br>
<br>
```

- [ ] **Step 2：浏览器验证**

刷新 demo 页面，确认：
- 页面顶部居中显示"生成式智能体 · 模拟回放"
- 字号显著大于下方 `<h3>` 副标题
- 下方原斜体 `This is a pre-computed replay…` 仍然完整显示

- [ ] **Step 3：提交**

```bash
git add examples/stanford_town/frontend/templates/demo/demo.html
git commit -m "feat(stanford_town): add Chinese page title to replay demo"
```

---

## Task 3：添加速度按钮组与"下一步"按钮的 HTML

**Files:**
- Modify: `examples/stanford_town/frontend/templates/demo/demo.html:20-30`

- [ ] **Step 1：替换控制区 HTML**

定位 `demo.html` 第 20-30 行的 `<div class="col-md-4">` 整块：

```django
<div class="col-md-4">
    <h2 style="text-align: right; {% if mode == 'simulate' %} display: none {% endif %}">
        <button id="play_button" type="button" class="btn btn-default">
        <strong style=" font-size:1.2em"><i class="glyphicon glyphicon-play"></i> &nbsp;Play</strong>
      </button>

      <button id="pause_button" type="button" class="btn btn-default">
        <strong style=" font-size:1.2em"><i class="glyphicon glyphicon-pause"></i> &nbsp;Pause</strong>
      </button>
    </h2>
</div>
```

替换为：

```django
<div class="col-md-4">
    <h2 style="text-align: right; {% if mode == 'simulate' %} display: none {% endif %}">
        <div class="btn-group" role="group" style="margin-right:0.5em">
            <button type="button" class="btn btn-default btn-sm speed-btn {% if play_speed == 1 %}active{% endif %}" data-speed="1">0.5×</button>
            <button type="button" class="btn btn-default btn-sm speed-btn {% if play_speed == 2 %}active{% endif %}" data-speed="2">1×</button>
            <button type="button" class="btn btn-default btn-sm speed-btn {% if play_speed == 4 %}active{% endif %}" data-speed="4">2×</button>
            <button type="button" class="btn btn-default btn-sm speed-btn {% if play_speed == 8 %}active{% endif %}" data-speed="8">4×</button>
        </div>
        <button id="play_button" type="button" class="btn btn-default">
            <strong style=" font-size:1.2em"><i class="glyphicon glyphicon-play"></i> &nbsp;Play</strong>
        </button>
        <button id="pause_button" type="button" class="btn btn-default">
            <strong style=" font-size:1.2em"><i class="glyphicon glyphicon-pause"></i> &nbsp;Pause</strong>
        </button>
        <button id="step_button" type="button" class="btn btn-default">
            <strong style=" font-size:1.2em"><i class="glyphicon glyphicon-step-forward"></i> &nbsp;下一步</strong>
        </button>
    </h2>
</div>
```

注意：`{% if play_speed == N %}` 中的数字与模板上下文中的 `play_speed`（已经在 views.py 中转成 int）匹配，合法值 1/2/4/8。

- [ ] **Step 2：浏览器验证（控件渲染，按钮尚未生效）**

刷新页面，确认：
- Current Time 那一行右侧顺序为：`[0.5×][1×][2×][4×]  [Play] [Pause] [下一步]`
- 默认 URL 下 `0.5×` 按钮高亮（class `active`）
- 在 URL 末尾加 `/4/`（views.py 的 sim_code/step/play_speed=4 → movement_speed=8）刷新，确认 `4×` 高亮
- 这一步速度按钮点击**还没有响应**（Task 4 才接入），但下一步/Play/Pause 不应报 JS 错

- [ ] **Step 3：提交**

```bash
git add examples/stanford_town/frontend/templates/demo/demo.html
git commit -m "feat(stanford_town): add speed switcher and step button UI"
```

---

## Task 4：实现速度切换与下一步的 JS 行为

**Files:**
- Modify: `examples/stanford_town/frontend/templates/demo/main_script.html`

- [ ] **Step 1：在 PREAMBLE 段加入两个新状态变量**

定位 `main_script.html` 第 87 行：

```js
let movement_speed = {{play_speed}};
```

在其后立即追加：

```js
let pending_movement_speed = null;
let manual_step_pending = false;
```

- [ ] **Step 2：在 `update()` 的 step 推进分支应用 pending 状态**

定位 `main_script.html` 第 477-489 行的 `if (execute_count == 0) { … }` 块：

```js
  if (execute_count == 0) {
      for (let i=0; i<Object.keys(personas).length; i++) {
      let curr_persona_name = Object.keys(personas)[i]
      let curr_persona = personas[curr_persona_name];
      curr_persona.body.x = movement_target[curr_persona_name][0];
      curr_persona.body.y = movement_target[curr_persona_name][1];
    }
        execute_count = execute_count_max + 1;
      step = step + 1;

      start_datetime = new Date(start_datetime.getTime() + step_size);
        document.getElementById("game-time-content").innerHTML = start_datetime.toLocaleTimeString("en-US", datetime_options);
    }
```

在 `step = step + 1;` 之后、`start_datetime = ...` 之前插入：

```js
        if (pending_movement_speed !== null) {
            movement_speed = pending_movement_speed;
            execute_count_max = tile_width / movement_speed;
            pending_movement_speed = null;
        }
        if (manual_step_pending) {
            play_context.scene.pause();
            manual_step_pending = false;
        }
```

注意：`execute_count = execute_count_max + 1;` 在上面的旧代码中已写死按"当前" `execute_count_max` 计算。我们在 step 推进时切换速度后，需要让下一 tile 的帧数用新值。因此把这块改为如下顺序（先切换速度再算 reset）：

最终该分支替换为：

```js
  if (execute_count == 0) {
      for (let i=0; i<Object.keys(personas).length; i++) {
        let curr_persona_name = Object.keys(personas)[i]
        let curr_persona = personas[curr_persona_name];
        curr_persona.body.x = movement_target[curr_persona_name][0];
        curr_persona.body.y = movement_target[curr_persona_name][1];
      }
      step = step + 1;

      if (pending_movement_speed !== null) {
          movement_speed = pending_movement_speed;
          execute_count_max = tile_width / movement_speed;
          pending_movement_speed = null;
      }
      execute_count = execute_count_max + 1;

      start_datetime = new Date(start_datetime.getTime() + step_size);
      document.getElementById("game-time-content").innerHTML = start_datetime.toLocaleTimeString("en-US", datetime_options);

      if (manual_step_pending) {
          play_context.scene.pause();
          manual_step_pending = false;
      }
  }
```

- [ ] **Step 3：把 `play_context` 提升到外层作用域以便按钮回调访问**

定位 `main_script.html` 第 334-348 行：

```js
function update(time, delta) {
    // *** SETUP PLAY AND PAUSE BUTTON ***
    let play_context = this;
    function game_resume() {
        play_context.scene.resume();
    }
    play_button.onclick = function(){
        game_resume();
    };
    function game_pause() {
        play_context.scene.pause();
    }
    pause_button.onclick = function(){
        game_pause();
    };
```

把 `let play_context = this;` 改为 `play_context = this;`（赋值给外层变量），并在 `update()` 函数定义**之前**（例如紧跟第 87 行的 `manual_step_pending` 声明后）增加：

```js
let play_context = null;
```

最终 update() 顶部变为：

```js
function update(time, delta) {
    // *** SETUP PLAY AND PAUSE BUTTON ***
    play_context = this;
    function game_resume() {
        play_context.scene.resume();
    }
    play_button.onclick = function(){
        game_resume();
    };
    function game_pause() {
        play_context.scene.pause();
    }
    pause_button.onclick = function(){
        game_pause();
    };
```

- [ ] **Step 4：在脚本末尾绑定速度按钮和下一步按钮**

定位 `main_script.html` 第 494-497 行：

```js
    // Control button binders
    var play_button=document.getElementById("play_button");
    var pause_button=document.getElementById("pause_button");
</script>
```

替换为：

```js
    // Control button binders
    var play_button=document.getElementById("play_button");
    var pause_button=document.getElementById("pause_button");
    var step_button=document.getElementById("step_button");

    document.querySelectorAll('.speed-btn').forEach(function (btn) {
        btn.onclick = function () {
            pending_movement_speed = parseInt(this.dataset.speed, 10);
            document.querySelectorAll('.speed-btn').forEach(function (b) {
                b.classList.remove('active');
            });
            this.classList.add('active');
        };
    });

    step_button.onclick = function () {
        if (play_context) {
            play_context.scene.resume();
        }
        manual_step_pending = true;
    };
</script>
```

- [ ] **Step 5：浏览器手动验收（按 spec §测试计划）**

刷新 demo 页面，DevTools Console 应无错误，依次验证：

| # | 操作 | 预期 |
|---|---|---|
| 1 | 打开页面（默认 URL） | `0.5×` 高亮；sprite 移动明显慢 |
| 2 | 点 `1×` | 当前 step 走完后，sprite 提速；`1×` 高亮 |
| 3 | 点 `2×` 然后 `4×` | 每次都在下一个 step 边界生效；sprite 位置无错位/跳变 |
| 4 | 自动播放中点"下一步" | 当前 step 走完后自动暂停 |
| 5 | 暂停状态下点"下一步" | 前进恰好 1 个 step 后再次自动暂停 |
| 6 | 手动步进后点 Play | 正常恢复自动播放 |
| 7 | 连点 5 次"下一步" | 只推进 1 个 step（非累积）|
| 8 | step 推进时观察右上时间 | 每推进一次时间 +`sec_per_step` 秒 |

每条预期不符 → 不要继续，回到对应步骤排查。

- [ ] **Step 6：提交**

```bash
git add examples/stanford_town/frontend/templates/demo/main_script.html
git commit -m "feat(stanford_town): wire speed switcher and manual step button"
```

---

## Task 5：完整端到端回归

- [ ] **Step 1：覆盖 spec §测试计划 7 项**

参考 spec 第 "测试计划" 一节，把 7 条手动验收全部跑一遍：

1. 标题显示
2. 默认速度 = 0.5×
3. 速度切换无错位
4. 下一步（自动播放中）
5. 下一步（暂停中）
6. 下一步与 Play 交互
7. 时间标签随 step 推进

- [ ] **Step 2：检查与 simulate 模式的兼容**

`demo.html:21` 的控制区有 `{% if mode == 'simulate' %} display: none {% endif %}`。我们的新按钮都嵌在同一个 `<h2>` 里，会被一同隐藏 → 行为正确，无需额外改动。在 simulate 模式入口刷新一次，确认按钮组与原 Play/Pause 一起隐藏（如手头无 simulate 入口可跳过，但记录到 PR 描述）。

- [ ] **Step 3：若上述均通过，无需额外提交（前面 Task 已分别提交）**

---

## Self-Review 结果

- ✅ Spec §1 标题 → Task 2
- ✅ Spec §2 控制区改造 → Task 3
- ✅ Spec §3.1 速度切换 → Task 4 Step 1, 2, 4
- ✅ Spec §3.2 下一步按钮 → Task 4 Step 1, 2, 3, 4
- ✅ Spec §4 后端默认值 → Task 1
- ✅ Spec §测试计划 7 项 → Task 4 Step 5 + Task 5 Step 1
- ✅ 变量命名一致：`pending_movement_speed` / `manual_step_pending` / `play_context` 全文统一
- ✅ 无 TBD / TODO / 占位
