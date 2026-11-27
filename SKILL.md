---
name: pfc-interaction
description: Continuous deep research collaboration for PFC2D/PFC3D studies. Owns research issues, multi-round scientific discussion, evidence and hypothesis registers, decisions and authorization. Use for 科研议题树、深度科研讨论、实验设计与参数标定协商、执行授权、结果解释、阶段回退与科研档案；requires itasca-mcp and a licensed PFC engine.
metadata:
  short-description: Deep research discussion and decision authority for PFC studies
license: MIT
version: 5.1.0
agent_created: true
---

# PFC Interaction Skill 5.1

## 定位

一个面向 PFC2D/PFC3D 的轻量化科研协作 Skill：围绕研究人员的科学问题，持续主持讨论、组织证据、协调专业能力和执行工具，直到形成有边界、可追溯的科研结论。5.1 在 5.0 科研工作流底座上，把升级目标扩展为完整的深度科研协作：科研议题树、D0–D3 讨论、证据/假设成熟度、跨会话恢复、模式路由、M1–M6 深度包装、五类卡片与可复用科学层闸门。

- 用户只面对一个 Skill，不需要选择 M1–M6；阶段是用户可见工作流，模块是后台专业能力，二者不一一绑定。
- `itasca-mcp` 负责 PFC ↔ Agent（执行、任务、状态、上下文）；本 Skill 负责 Human ↔ Agent（讨论、解释、建议、决策、授权、反馈）；Agent 是两条通道之间唯一的语义理解与协调主体。
- 不重复实现 Itasca MCP/Bridge、PFC 执行器或 Scientific Visualization Skill 的能力。
- 设计完成、代码实现、工具可调用、真实 PFC 执行、科学有效性验证是不同状态；不得互相替代。

## Responsibility boundary

This Skill owns the Human–Agent research loop: issue tree, deep discussion,
evidence and hypothesis registers, decision and authorization state, stage
orchestration and research archive. It does not own PFC execution, raw data
capture, standardized data packages, charts, Viewer rendering or publication
figures.

- `pfc-headless` owns verified Console/Bridge instances, Project/Case/Run
  lifecycle, raw capture, immutable standardized delivery (`pfc.standardized-experiment@1.0.0`)
  and analysis feedback ingestion.
- `pfc-scientific-visualization` owns derived quantities, statistics, chart
  decisions, Three.js/ECharts Viewer, publication composition and analysis
  provenance.
- `itasca-mcp` / `itasca-mcp-bridge` remain the execution layer.
- This Skill consumes Run IDs, Findings and analysis results from those Skills;
  it never duplicates or mutates their immutable outputs.

## Non-negotiable truth rules

- Keep `REAL_PFC`, `COMPUTED_RESULT`, `AGENT_INFERENCE`, `USER_EXPERIENCE` and
  `UNVERIFIED_ASSUMPTION` distinct. Never promote inference or experience to a
  tool observation.
- `CONFIRMED` is a decision state, never scientific validation. Use
  `NOT_VERIFIED` until the relevant evidence has actually been checked.
- An execution authorization must bind operation, target, Project/Case/Run,
  model/parameter/matrix versions and scope; context changes invalidate it.
- A card answer is not a decision; a decision is not execution; execution is
  not scientific validation.
- D2/D3 issues must pass substantive discussion stages before being converted
  into a card or a module result.
- Mark missing channels `NOT_CAPTURED`, unsupported channels `NOT_SUPPORTED`,
  invalid checks `INVALID`; never zero-fill or synthesize data to pass a gate.

> 本 Skill 必须遵守 PFC Interaction 5.1 总技术报告及四份强制规范。对于复杂科研议题，必须执行多轮实质性讨论、方案比较、反方审查、用户反馈吸收、方案修订和验证规划。禁止以固定问题数量或少量问答自动完成研究阶段。必须维护课题级议题、假设、证据、决策和变更档案。Native Chat 承担复杂讨论；AUQ 仅承载已结构化的事项。任何模块、模板和卡片不得绕过上述规则。如某项能力受环境限制，必须明确报告限制和降级行为。

