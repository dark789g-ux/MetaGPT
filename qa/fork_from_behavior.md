# Stanford Town Dashboard：勾选 "Fork from" 后会发生什么？

## 问题

在 Stanford Town Dashboard 启动新模拟的表单里，如果勾选了 "Fork from"，运行时会发生什么？

## 答案

需要先澄清一点：**"Fork from" 本身不是勾选框**，它是一个**必填的下拉框**（见 [landing.html:36](../examples/stanford_town/frontend/templates/landing/landing.html#L36)）。它旁边那个小复选框 `显示全部存档`（id=`show-all-forks`）只是切换这个下拉里列出的候选项范围，并**不**决定 "要不要 fork"。

### 1. `Fork from` 下拉（必选）

- 后端在 [sim_utils.py:92-99](../examples/stanford_town/frontend/translator/sim_utils.py#L92-L99) 强制校验：
  - `fork_sim_code is required`
  - 对应的 `storage/<fork>/reverie/meta.json` 必须存在
  - 否则直接报错拒绝启动
- 启动时该值会作为参数传给 `run_st_game.py`：
  ```
  run_st_game.py <idea> <fork_sim_code> <sim_code> --n_round N
  ```
  （见 [sim_utils.py:142-148](../examples/stanford_town/frontend/translator/sim_utils.py#L142-L148)）
- 运行时它的作用：把 `storage/<fork_sim_code>/` 整个存档当作**起点**复制出一份新存档 `storage/<sim_code>/`，人物、空间记忆、associative memory、scratch、reverie/meta.json 全部继承，新模拟在这份初始世界状态上继续推进 `Rounds` 步。

### 2. `显示全部存档` 复选框

- 仅前端行为（见 [landing.html:142-155](../examples/stanford_town/frontend/templates/landing/landing.html#L142-L155)）
- **不勾选**：下拉只列 `BASE_SIMS`（原生 base 存档，例如 `base_the_ville_n25`、`base_the_ville_isabella_maria_klaus`）
- **勾选**：下拉列出 `ALL_SIMS`，包含之前跑出来的派生存档（如 `test_sim`、`test_breakfast`），就可以**基于一个已经跑过的存档继续 fork**——相当于"接着之前的剧情往下演"

## 总结

截图里勾选 `显示全部存档` 的实际效果是：下拉里会出现所有非 base 的旧存档；你选哪个，新模拟就从那个存档的最后状态克隆出一份作为起点开跑。如果不勾，就只能从原始 base 模板派生。

**两种情况下都会发生 fork**——区别只是**能选谁**作为父存档。

## 相关代码位置

- 前端模板：[examples/stanford_town/frontend/templates/landing/landing.html](../examples/stanford_town/frontend/templates/landing/landing.html)
- 后端校验与启动逻辑：[examples/stanford_town/frontend/translator/sim_utils.py](../examples/stanford_town/frontend/translator/sim_utils.py)
- 实际跑模拟的入口：`examples/stanford_town/run_st_game.py`
