# AGENTS.md

本文档为在 MetaGPT 仓库中工作的 AI 编码 Agent 提供指引。

## 项目概览

MetaGPT 是一个多智能体框架，模拟由基于 LLM 的角色（产品经理、架构师、项目经理、工程师等）组成的软件公司，通过 SOP 协作将一句话需求转化为交付物（PRD、设计文档、代码、文档等）。

- 核心理念：`Code = SOP(Team)`
- CLI 入口：`metagpt=metagpt.software_company:app`
- 库调用入口：`from metagpt.software_company import generate_repo`
- Python 版本要求：`>=3.9, <3.13`

## 仓库目录结构

```
metagpt/                 # 主包
  actions/               # 原子化 LLM 驱动步骤（写代码、设计 API 等）
  roles/                 # 角色类（Engineer、Architect、ProductManager……）
  provider/              # LLM 提供商集成（OpenAI、Azure、Anthropic……）
  rag/                   # RAG 引擎、检索器、向量嵌入
  tools/                 # 角色可调用的工具
  memory/                # 短期 / 长期记忆后端
  strategy/              # 规划与推理策略
  ext/                   # 扩展 / 实验性模块
  configs/               # Pydantic 配置模型
  schema.py              # 核心数据结构（Message、Document……）
  context.py             # 全局 Context 对象
  team.py                # 团队编排
  software_company.py    # CLI + generate_repo 入口
config/                  # 用户配置示例（config2.example.yaml）
examples/                # 可运行的示例
tests/                   # Pytest 测试套件（目录结构镜像 `metagpt/`）
docs/                    # 文档及多语言 README
```

## 环境搭建

```bash
# 以可编辑模式安装，包含 dev/test 额外依赖
pip install -e .[dev,test]
pre-commit install
```

用户配置文件位于 `~/.metagpt/config2.yaml`，以 `config/config2.example.yaml` 为模板。**切勿提交真实 API 密钥。**

## 代码规范

- **格式化**：`black`，`--line-length 120`
- **导入排序**：`isort --profile black`（跳过 `__init__.py`）
- **代码检查**：`ruff`（配置见 `ruff.toml`，`target-version = "py39"`）
- 保持 Python 3.9 兼容性；不使用 3.10+ 语法（禁用 `match`，除非有 `from __future__ import annotations`，否则不使用 `X | Y` 联合类型注解）。
- 结构化数据优先使用 `pydantic` 模型（新代码遵循 pydantic v2 规范，旧代码中仍有 v1 写法——保持与所在文件一致）。
- 异步优先：`Action.run` 和 `Role._act` 等方法均为 `async`，使用 `asyncio` 和 `await`，不阻塞事件循环。
- 日志：使用 `from metagpt.logs import logger`，不使用 `print`。

提交前运行格式化/检查工具：

```bash
pre-commit run --all-files
# 或分别执行
ruff check . --fix
black --line-length 120 .
isort --profile black .
```

## 测试

- 框架：`pytest`，配合 `pytest-asyncio`、`pytest-cov`、`pytest-mock`。
- 测试目录结构镜像 `metagpt/`，位于 `tests/metagpt/` 下。
- 许多需要网络/API 密钥的集成测试已在 `pytest.ini` 中显式忽略——新增需要凭据的测试前请先查阅该文件。
- 异步测试：添加 `@pytest.mark.asyncio` 标记。
- Mock 文件位于 `tests/mock/`；复用 `mock_llm_response` 风格的 fixture，不调用真实 LLM。

运行测试：

```bash
pytest tests/metagpt/<模块>/test_<文件>.py -q
pytest -k <表达式> -q
```

不要盲目运行完整测试套件；覆盖率收集耗时较长，且很多测试依赖 API 密钥。

## 新增功能

- **新角色**：继承 `metagpt.roles.role.Role`，定义 `_act` / `_think`，注册 action，放入 `metagpt/roles/`，并在 `tests/metagpt/roles/` 下添加测试。
- **新 Action**：继承 `metagpt.actions.action.Action`，实现 `async def run(...)`，放入 `metagpt/actions/`。
- **新 LLM 提供商**：继承 `metagpt.provider.base_llm.BaseLLM`，在 `metagpt/provider/__init__.py` 中注册，并在 `metagpt/configs/llm_config.py` 中添加 `LLMType` 条目。
- **新工具**：添加至 `metagpt/tools/`，通过工具注册表注册，使角色能够发现并调用。

扩展公开 API 时，须同步更新或补充 docstring，并添加对应测试。

## 禁止事项

- 不要提交密钥、真实 API key 或 `~/.metagpt/` 下的任何文件。
- 不要破坏 Python 3.9 兼容性。
- 不要在 `async` 路径中引入同步阻塞调用（async 代码中禁用 `requests.get`，改用 `aiohttp`/`httpx`）。
- 不要绕过 `Context` / 配置系统直接读取环境变量，应通过 `metagpt.config2.Config` 统一访问。
- 不要向 `requirements.txt` 添加重型依赖，优先在 `setup.py` 的 `extras_require` 中声明。

## 参考资源

- `README.md` — 面向用户的概览与安装说明
- `docs/` — 设计文档及多语言指南
- `examples/` — 规范用法示例，新示例应参照其风格
- `config/config2.example.yaml` — 完整配置项参考