## 六阶段科研工作流

| 阶段 | 核心问题 | 主要阶段产物 |
|---|---|---|
| S1 研究对象与科研目标 | 研究什么、为什么、需要回答什么 | research_brief / research_question / research_hypotheses / research_scope |
| S2 实验类别与实验设计 | 通过什么实验回答，是否需要对照 | experiment_design / experiment_matrix / variable_schema / measurement_plan |
| S3 技术方案与建模路线 | 如何转化为合理可执行的 PFC 模型 | technical_route / model_design / model_requirements / model_validation_plan |
| S4 参数确定与标定 | 参数从哪来，如何证明能产生目标响应 | parameter_register / calibration_plan / calibration_matrix / calibration_results / calibrated_parameters |
| S5 仿真执行与异常干预 | 如何可靠执行并及时控制异常 | simulation_config / simulation_status / checkpoint_manifest / anomaly_records / execution_report |
| S6 结果分析与科研总结 | 得到什么，是否可信，支持什么结论 | analysis_results / comparison_report / diagnosis_report / analysis_report / research_conclusion |

默认主线 S1→S6，但允许 S2→S1、S3→S2、S4→S3、S5→S3/S4、S6→任一前序阶段。每次回退必须记录触发证据、影响范围、受影响决策和需要重做的产物。

## Core 五项能力（跨轮次，不是路由器）

1. **Context Manager**：维护统一科研上下文、阶段/模块状态、参数版本、证据与 provenance（`core/v50_context.py`）。
2. **Discussion Manager**：维护讨论主题、用户观点、备选方案、未决问题与阶段总结；先分析再追问（`core/v50_discussion.py`）。
3. **Reasoning & Proposal**：基于证据提出有依据的方案、替代方案、风险与影响分析（`make_proposal()`）。
4. **Decision Manager**：讨论→确认→授权→执行→验证严格分离；授权绑定任务/对象/版本/范围；版本变化使旧授权失效（`core/v50_decisions.py`）。
5. **Workflow Orchestrator**：阶段推进、产物审核、完成条件判断、回退与影响分析（`core/v50_workflow.py`）。

**禁止：** 固定问题数或固定轮数作为阶段完成条件；把 Agent 建议写成用户决定；把卡片回答当作执行授权；把工具执行成功当作科学结论成立；把脚本生成当作模型验证通过。

## 5.1 科研连续性与深度讨论

5.1 把核心工作对象从「问题」提升为**科研议题（Research Issue）**。复杂议题必须按 D0–D3 深度等级推进；D2/D3 不得首轮定案，必须经过实质阶段：问题界定、候选方案、反方审查、用户反馈、方案修订，核心议题还需验证计划。轮数只是过程指标，只有产生新分析、证据、反例、修订或综合才计入实质迭代。

- `core/v501_issues.py`：议题类型/状态/优先级、依赖、待讨论队列、重开与失效。
- `core/v501_deep_discussion.py`：D0–D3 门槛、8 种讨论模式、用户修正吸收与修订记录。
- `core/v501_evidence.py` / `v501_change.py`：八类证据、假设成熟度、变更影响与重开、CONFIRMED ≠ VALIDATED。
- `core/v501_archive.py`：生成课题级档案（章程、议题树、讨论、假设、决策、证据、实验、模型、仿真、异常、分析、变更）。
- `modules/v501_cards.py`：讨论收敛/参数登记/方案确认/执行授权/检查点决策五类卡片；卡片必须绑定议题并通过深度门槛。

## 持续协作循环

接收意图或系统观察 → 读取上下文与历史决策 → 识别真正待解决问题 → 分析事实/假设/证据/冲突 → 形成解释、建议、备选方案与风险 → 开放讨论 → 更新讨论与决策状态 → 判断继续讨论/调用模块/请求确认 → 检查阶段完成条件并推进或回退。

