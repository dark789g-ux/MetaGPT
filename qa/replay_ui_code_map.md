# 回放界面 ↔ 代码地址速查

记录 stanford_town 前端回放界面每块 UI 对应的源码路径，方便直接复制定位。

## URL → 模板路径

| URL 入口 | View | 模板 | 主脚本 |
|---|---|---|---|
| `/replay/<sim_code>/<step>/` | `translator.views.replay` | `templates/home/home.html` | `templates/home/main_script.html` |
| `/demo/<sim_code>/<step>/<play_speed>/` | `translator.views.demo` | `templates/demo/demo.html` | `templates/demo/main_script.html` |
| `/simulator_home` | `translator.views.home` | `templates/home/home.html` | `templates/home/main_script.html` |

源码定位：

- View：`examples/stanford_town/frontend/translator/views.py`
- URL 路由：`examples/stanford_town/frontend/frontend_server/urls.py`
- Django 设置：`examples/stanford_town/frontend/frontend_server/settings/base.py`
- 启动器：`launch_stanford_town.py`（cwd = `examples/stanford_town/frontend`）

## UI 元素 ↔ 代码位置

### 标题
- `templates/home/home.html:5-7` — `/replay/` 路径
- `templates/demo/demo.html:5-7` — `/demo/` 路径

### Current Time 显示
- `templates/home/home.html:14-18`（`#game-time-content`）
- `templates/demo/demo.html:15-19`
- JS 更新：`templates/home/main_script.html` 第 509 行（offline replay）；`templates/demo/main_script.html` 第 488 行

### 控制区按钮组（速度 / Play / Pause / 下一步）
- `templates/home/home.html:21-42`
- `templates/demo/demo.html:20-40`
- 按钮绑定 JS：
  - `templates/home/main_script.html` 脚本末尾（`var play_button` / `pause_button` / `step_button` + `.speed-btn` forEach）
  - `templates/demo/main_script.html` 脚本末尾

### 速度与步进核心状态变量
- `templates/home/main_script.html:121-125` — `movement_speed` / `pending_movement_speed` / `manual_step_pending` / `play_context`
- `templates/demo/main_script.html:87-90` — 同上

### 暂停场景（默认进入手动步进）
- `templates/home/main_script.html` `create()` 末尾（`OFFLINE_MOVEMENT` 时 `scene.pause()`）
- `templates/demo/main_script.html` `create()` 末尾（无条件 `scene.pause()`）

### Step 边界逻辑（speed 切换 / 手动步进暂停在此触发）
- `templates/home/main_script.html` 在 `phase == "execute"` 的 `else` 分支末尾（execute_count 用尽时）
- `templates/demo/main_script.html` 在 `if (execute_count == 0) { ... }` 块内

### 角色头像列表 / 状态详情卡片
- `templates/home/home.html:36-60`
- `templates/demo/demo.html:38-93`
- 状态字段：`current_action__<name>` / `target_address__<name>` / `chat__<name>` / `quick_emoji-<name>`

### Phaser 场景
- 地图加载：`templates/<home|demo>/main_script.html` `preload()` 函数
- 地图 JSON：`static_dirs/assets/the_ville/visuals/the_ville_jan7.json`
- tileset 图：`static_dirs/assets/the_ville/visuals/map_assets/`
- 角色 atlas：`static_dirs/assets/characters/<name>.png` + `atlas.json`

### 离线回放数据
- 注入入口：`templates/home/main_script.html:12`（`all_movement|json_script:"all_movement_json"`）
- 解析：`templates/home/main_script.html:39-44`（`OFFLINE_MOVEMENT`）
- 数据源（磁盘）：
  - 移动帧：`examples/stanford_town/storage/<sim_code>/movement/<step>.json`
  - 环境快照：`examples/stanford_town/storage/<sim_code>/environment/<step>.json`
  - 角色目录：`examples/stanford_town/storage/<sim_code>/personas/`

## 常用配置位

| 想改什么 | 改哪 |
|---|---|
| 默认回放速度（demo URL 缺省） | `views.py:129` `play_speed="1"` |
| 速度档位与映射 | `views.py:133-134` `play_speed_opt` |
| 速度按钮档位（前端） | `home.html:23-26` / `demo.html` 对应行 |
| 每 step 模拟秒数 | `storage/<sim_code>/reverie/meta.json` 的 `sec_per_step` |
| 画面分辨率 / 缩放 | `main_script.html` 顶部 `config = { width, height, scale.zoom }` |

## 排错速查

- **改了模板没生效** → Django dev server 用 `--noreload` 启动时，进程内存里的旧模板/Python 模块不会刷新；改 Python 必须重启，改模板理论上不需要但保险起见也重启
- **走 `/replay/` 看不到 demo 的改动** → 两套模板（`home/` vs `demo/`），改动需要同步
- **`play_speed` URL 显式带值与缺省值** → `views.py:205` 的快捷入口写死 `play_speed="3"`，不走 URL 缺省
