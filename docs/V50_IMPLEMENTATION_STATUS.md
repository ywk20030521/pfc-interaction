# PFC Interaction 5.0 实现状态矩阵

**规则：** 规范描述的是目标能力，不自动代表已实现。本文件逐项标注状态与证据，禁止将「设计完成 / 代码存在 / 单测通过」写成「工具可调用 / 科学有效」。

## 状态用语

| 用语 | 含义 |
|---|---|
| 已实现 | 有代码且可调用，并有离线测试证据 |
| 接口层通过 | 4.0 IF0 / v41 契约或新 5.0 数据契约测试通过 |
| 协议层离线通过 | 5.0 六阶段/讨论/决策/标定闭环经离线回放通过 |
| 工具层在线通过 | 真实 itasca-mcp / bridge 往返并取得 tool_task_id |
| 工具层待验证 | 需要真实 itasca-mcp / bridge（本次未验证） |
| 科学层未通过 | 物理有效性、参数标定未达标 |
| 宿主边界 | 依赖宿主面板能力，Skill 只能提供内容与元数据 |

## 架构规范 PFCI-ARCH-5.0

| 强制项 | 状态 | 实现/证据 |
|---|---|---|
| 单一 Skill、阶段与模块不一一绑定 | 已实现 | `SKILL.md`；`core/v50_workflow.plan_modules()`；测试 `test_stage_and_module_are_not_one_to_one` |
| Agent 主导、用户决策 | 已实现 | `core/v50_decisions.py`：建议不自动确认 |
| 六阶段覆盖、回退/重开 | 协议层离线通过 | `core/v50_workflow.py`；演练报告含 ROLLBACK |
| Core 持续上下文与讨论状态 | 已实现 | `core/v50_context.py`、`core/v50_discussion.py` |
| 不以固定问题数推进 | 已实现 | `DiscussionManager.can_advance()` 基于完成条件 |
| 参数标定跨模块闭环 | 协议层离线通过 | `modules/v50_calibration.py` |
| M4 运行控制 / M5 科学诊断分离 | 已实现（接口层） | M4 记录工具证据，M5 单独写 `diagnose_trust()` |
| M5 可信度 / M6 定量分析分离 | 已实现 | `diagnose_trust()` 是 `compute_error()` 的前置条件 |
| 复用既有工具/不建 Web/DB | 已实现 | 仅本地文件与既有 `adapters/itasca_mcp.py`；无新增服务 |
| 设计/实现/运行/科学验证状态区分 | 已实现 | 本文件 + `docs/V50_ACCEPTANCE.md` |

## 模块规范 PFCI-MOD-5.0

| 模块/协议 | 状态 | 说明 |
|---|---|---|
| M1–M6 职责边界、统一 `module_result` | 接口层通过 | 4.0 `core/contract.py` Envelope；5.0 契约字段在 `core/v50_context.py` 的研究上下文中体现 |
| 对照组强制判断 | 已实现（既有） | 4.0 `modules/nature_experiment_design.py` 与 M2 设计评审 |
| M3 七层检查 | 已实现（既有） | 4.0 `modules/v41_modeling.py` 分阶段检查；5.0 不重复实现 |
| M4 复用 MCP、禁止复制执行器 | 已实现 | 5.0 标定循环只接收工具证据，不调用 PFC |
| M5 五层诊断、M6 强制边界 | 协议层离线通过 | 5.0 演练含诊断→误差顺序 |
| 参数标定 11 步协议 | 协议层离线通过 | `ParameterCalibrationLoop`；测试 9 条 |
| 每模块正常/边界/接口/失败/证据案例 | 部分 | 旧 4.0 用例覆盖模块；5.0 新增覆盖上下文/标定/交互，未逐模块重写六类案例 |

## 人机协作规范 PFCI-HUMAN-5.0