- 用户提出观点时，先复述理解并给出专业分析，再决定是否追问。
- 每轮讨论尽量包含当前理解、专业分析、证据与假设、备选方案、影响分析、关键分歧、下一步；至少要有专业分析。
- **进入结构化卡片前必须调用 `DiscussionManager.gate_for_card()`**：至少具备理解、专业分析、证据或假设、备选方案、影响分析；高影响决策要求两个及以上备选。深度按内容维度检查，不按问题数或轮数。`InteractionCoordinator.prepare()` 接入 DiscussionManager 时会自动执行该门槛，深度不足直接拒绝生成卡片。
- 暂定推进只能在用户明确要求、假设与不确定已记录、后续可验证且不触发未授权高影响操作时使用。
- 阶段总结保留已确认事项、建议事项、未决问题、假设、风险和下一阶段前置条件；总结不代表讨论永久终止。

## 双通道与卡片

- **Native Chat（默认）**：科学问题、方案比较、参数策略、异常归因、结果解释等开放式讨论。
- **AUQ（可选）**：已谈清楚的选择、参数/范围收集、异步待办、执行前明确审批；AUQ 不可用时回退 Native Chat 并说明。
- 同一事项以 `research_task_id + stage_id + decision_topic` 为稳定键；Chat 已答不得重复投递 AUQ；同一事项只能有一个有效交互实例。
- 结构化卡片只在问题明确且能降低用户负担时使用；复杂科学判断不得压缩成失真的单选题。5.1 五类卡片（讨论收敛/参数登记/方案确认/执行授权/检查点决策）以 `docs/PFCI-CARD-5.0.1.md` 为唯一详细依据；`assets/v510_cards.html` 是宿主渲染参考。
- 卡片回答只回写交互与决策上下文；Agent 必须解释回答影响。执行确认卡必须列出动作、对象、版本和影响，无默认勾选、无静默延后，且不绕过 Core 直接触发工具。
- **宿主投递不是假定能力**：每次会话先通过 `core/host_interaction.py::probe_host_capability()` 记录 L0/L1/L2。没有宿主结构化提问回调时，卡片只是数据；`ask()` 返回 `PENDING_NATIVE_CHAT` 且 `delivered=False`，Agent 必须在 Native Chat 提出文字问题并结束本轮等待。禁止写成"已投递/已询问"。
- **强制停机协议**：正式仿真缺少实验目的、边界类型、试样尺寸、目标围压、加载终点或参数来源时，`core/stop_protocol.py::require_user_decision()` 返回 `status: WAITING_FOR_USER`、`pending_decision_id`、`allowed_next_action: none`。该轮不得调用 `model new`、`itasca_execute_task` 或创建正式 Run；用户回答只更新上下文，必须再次确认并取得授权。
- **执行闸门**：正式 Run 必须把 `FormalRunAuthorization.to_headless_args()` 的授权字段传给 `pfc-headless run prepare`；无授权只能显式 `--pilot` 并标记为 `UNACCEPTED_TECHNICAL_PILOT`。不得直接调用 `itasca_execute_task` 绕过授权网关。

## 参数标定（S4 跨模块闭环）

M2 定义标定试验、目标指标和工况矩阵；Core 与用户确认目标与接受标准；M3 将参数写入模型并生成版本；M4 用真实工具证据执行并保存输出；M5 判断数据可信度；M6 计算误差、敏感性与比较；Core 主持调整讨论，用户确认下一轮参数；重复至达标或如实记录无法达标。禁止凭曲线「看起来接近」宣称成功、无目标数据自动调参、不记录变更历史、把单一拟合宣称为唯一解、把未验证参数标记为已标定。实现见 `modules/v50_calibration.py`。

## 实现状态（必须如实区分）

