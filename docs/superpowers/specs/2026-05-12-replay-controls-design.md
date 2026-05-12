# 回放界面控制增强 — 设计文档

日期：2026-05-12
范围：`examples/stanford_town/frontend/templates/demo/demo.html`、`examples/stanford_town/frontend/templates/demo/main_script.html`、`examples/stanford_town/frontend/translator/views.py`

## 背景

斯坦福小镇 (`stanford_town`) 的回放页面 (`demo.html` + `main_script.html`) 当前只提供 Play / Pause 两个控制按钮，自动回放速度由 URL 参数 `play_speed` 决定，缺少：

1. 用户手动逐步推进回放的能力
2. 运行时切换速度的能力（且默认速度偏快）
3. 页面级标题

## 目标

- 支持用户手动按"下一步"前进一个 step
- 提供 0.5× / 1× / 2× / 4× 速度切换控件，默认进入 0.5× 档
- 在页面顶部增加中文标题

## 非目标

- 不修改 `sec_per_step`（时间标签步长不变）
- 不持久化用户的速度选择（刷新回到 URL 决定的默认）
- 不引入键盘快捷键
- 不修改后端模拟逻辑或回放数据格式

## 现状要点

- `let movement_speed = {{play_speed}}` (像素/帧)，合法值 1/2/4/8/16/32（需被 `tile_width=32` 整除）
- `execute_count_max = tile_width / movement_speed`：走完一格 tile 所需的帧数
- 当 `execute_count == 0` 时 step += 1 并刷新时间标签
- `play_button` / `pause_button` 通过 `scene.pause()` / `scene.resume()` 控制 Phaser 场景
- 后端 `views.py:demo` 的 URL `play_speed` 默认值为 `"2"`，对应 `play_speed_opt` 映射 `{"1":1, "2":2, "3":4, "4":8}`

## 设计

### 1. 页面标题

在 `demo.html` 的 `{% block content %}` 最顶部（现有 `<br><br>` 之前）插入：

```html
<h1 style="text-align:center; margin-top:1em; margin-bottom:0.2em; font-weight:600">
  生成式智能体 · 模拟回放
</h1>
```

原有 `<h3><em>This is a pre-computed replay…</em></h3>` 保留作为副标题，自然下移。

### 2. 控制区改造

在 `demo.html` 现有 `col-md-4` 内（Play / Pause 按钮所在），调整为：

```
[ 0.5× ][ 1× ][ 2× ][ 4× ]    [▶ Play] [⏸ Pause] [⏭ 下一步]
```

- 速度按钮组：使用 Bootstrap `btn-group`，每个按钮带 `data-speed` 属性，值分别为 `1` / `2` / `4` / `8`（对应 movement_speed）；当前档位添加 `active` 类
- "下一步"按钮：`id="step_button"`，文案 `<i class="glyphicon glyphicon-step-forward"></i> 下一步`
- 初始 active 速度档由 `{{play_speed}}` 决定，模板侧用 `{% if play_speed == 1 %}active{% endif %}` 等条件渲染

### 3. JS 行为（`main_script.html`）

在 `update()` 之外、脚本末尾按钮绑定区域追加逻辑。

#### 3.1 速度切换

```js
let pending_movement_speed = null;

document.querySelectorAll('.speed-btn').forEach(btn => {
  btn.onclick = function () {
    pending_movement_speed = parseInt(this.dataset.speed, 10);
    document.querySelectorAll('.speed-btn').forEach(b => b.classList.remove('active'));
    this.classList.add('active');
  };
});
```

在 `update()` 的 `execute_count == 0` 分支末尾（step 推进完成后）应用：

```js
if (pending_movement_speed !== null) {
  movement_speed = pending_movement_speed;
  execute_count_max = tile_width / movement_speed;
  pending_movement_speed = null;
}
```

**为什么在 step 边界生效**：中途切换会让已部分移动的 sprite 与剩余帧数不匹配，导致 sprite 越过或未达 target，出现位置错位。延迟到 step 边界，用户最多等一个 step (≤ 当前 execute_count_max 帧) 看到生效，无视觉伪影。

#### 3.2 下一步按钮

```js
let manual_step_pending = false;

document.getElementById('step_button').onclick = function () {
  play_context.scene.resume();   // 若处于暂停，必须恢复以触发 update()
  manual_step_pending = true;
};
```

`play_context` 已在 `update()` 中保存（`let play_context = this;`），需将其提升到外层作用域使按钮回调可访问，或将按钮绑定移入 `update()`（与现有 Play/Pause 模式一致）。

在 `update()` 的 `execute_count == 0` 分支末尾追加：

```js
if (manual_step_pending) {
  play_context.scene.pause();
  manual_step_pending = false;
}
```

**语义**：无论当前状态如何，点击 → 推进恰好 1 个 step → 暂停。如果点击时正处于自动播放，效果是"播放到下一个 step 边界后停下"。

### 4. 后端默认值

`examples/stanford_town/frontend/translator/views.py:129`：

```python
def demo(request, sim_code, step, play_speed="2"):
```

改为：

```python
def demo(request, sim_code, step, play_speed="1"):
```

使 URL 缺省值映射到 `movement_speed=1`，即 0.5× 档，默认入口更慢更便于观察。

`urls.py` 中 `play_speed` 是 URL path 参数；URL 显式带值时（如 `views.py:205` 的快捷入口 `play_speed="3"`）行为不变。

## 数据流

无新增数据流。所有控件状态仅存在于前端 JS 局部变量：

- `movement_speed`（已存在）
- `execute_count_max`（已存在）
- `pending_movement_speed`（新增）
- `manual_step_pending`（新增）

## 错误处理

- 速度按钮 `data-speed` 仅取 1/2/4/8，与 tile_width=32 整除条件相容，无需运行时校验
- "下一步"按钮在场景已暂停时也能正常工作（先 resume 再设置标志，update 跑到 step 边界后再 pause）
- 连续快速点击"下一步"：每次点击都会设置 `manual_step_pending=true`，由于 `execute_count==0` 时立即 pause + 清标志，最多生效一次。多点击不会累积步数 — 这是可接受的行为（避免误触跳很多步）

## 测试计划

手动验收：

1. **标题显示**：页面顶部中央渲染 "生成式智能体 · 模拟回放"，下方原斜体说明保留
2. **默认速度**：访问 `/demo/<sim_code>/<step>/`（不带 play_speed）→ 0.5× 按钮高亮，sprite 移动速度为 1 px/帧
3. **速度切换**：依次点击 1× / 2× / 4×，下一个 step 边界开始 sprite 速度变化，按钮高亮同步切换，无明显闪烁或位置错位
4. **下一步（自动播放中）**：点击下一步 → 回放继续到当前 step 完成 → 暂停
5. **下一步（暂停中）**：先点 Pause，再点下一步 → 推进 1 个 step → 再次自动暂停
6. **下一步与 Play 交互**：手动步进后点 Play → 正常恢复自动播放
7. **时间标签**：每次 step 推进时间标签 +`sec_per_step` 秒（与改动前一致）

## 不引入的复杂度

- 不重构现有 `update()` 函数结构
- 不抽出独立的 controls 组件
- 不引入额外 JS 框架或状态管理