| 强制项 | 状态 | 实现/证据 |
|---|---|---|
| 自然语言持续讨论、先分析后追问 | 已实现 | `DiscussionManager.add_turn()` / `respond_to_user()`；无分析追问被拒绝 |
| 进入卡片前的讨论深度校验 | 已实现 | `gate_for_card()` / `require_depth()` + `InteractionCoordinator.prepare()`；7 条测试覆盖浅讨论拒绝 |
| 有依据建议、替代方案、风险 | 已实现 | `make_proposal()` / `ProposalOption.validate()` |
| 无固定问题数 | 已实现 | `can_advance()` |
| Chat/AUQ 事项去重与回退 | 已实现 | `InteractionRouter.open()` / `switch_channel()` |
| AUQ 不可用时基本协作可用 | 已实现 | `auq_available=False` 回退 Native Chat（测试覆盖） |
| 讨论/确认/授权/执行/验证分离 | 已实现 | 回答不确认、参数变更使授权失效（测试覆盖） |
| 高影响操作明确授权 | 已实现 | `HIGH_IMPACT_OPERATIONS` + `DecisionManager.authorize()` |
| 异常提醒含证据/影响/建议 | 协议层离线通过 | 演练回退含证据、影响资产、失效决策 |
| 工具结果回到 Agent 并解释 | 接口层通过 | 4.0 Core 反馈链；5.0 卡片提交要求 `requires_agent_feedback` |

## 卡片规范 PFCI-CARD-5.0

| 强制项 | 状态 | 说明 |
|---|---|---|
| 三类卡片、单卡单决策、最多三卡 | 已实现 | 复用 4.0 `core/question.py` 与 `modules/question_cards.py`；`validate_batch()` |
| 标题/说明/选项长度上限 | 已实现 | `validate_card()`；新测试覆盖批次 |
| 先讨论后结构化 | 已实现 | `InteractionCoordinator.prepare()` 只接收通过自检的卡片 |
| 推荐有依据、高级依据折叠 | 已实现 | `Option.rationale` / `technical_basis` / `question_meta` |
| 提交回写与 Agent 反馈要求 | 已实现 | `submit()` 返回 `requires_agent_feedback=True` |
| 卡片不绕过 Core 执行 | 已实现 | 只有执行卡 + 明确回答才进入授权；测试覆盖 |
| 徽章/按钮文案/窄屏视觉 | 宿主边界 | 宿主面板决定；Skill 输出 header、prompt、meta |

## 工具层与 5.0 执行载体（2026-11-27 在线补验）

| 项 | 状态 | 证据 |
|---|---|---|
| PFC2D Console + bridge 0.6.17 连通 | 工具层在线通过 | `/health=success`、`execute_code` 真实往返 `pfc-91953ca2` |
| 4.0 M3 脚本执行 / M4 真实任务 ID | 工具层在线通过（2D/3D） | `tests/test_v40_tooling.py` 3 条在 PFC2D/PFC3D 均通过；2D `pfc-d9040b69`/`pfc-2c4e3299`，3D `pfc-83413d94`/`pfc-1b82f099` |
| 4.0 Envelope → 5.0 `module_result` | 已实现 | `modules/v50_execution.py::module_result_from_envelope()` + 单元测试 |
| 5.0 Core 授权网关调用真实 bridge | 已实现 | `V50ExecutionGateway`；无授权/桥离线返回 BLOCKED 且不伪造 ID |
| 5.0 标定闭环用真实工具证据 | 工具层在线通过（2D/3D） | `examples/v50/real_bridge_execution.py` → `REAL_BRIDGE_PASS`；2D `pfc-1f2c971a`，3D `pfc-b9f18288` |

## 明确未实现或未验证

- 独立数据库、Web 后台、Agent 退出后主动推送：按 5.0 轻量原则不实现。
- 科学有效性：围压维持、胶结保留率、峰后采样等历史问题未关闭。
- 端到端真机科研案例：本次真实执行仅验证工具链协议（颗粒计数），未运行完整科研任务。
- 宿主 UI 动态视觉验证：属宿主能力边界。