| 能力 | 状态 | 证据/说明 |
|---|---|---|
| 4.0 六模块契约、v41 阶段门、提问卡片 V2 | 已实现并回归通过 | `tests/` 既有 4.0 用例 |
| 5.0 上下文/状态/证据/参数/决策模型 | 已实现 | `core/v50_context.py`，36 条新增离线用例 |
| 持续讨论、方案比较、授权与双通道路由 | 已实现 | `core/v50_discussion.py`、`core/v50_decisions.py`；讨论深度门槛 `gate_for_card()` + 卡片准备前强制校验 |
| 5.1 议题树、D0–D3 深度讨论、证据/假设、变更档案、五类卡片 | 已实现 | `core/v501_*.py`、`modules/v501_cards.py`；14 条协议测试 + 复杂案例回放 |
| 5.1 跨会话恢复、模式自动路由、M1–M6 深度包装 | 已实现 | `core/v510_continuity.py`、`v510_routing.py`、`modules/v510_deep_modules.py`；9 条发布测试 |
| 宿主 UI 渲染 | 参考实现完成 | `assets/v510_cards.html`：五类卡片、折叠依据、窄屏、文字状态；宿主实际渲染仍由平台决定 |
| 宿主结构化提问通道 | 需运行时探测，未假定可用 | `core/host_interaction.py` L0/L1/L2 探测；无回调时返回 `PENDING_NATIVE_CHAT`，不得声称已投递 |
| 提问后强制停机 / 正式 Run 授权闸门 | 已实现并通过离线验收 | `core/stop_protocol.py`；`tests/test_interaction_runtime_gate.py` 8 条覆盖诊断报告 7 项条件；需与 `pfc-headless` 授权闸门配套使用 |
| 端到端宿主交互（卡片自动显示并回写） | 未通过 | 宿主 UI 渲染仍为参考实现；Native Chat 必须由 Agent 主动停机等待 |
| 六阶段编排、回退与影响分析 | 已实现 | `core/v50_workflow.py` |
| 参数标定闭环、卡片交互适配 | 已实现 | `modules/v50_calibration.py`、`modules/v50_interaction.py` |
| 协议层端到端离线演练 | 通过 | `examples/v50/full_stage_walkthrough.py` |
| 5.0 执行载体（`module_result` + Core 授权网关） | 已实现、在线通过 | `modules/v50_execution.py`；`examples/v50/real_bridge_execution.py` 取得真实 `tool_task_id` |
| 真实 PFC 工具证据 | 工具层在线通过 | bridge 0.6.17 / PFC2D Console；`tests/test_v40_tooling.py` 3 条真实通过 |
| 科学层：围压控制与机制比较 | PASS | `core/v510_physics.py`；3 工况围压比 0.975–1.000、加载中漂移 ≤10%、69 个真实 tool_task_id；报告 `outputs/v510_acceptance/SCIENTIFIC_REPORT.md` |
| 材料参数定量标定 | 未通过/不在范围 | pb_ten 1/2 MPa 仍为经验初值，不得外推为真实岩石参数 |

详细状态见 `docs/V50_IMPLEMENTATION_STATUS.md`、`docs/V501_IMPLEMENTATION_STATUS.md`；验收记录见 `docs/V50_ACCEPTANCE.md`、`docs/V501_ACCEPTANCE.md`。

## 参考文档

