# PFC Interaction Skill

面向 Itasca PFC（PFC2D / PFC3D）仿真的科研协作 Skill。让 Agent 围绕 PFC 实验与操作者持续协作：汇报状态、解释现象、讨论方案、协商参数、接收决策并验证执行，形成 Human ↔ Agent ↔ itasca-mcp 的闭环。

一个 Skill 内含六个专业模块（M1 科研规划、M2 实验设计、M3 数值建模、M4 仿真管理、M5 科学诊断、M6 科学分析），共享一套交互与执行机制，用户无需选择模块。

## 核心特性

- **阶段门批准**：`V41CoreDispatcher.dispatch()` 校验 `ApprovalLedger` 中绑定 `context_version` 的真实批准；前置批准缺失即返回 BLOCKED。批准只能由 `resolve_decision()` 写入，payload 中的 `approved: true` 无效。
- **多轮协商**：M1 两轮、M2 四轮；每个参数记录 unit / source / confirmed / missing_risk，未确认字段不得进入建模。
- **真实执行**：M4 只通过 Core I5 提交，保存真实 `tool_task_id`；桥离线或物理准入失败返回 BLOCKED，不伪造执行结果。峰后在末点或缺少 tool_task_id 时质量闸门 FAIL。
- **提问卡片**：A/B/C 三种内部分类（科研讨论 / 参数决策 / 执行确认），按模型阶段 M1→M6 顺序展示 28 张卡；面板呈现遵循设计标准（阶段·决策 header、标题+说明、物理意义选项、独立建议区），类型不暴露给用户。
- **可审计**：事实/推断/建议分层，所有决策落账，产物版本化不覆盖。

## 安装

需要 Python 3.10+、itasca-mcp 与可用的 PFC 引擎（PFC2D 或 PFC3D）。

```bash
git clone https://github.com/ywk20030521/pfc-interaction.git
```

将 `pfc-interaction/` 目录放入 WorkBuddy 的项目级 skills 目录：

```
<your-project>/.workbuddy/skills/pfc-interaction/
```

运行时只需 `SKILL.md` 与 `references/`；其余目录用于安装、验收与升级。

## 快速开始

在 WorkBuddy 中直接描述一个 PFC 实验任务，例如：

> 用三轴压缩实验研究围压对胶结颗粒集合体峰值强度的影响，围压 1/5/10 MPa。

Skill 会自动编排 M1→M6：先与你确认研究计划与实验参数，再生成分阶段脚本、真实执行、诊断与分析。每步需要你决策时会通过提问卡片呈现。

示例脚本：

```bash
python examples/v41/triaxial_longitudinal_slice.py   # 三轴纵向闭环（离线数据回放）
python examples/v40/interactive_walkthrough.py        # 六模块自动走查
python examples/v40/full_research_loop.py             # 完整科研案例
```

## 架构

```
pfc-interaction/
├── SKILL.md                  # Skill 入口与运行时规则
├── core/                     # 统一契约、状态机、决策账本、阶段门、工作流、提问结构
├── adapters/itasca_mcp.py    # 真实执行适配器（Core I5 → bridge HTTP）
├── modules/                  # M1–M6 实现、实验知识库、卡片分类与顺序契约
├── references/               # 运行时按需读取的语义规范
├── templates/                # 状态汇报、参数协商、异常报告模板
├── tests/                    # 接口级与验收测试
├── examples/                 # 端到端演示与验收脚本
└── docs/                     # 技术报告、接口冻结规范、规范验收
```

详见 `references/architecture.md`、`references/module_contract.md` 与 `docs/PFC_Interaction_4.0_技术报告.md`。

## 测试

```bash
python -m unittest discover -s tests -p "test_*.py"
```

当前 98 条测试（4 条因 PFC bridge 离线跳过）。需要真实 PFC 执行时，先用 `pr0/poc/start_bridge_p2d.dat` 或 `start_bridge_p3d.dat` 启动对应 Console 的 bridge。

## 已知限制

- **科学层未验收**：端到端物理标定未完成。围压建立达标、峰后捕获达标，但加载中围压维持与胶结保留率未达标；不宣称整体验收通过。
- **工具层依赖 bridge**：无真实 `tool_task_id` 一律 BLOCKED，不用历史数据回放冒充执行。
- **面板渲染**：卡片内容按设计标准输出，最终视觉由宿主面板能力决定。

状态用语分层：`已实现` / `接口层通过` / `协议层实测通过` / `阻塞已确认` / `未通过`。

## 许可

MIT — 详见 [LICENSE](LICENSE)。