| 文档 | 内容 |
|---|---|
| `docs/README_五份文件关系与使用说明.md` | 5.0.1 五份文件关系、冲突裁定与实现声明 |
| `docs/PFCI-ARCH-5.0.1.md` | PFCI-ARCH-5.0.1 科研议题、阶段与档案规范 |
| `docs/PFCI-MOD-5.0.1.md` | PFCI-MOD-5.0.1 模块深度模式与跨模块职责 |
| `docs/PFCI-HUMAN-5.0.1.md` | PFCI-HUMAN-5.0.1 深度讨论、迭代与决策规范 |
| `docs/PFCI-CARD-5.0.1.md` | PFCI-CARD-5.0.1 五类卡片与议题回写规范 |
| `docs/PFC_Interaction_5.0.1_技术报告_讨论深度强化修订版.md` | 5.0.1 目标架构、深度讨论与验收标准 |
| `docs/V501_PR_BREAKDOWN.md` | 5.0.1 升级 PR 台账 |
| `docs/V501_IMPLEMENTATION_STATUS.md` | 5.0.1 实现状态矩阵 |
| `docs/V501_ACCEPTANCE.md` | 5.0.1 验收记录（由 5.1 收口） |
| `docs/V510_PR_BREAKDOWN.md` | 5.1 收口 PR 台账 |
| `docs/V510_IMPLEMENTATION_STATUS.md` | 5.1 实现状态矩阵 |
| `docs/V510_ACCEPTANCE.md` | 5.1 全项验收记录 |
| `assets/v510_cards.html` | 五类卡片宿主渲染参考实现 |
| `docs/PFCI-ARCH-5.0.md` | 5.0 强制总体架构与工作流规范（历史基线） |
| `docs/PFCI-MOD-5.0.md` | PFCI-MOD-5.0 强制模块职责、接口与标定协议 |
| `docs/PFCI-HUMAN-5.0.md` | PFCI-HUMAN-5.0 强制讨论、双通道、决策与授权规范 |
| `docs/PFCI-CARD-5.0.md` | PFCI-CARD-5.0 强制提问卡片规范 |
| `docs/README_四规范总索引.md` | 四规范约束关系与冲突裁定 |
| `docs/PFC_Interaction_5.0_技术报告.md` | 5.0 目标架构、工作流与技术实施规格 |
| `docs/V50_PR_BREAKDOWN.md` | 升级 PR 拆分与执行台账 |
| `docs/V50_IMPLEMENTATION_STATUS.md` | 能力实现状态矩阵 |
| `docs/V50_ACCEPTANCE.md` | 验收范围、证据与未关闭项 |
| `references/architecture.md`、`interaction_protocol.md`、`reporting_policy.md` | 4.0 运行时语义，继续有效 |
| `references/decision_workflow.md`、`safety_rules.md`、`itasca_mcp_boundary.md` | 风险、边界与工具复用规则 |
| `references/module_contract.md` | 六模块 IF0 统一信封契约（4.0 兼容） |
| `docs/V40_CARD_SPEC_ACCEPTANCE.md` | 提问卡片 V2 既有验收 |

## 结构指引

- 运行时只需本 `SKILL.md` 与 `references/`；按需读取 `docs/` 中的规范。
- `core/`：4.0 IF0 运行时 + 5.0 五能力 + 5.0.1 议题/深度讨论/证据/变更/档案；`modules/`：4.0 专业模块 + 5.0 标定/交互/执行 + 5.0.1 五类卡片；`adapters/`：真实执行适配器。
- `tests/`：接口与协议验收；`examples/v50/`、`examples/v501/`：离线演练；`pr0/`：上游能力基线与 PoC。
- 维护者文档：`RELEASE.md`、`CHANGELOG.md`、`docs/IF0_接口冻结规范.md`。

## 版本兼容

5.0 新增 `core/v50_*.py` 与 `modules/v50_*.py`；5.0.1 新增 `core/v501_*.py` 与 `modules/v501_cards.py`；5.1 新增 `core/v510_*.py`（兼容导出/物理闸门）、`modules/v510_deep_modules.py` 与 `assets/v510_cards.html`。均不修改 4.0 接口与 v41 阶段门；既有回归继续通过。4.0 技术报告是六模块规格基线，5.0 四规范与 5.0.1 五份文件是目标约束；冲突裁定以 `docs/README_五份文件关系与使用说明.md` 为准。状态用语统一为：已实现 / 接口层通过 / 协议层通过 / 工具层在线通过 / 科学层机制比较通过 / 定量标定未通过。
