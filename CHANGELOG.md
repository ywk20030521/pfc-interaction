# PFC Interaction Skill — 变更日志

## 5.2.0（2026-11-27）— 参数识别与标定核心子系统（S4）

**定位：** 按《05_参数识别与标定核心子系统技术规范》V2.0，把参数标定建设为 S4 独立核心子系统（保留 S1–S6 与 M1–M6，不新增第七模块、不并入 M4），发布通用 5.2.0。

### 新增能力（新载体，不改 4.0/5.x 旧实现）

- `core/s4_contracts.py`：参数五分类、证据 E0–E5、关系六状态、参数六态、条件指纹与 12 类数据对象。
- `core/s4_relation.py`：五层宏观—细观关系分析引擎、关系知识库、静态映射表拒绝、局部敏感性 S_ij。
- `core/s4_identifiability.py`：可辨识性五问、等效解检测、耦合四问；不可辨识时拒绝盲目扩大搜索。
- `core/s4_negotiation.py`：逐参数七步协商、协商卡片（提交≠确认≠授权）、B 方案（独立档案+联合识别并行）。
- `core/s4_rules.py`：12 条高效率标定规则、三类规则优先级、PBM 示例映射（模型隔离）、E0–E5 经验库与反例否定。
- `core/s4_next_experiment.py`：下一步最优试算决策（信息增益/成本/不确定性/科学价值）；补偿关系触发"增加独立观测而非继续搜索"。
- `modules/s4_calibration.py`：C1–C8 编排门面，拟合/标定/独立验证三分，独立验证通过+科研判断方可冻结。
- `examples/v520/full_flow_walkthrough.py` + `outputs/v520_walkthrough/full_flow_report.json`：S1–S6 全流程 + M1–M6 + S4 的交互式实测走查（复用 5.1 真机 tool_task_id 回放），`FULL_FLOW_REPLAY_PASS`。
- `docs/V520_FULL_FLOW_EVALUATION.md`：八维能力综合评价（雷达图数据），含科学有效性边界说明。
- `docs/S4_SPEC.md`、`docs/V520_PR_BREAKDOWN.md`、`docs/V520_ACCEPTANCE.md`、`docs/V520_IMPLEMENTATION_STATUS.md`。

### 验收

- 新增 **49 条 S4 测试**全部通过；全量 **219 条**（170 旧 + 49 新）通过、0 失败（bridge 在线，含真实 tool_task_id 证据链）。
- 全流程走查 6/6 强制检查通过：D3 门槛、模块缺输入阻塞、静态映射拒绝、补偿→新增观测、拟合≠验证、回退带证据；3 个交互决策点用户判断与系统护栏一致。
- 三条不可降级原则均有强制测试守护；本版本是设计与协议闭环，不自动宣称材料参数定量标定成功（真实 PFC 与独立验证单独执行）。

## 5.1.0（2026-11-27）— 通用深度科研协作系统，全项收口

**定位：** 5.1 不是针对单一实验的补丁，而是整个 Skill 的通用升级：在 5.0/5.0.1 底座上关闭跨会话恢复、模式自动路由、M1–M6 深度包装、宿主 UI 参考实现与科学层围压闭环。

### 新增能力

- `core/v510_continuity.py`：从科研档案结构化 state 恢复议题树、证据与开放待办。
- `core/v510_routing.py`：按议题类型/状态/阶段自动推荐 8 种讨论模式。
- `modules/v510_deep_modules.py`：M1–M6 通用深度包装，门槛与模块输入双检查，输出 candidates/confidence/unresolved。
- `assets/v510_cards.html`：五类卡片渲染参考，支持折叠依据、窄屏、文字状态与暂缓/返回。
- `core/v510_physics.py`：围压控制与峰值声明分离的可复用物理闸门。
- `outputs/v510_acceptance/scripts/pfc_case_runner.py`：可复用三轴配方（force-x/force-y servo、velocity-max 1.0、gain-update 10、20 段采样）。

### 验收

- 全量 **170 条测试通过**（bridge 在线，0 跳过）。
- 三工况真实 PFC3D：69 个真实 tool_task_id；围压比 0.975–1.000，加载中漂移 ≤10%；C1 捕获峰后；H3 被否决、H2 获范围内支持、H1 仍 UNRESOLVED。
- `docs/V510_ACCEPTANCE.md`：宣布 5.1.0 在目标范围内通过；材料参数定量标定不在范围。

## 5.0.1（2026-11-27）— 深度科研讨论与科研连续性

**定位：** 按讨论深度强化修订版五份规范升级。核心对象从“问题”提升为“科研议题”；复杂议题必须经历 D0–D3 实质迭代、反方审查、用户修正、方案修订和验证计划。

### 新增能力

- `core/v501_issues.py`：ResearchIssue 类型/状态/优先级/依赖/重开/失效与待讨论队列。
- `core/v501_deep_discussion.py`：D0–D3 深度等级、8 种讨论模式、实质阶段门槛、用户修正与修订记录。
- `core/v501_evidence.py`：八类证据、假设登记与科研成熟度；USER_EXPERIENCE 不升格为事实，CONFIRMED ≠ VALIDATED。
- `core/v501_change.py` / `core/v501_archive.py`：变更影响、议题重开、决策失效与 15 类课题档案生成。
- `modules/v501_cards.py`：讨论收敛/参数登记/方案确认/执行授权/检查点决策五类卡片，绑定议题并通过深度门槛。
- 五份 5.0.1 规范与技术报告纳入 `docs/`；新增 PR 台账、实现状态与验收文档。

### 验收

- 新增 14 条 5.0.1 协议测试；全量 161 条通过（bridge 在线，0 跳过）。
- `examples/v501/complex_case_replay.py` 基于真实三轴案例回放：3 工况/21 个真实 tool_task_id、议题重开、假设 UNRESOLVED；报告标记 `V501_REPLAY_PASS`，科学层未通过。
- 真实复杂课题验收档案见 `outputs/v501_acceptance/`（13 轮 D3 讨论、科研档案、UNRESOLVED 结论）。

## 5.0.0（2026-11-27）— 科研工作流驱动 + Core 持续讨论

**定位**：在 4.0.0 六模块契约基础上升级到 5.0，新增 `core/v50_*` 与 `modules/v50_*` 实现载体；保留 4.0 接口与 v41 阶段门，既有回归不破坏。

### 新增能力

- 统一科研上下文与状态模型（`core/v50_context.py`）：S1–S6、阶段/模块状态分离、六类证据、参数/决策/交互记录、context 版本与 provenance。
- 讨论与方案建议（`core/v50_discussion.py`）：先理解分析后追问、备选方案 pros/cons/适用条件/依据、按完成条件推进、阶段总结；新增 `gate_for_card()` 内容维度深度门槛，接入卡片准备后浅讨论不得结构化。
- 决策与授权（`core/v50_decisions.py`）：PROPOSED→DISCUSSING→CONFIRMED 等状态、高影响操作授权绑定、版本变化失效、Native Chat/AUQ 事项去重与回退。
- 工作流编排（`core/v50_workflow.py`）：阶段主线推进、按需模块计划、产物审核、回退证据与影响分析。
- 跨模块参数标定（`modules/v50_calibration.py`）：M2–M6 分工、真实 tool_task_id 门槛、逐版本误差与接受标准、迭代上限、敏感性与非唯一性提示。
- 卡片交互适配（`modules/v50_interaction.py`）：复用 04 规范卡片校验、单卡单决策/最多三卡、提交回写与 Agent 反馈、执行卡单独授权。
- 真实执行载体（`modules/v50_execution.py`）：4.0 Envelope→5.0 `module_result` 转换、按需模块总线、Core 授权绑定的 bridge 网关（桥离线/无授权一律 BLOCKED，不伪造 ID）。
- 四份强制规范与 5.0 技术报告纳入 `docs/`；新增 `V50_PR_BREAKDOWN.md`、`V50_IMPLEMENTATION_STATUS.md`、`V50_ACCEPTANCE.md`。

### 验收

- 新增 36 条 5.0 离线协议测试 + 6 条执行载体验收 + 7 条讨论深度门槛测试；全量 147 条测试通过（bridge 在线，0 跳过）。
- `examples/v50/full_stage_walkthrough.py` 完成六阶段 + 标定迭代 + 证据回退的离线回放，报告标记 `OFFLINE_REPLAY_PASS`。
- **bridge 在线补验**：PFC2D 与 PFC3D Console + bridge 0.6.17 均通过；`tests/test_v40_tooling.py` 3 条真实通过；`examples/v50/real_bridge_execution.py` 通过 Core 授权网关取得真实 `tool_task_id`，S4 标定协议链 `REAL_BRIDGE_PASS`（3D 报告 `dimension=3D`）；修复 FISH 块回归用例中的 2D 硬编码，使其自动适配 2D/3D。
- 三轴压缩交互验证：初版讨论粒度不足，重划为 11 个子阶段并补上 S2c 观测指标决策；用户确认采用峰值强度+峰值应变+E50；报告 `outputs/v50_interaction_validation/triaxial_interaction_report.md`（修订版）。
- 科学有效性验证（围压维持、胶结保留率、峰后采样）与宿主 UI 视觉仍未关闭。

## 0.1.0（2026-11-25）— 首个试用版

**定位**：从 V3.1 架构方案落地的可运行 Skill，核心协作闭环经真实 PFC 环境验证。状态为"可试用"，不宣称全部验收通过。

### 架构

- 采用 V3.1 收敛方案：三方、两条通道、一个 Agent 中心；
- 冻结 ADR-001～005（Skill 优先、复用 itasca-mcp、Native Chat + AUQ 双通道、Agent 为唯一语义中心、MCP/Web 条件性增强）；
- 从 V0.x 保留三条安全原则：阶段级检查点、证据分级、高风险操作单独确认。

### 交付内容

- `SKILL.md` + 10 份 `references/`：架构、交互协议、汇报策略、决策流程、安全规则、工具边界、主动协作、通道路由、AUQ 集成、实验示例；
- 3 份 `templates/`：状态汇报、参数协商、异常报告；
- `pr0/`：itasca-mcp / 宿主 / AUQ 三份能力基线 + PoC 脚本；
- `examples/`：E2E 验收报告、完整物理 E2E 报告、阶段脚本、验收清单。

### 实测验证

- PFC2D / PFC3D Console 的 T1–T8 全部通过（itasca-mcp 0.8.1 / bridge 0.6.11）；
- E2E 核心协作闭环：2 次检查点决策 + 1 次异常修正重跑 + 决策→执行→PFC 状态证据链；
- 完整物理 E2E：3 次基于数据质量的协作决策（详见报告）；
- AUQ 3.4.0（npm）异步往返 A1–A5 通过。

### 关键修正（相对四份技术报告）

1. AUQ 是 **npm 包 `auq-mcp-server`**，非 Python 包；
2. 上游工具名随版本变化，改为能力探测 + 显式版本传参；
3. Console 模式下用户直接输入不可观察（源码定论）；
4. 新增桥接、接触模型、PFC2D/3D 维度差异等一手建模知识。

### 已知限制

- GUI 动态验证（G1–G6）待人工执行；
- AUQ MCP 工具宿主集成（A6/A8）待会话重启验证；
- 跨实验类型通用性证据有限；
- 有效应力-应变曲线因实验几何标定未得到（非 Skill 缺陷）。

### 版本基线

| 组件 | 版本 |
|---|---|
| itasca-mcp | 0.8.1 |
| itasca-mcp-bridge | 0.6.11 |
| AUQ | 3.4.0（npm） |
| PFC | PFC900 Console（2D/3D 已验，GUI 未验） |

---

## 0.1.0-rev1（2026-11-25）— 收尾复审修正（文档修订，功能不变）

依据第二轮复审意见修正状态表述与协议细节，**不新增功能**：

1. **状态分层**：区分"实测通过 / 设计通过 / 阻塞已确认"。项目状态定为**可受控试用**。A6（双通道运行时去重）、A8（AUQ 宿主集成）、GUI 动态验证、完整物理曲线独立验证均明确标为**未通过**。
2. **回归案例**：完整物理 E2E 定名为 `E2E_DATA_QUALITY_AND_DECISION_RECOVERY`，验收重点为 6 项数据质量与决策恢复能力，与"是否得到漂亮曲线"无关。
3. **诊断定性**：颗粒扩散 ±2.0 的几何解释改为**待复核的技术诊断**，不作为已证明物理根因。
4. **去重协议强化**：事项键增加 `context_version`；增加 `delivery_status`（7 态）；"换通道先撤销"改为 `SUPERSEDED` 标记 + 保留关联记录（Chat 消息未必可撤回）。
5. **文档一致性**：V3.2 与 SKILL.md 的去重表述对齐，设计文档不定义运行时细节。

## 0.1.0-rev2（2026-11-25）— 架构图实践检测（文档修订，功能不变）

1. **架构目标实践检测**：对照 `核心技术框架.png` 做真实工具调用检测，6 要素（Human 层、人↔Agent 通道、Agent 中心、Agent↔PFC 双向通道、PFC 引擎层、三方协作闭环）全部有实证，报告见 `examples/ARCHITECTURE_PRACTICAL_CHECK.md`。结论：核心架构目标实现；仍为可受控试用。
2. **A8 分层**：工具层实测通过（MCP stdio `tools/list` + nonBlocking 异步往返全通过），宿主会话层未通过（ToolSearch 无结果）。schema 修正：`nonBlocking` 默认 false；CLI `answer` 只接受完整 UUID。
3. **物理曲线独立验证**：开始但未完成（`examples/_dev/calibration_circle_wall_stress.py`），复审明确为独立标定任务，不混入 Skill 开发。

## 0.1.0-rev3（2026-11-25）— 复杂实验指导（文档补充，功能不变）

1. 新增 `references/complex_experiment.md`：基于工作区已有的 4–11 阶段实验范式，说明阶段化拆解、检查点协作、长任务状态访问、多实验隔离、数据质量把关与 2D/3D 差异。
2. 修正 GUI 验证文档中过时的 PID 引用（改为动态查询方式）。

## 4.0.0（2026-11-25，架构升级）

按用户决策，4.0 是现有 PFC Interaction Skill 的架构升级，**不新建第二个 Skill**。执行 PR-A 迁移 → PR-B 接口统一 → PR-C 真实适配器 → PR-D 第二批模块 → PR-E 验收发布。

1. **合并迁移**：4.0 的 `core/`、`modules/`、`tests/`、`examples/v4/` 迁入唯一目录 `pfc-interaction/`；既有 43 文件全部保留；SKILL.md 升 `version: 4.0.0`，description 增补六模块能力。
2. **接口统一**：新增 `references/module_contract.md`，明确"语义在 references、机器枚举在 core"；IF0 与 interaction_protocol / decision_workflow / reporting_policy / interaction_transport_policy 建立引用，消除双套定义。修复去重漏洞（UNDELIVERED 事项键占用）。
3. **真实适配器**：新增 `adapters/itasca_mcp.py`，Core I5 映射到 bridge HTTP API（`execute_code` / `execute_task` / `check_task_status`），支持 `.dat` 脚本包装；`task_state` 只认工具返回。实测 bridge 0.6.11 通过。
4. **六模块**：第一批 M1/M2/M3 + 第二批 M4/M5/M6 全部实现；M4 检查点经 Core 交互、M5 分层诊断且推断不能作 confirmed、M6 质量闸门失败阻止结论。
5. **验收**：接口用例 32 条（19+13）全通过；六模块流水线经真实 PFC2D bridge 跑通（59–60 球成样，真实 tool_task_id）；未通过项 A6/A8 宿主层/GUI/完整曲线状态不变。

## 4.0.1（2026-11-26，缺陷修订版）

依据 `V4_INDEPENDENT_REVIEW.md` 独立技术审查与上游 issue #250 的维护者回复，修复三项已实证缺陷：

1. **适配器 `.dat` 执行（P0）**：删除自造的逐行 `itasca.command` 拆分。根因——单独发送 `fish define NAME` 会让 PFC 进入交互 FISH 提示，C 调用持有 GIL 等待函数体，冻结进程内所有 Python 线程（含 `/health` 与超时处理），bridge 永久失联。改为把整个 `.dat` 脚本作为一个 `itasca.command(<string>)` 传入，由 bridge 原生 `preprocess_source` 拆分（保持 FISH 块完整、处理续行与注释）。实测含两个 FISH 块的脚本 2.5 s 完成、bridge 健康。
2. **M6 证据闸门（P0）**：新增 `EvidenceSource.INVALID_EVIDENCE`；缺 `tool_task_id` 的 `pfc-*` 引用不再降级为推断，而是标无效、质量闸门 FAIL、结论强度强制降为 hypothesis、模块 BLOCKED。合法 PFC 证据（带 tool_task_id）仍可 COMPLETED/confirmed。
3. **去重状态语义（P1）**：`REJECTED` 由 `delivery_status=ANSWERED` 改为 `CANCELLED` 并保留 `resolution=REJECTED`；同步修复 `check_duplicate`——被拒事项同一 context 不得重投，新 context 可重新发起。
4. **回归**：新增 `tests/test_v401_regressions.py`（6 条，含真实 bridge FISH 测试）；32 条既有用例 + 6 条新用例全部通过。

**上游 issue 定性澄清**：issue #250 最初报为"上游 bug"，维护者澄清为引擎持有 GIL 的设计约束 + 客户端误用，bridge 自 0.4.4 起已有正确的 FISH 块保持机制。已在 issue 中明确纠正并请关闭。**保留过程记录但不改变最终定性**。

## 整体验收尝试（2026-11-26）

按用户要求推进整体验收，产出 `FINAL_ACCEPTANCE_2026_11_26.md`：

1. **A8**：配置与包均正确、协议层工具清单实测通过，但当前会话仍查不到 AUQ 工具——宿主层阻塞已确认，需重启/信任，未在会话内闭合。
2. **A6**：新增 `tests/test_a6_dual_channel.py`（5 条，对接真实 AUQ server），协议/接口层实测通过；`DecisionItem` 新增 `channel` 字段记录投递通道。宿主运行时验证仍待 A8 关闭后做。
3. **GUI**：exe 存在、步骤文档修正硬编码 PID；动态 G1–G6 需人工在 IPython 启动，未执行。
4. **完整物理曲线**：8 次真实 PFC 实验。关键根因定位——此前曲线无效是因 `bonded=0`（未真正成键）；按 brazil-pfc 正确流程修正后 `bonded=5268`。但曲线仍不可信（峰值在极小应变、应力单调下降），待复核诊断不写成物理结论。实证回写 `references/itasca_mcp_boundary.md` §3.2，追加报告 `examples/FULL_UCS_PHYSICAL_REVIEW.md`。
5. **全量回归**：19+13+6+5=43 条用例通过。

**结论：4.0 整体验收仍未通过**；A8/A6 运行时/GUI/物理曲线按分层状态如实记录。

## 2026-11-26 晚 · 目录清理（v4.0.1 内容不变）

- 按用户要求保留最新版、删除旧版与中间产物：删除 `v0.1.0.zip`、`v4.0.0.zip`、`pfc-interaction/work/`、`examples/_dev/`、两个 `PFC Interaction 4.0/` 独立目录。
- 4.0 六份核心设计档案（技术报告 / IF0 规范 / 可组合性用例 / 架构升级规划 / 基线登记 / 第一批验收）迁入 `pfc-interaction/docs/` 保留追溯；断裂引用已修正指向 `docs/`。
- 清理前完整快照保存在 `.workbuddy/cleanup_snapshot_20261126.zip`（242 文件，可恢复）。
- 保留：最新版 `pfc-interaction-v4.0.1.zip` + `pfc-interaction/` 源目录 + 上游源码克隆（itasca-mcp-main / ask-user-questions-mcp-master）。
- 本轮为目录清理，功能与代码无变化，版本号仍为 4.0.1。

## 4.0.1-rev1（2026-11-26 晚）— GUI 动态验证关闭（文档修订，功能不变）

由用户启动 PFC3D GUI（PID 28488）并在 IPython 执行 `itasca_mcp_bridge.start()`，bridge 0.6.17 / runtime_mode=gui：

1. **G1–G6 全部实测通过**：G1 gui；G2 捕获用户输入 `print('GUI_VERIFY_20261126')`；G3 Plot01/data_file 视图跟踪；G4 游标 64→65 不重放；G5 `state.unsaved=["new"]`；G6 dialog open/closed 配对。报告 `examples/GUI_DYNAMIC_ACCEPTANCE.md`。
2. **版本机制修正（重要）**：0.6.17 上下文从"执行响应附加 `_context`"改为"独立 `console_history` HTTP 端点拉取"（`data.entries[]` + `cursor` + `state.unsaved`）；MCP 工具层未暴露该命令，需走 bridge HTTP。同步修正 `itasca_mcp_boundary.md`、`active_collaboration.md`、`complex_experiment.md`、`reporting_policy.md`、`safety_rules.md` 五份文档。
3. **PFC2D GUI 交叉验证**：用户随后启动 PFC2D GUI（PID 14288），同一 bridge 0.6.17 上确认 gui 模式 / console_history / 2D 建模执行（`vec2`）通过；补充 API 差异——GUI 内 `itasca` 无 `dimension()`/`vec2` 构造器，维度判定用 `ball.pos()` 类型。
4. **状态更新**：GUI 动态从"阻塞已确认/未通过"改为"实测通过（双 GUI）"；`FINAL_ACCEPTANCE_2026_11_26.md`、`PR_STATUS.md`、`RELEASE.md` 同步。未通过清单现剩 A8 宿主层、A6 宿主运行时、完整物理曲线、4.0 整体验收。

## 4.0.0（2026-11-26）— 技术报告完整实现

按 `docs/PFC_Interaction_4.0_技术报告.md` 的完整范围实现，超越 4.0.1 的接口骨架：

1. **Core**：新增 `core/gates.py`（不可伪造批准账本、阶段门、物理准入）、`V41CoreDispatcher`（dispatch 前强制门）、7 类交互事件 `InteractionEventType`、四模块回退 `WorkflowOrchestrator`（M5→M3、M6→M4/M2、→M1）。
2. **M1**（`v40_design.py`）：9 项功能 + 5 标准输出（research_question/plan/hypotheses/workflow/requirements）。
3. **M2**（`v40_design.py`）：9 项功能 + 5 标准输出（experiment_design/matrix.csv/control_groups/measurement_plan/parameter_schema）；8 种实验类型知识库 `experiment_knowledge.py`。
4. **M3**（`v40_modeling_full.py`）：12 项功能，生成真实 `.dat` 命令脚本（非 JSON），语法/结构/物理三层检查，5 标准输出。
5. **M4**（`v40_runner_full.py`）：10 项功能，多工况/检查点/恢复/版本化证据，6 标准输出；无真实 tool_task_id 一律 BLOCKED。
6. **M5/M6**（`v40_analysis_full.py`）：五层诊断 10 功能 + 5 输出；13 项分析功能 + 6 输出；自动读 CSV 计算，峰后在末点禁止峰值结论。
7. **验收**：`tests/test_v40_full.py` 19 条五层验收全过；合计 73 条（72 通过 1 skip）；完整案例 `examples/v40/full_research_loop.py` 含 M6→M4 跨模块迭代；结论 `V40_FULL_ACCEPTANCE.md`。

**五层验收**：功能✅ 工程✅ 协作✅；工具❌（桥离线）、科学❌（物理未标定）——不宣称 4.0 整体验收通过。

## 4.0.0-rev1（2026-11-26）— 提问面板与内容质量改进

按用户反馈（参考 nature-skills-main 的实验设计评价 + PFC 官方手册 + 面板形式）改进 M1/M2 提问：

1. **结构化提问** `core/question.py`：Question/Option 数据类，带 why/unit/group/progress/allow_free_text/author_input_needed；`display_prompt()` 把背景、单位、依据、默认值折叠进面板文本；选项带单位/来源/依据。兼容原 question_set 结构。
2. **Nature 实验设计评审**（M2 第4轮）：`modules/nature_experiment_design.py` 从 nature-statistics 引入对照组、独立实验单元与技术重复、随机化/盲法、效应量口径四类提问；`design_review()` 给 P0/P1/P2 建议，缺失标 AUTHOR_INPUT_NEEDED，不编造 n。仅实验设计评价，不引入事后可视化/分析。
3. **PFC 手册依据**：从本机 PFC9 手册提取 ball generate（无重叠）vs ball distribute（不检查重叠直到目标孔隙率）的语义，作为成样方式选项的 basis 落盘，对应 B03 根因。
4. **面板四项要求**：先给背景、自由输入、分组+进度、选项带单位/默认值/依据——全部实现。
5. **验收**：新增 `tests/test_v40_question_quality.py` 6 条全过；M2 从 3 轮变 4 轮，76+6=82 条回归全过；自动/手动走查均完成；文档 `docs/V40_QUESTION_PANEL_DESIGN.md`。

### 4.0.0-rev2（面板实测反馈修正）

- 面板主问题简化：去掉 "(分组)"、"为什么问"、"依据" 前缀，背景改由 Agent 在面板前用文字说明；结构化信息只留 question_meta 供审计。
- 重复次数问法改为 PFC 专属：不问生物学独立单元/技术重复，改问 "同一工况做几次独立重复？用什么方式产生差异？"（不同随机种子/初始装配）。
- 再次面板实测：四题均简洁主问题 + 选项说明，用户全选推荐项，回放 M1→M6 通过。

## 4.0.0-rev4（2026-11-26）— 面板对照标准图修正

按用户对照规范截图的反馈：panel_prompt 末尾独立"建议"段落（不再塞进选项）；选项说明只留物理意义，来源/单位/理由移入 question_meta；自由输入项改为"其他变量 / 由用户补充研究因素"；header 改为"阶段·卡片类型"，P1 参数卡显示"关键决策"。状态徽章属宿主能力边界，status=pending 已写入 meta。修正后真实面板实测两卡均选推荐项；98 条测试通过。

## 4.0.0-rev5（2026-11-26）— 内容·逻辑·形式融合

按用户连续澄清：卡片形式照录报告图片（A 科研讨论/B 参数决策/C 执行确认），同一类型可出 N 张直到实验完成，卡片顺序严格跟随模型 M1→M6。

1. `modules/card_templates.py`：固化图片三类卡片的标题/说明/适用原文，作为形式单一真相源。
2. `modules/card_sequence.py`：28 张卡按 M1(9)→M2(14)→M3(1)→M4(2)→M5(1)→M6(1) 排列，阶段内 A→B→C；`validate_sequence()` 校验无倒退。
3. `modules/v41_interview.py`（实际入口）：M1 两轮、M2 四轮问组改为 `_a_card/_b_card/_c_card` 引用模板；M1/M2 确认改为 C 执行确认卡（动作/对象/影响+明确确认）。保留全部答案 id 与 topic，阶段门逻辑不变。
4. 验证：98 条测试通过（4 skip 桥离线），v41 纵向切片、v40 自动走查均通过；验收并入 `docs/V40_CARD_SPEC_ACCEPTANCE.md` §0。

## 4.0.0-rev3（2026-11-26）— 提问卡片强制规范 V2

按用户提供的 `PFC_Interaction_提问卡片强制设计规范_V2.md`（第6、12章 MUST）实现：

1. **规范数据结构** `core/question.py`：CardType(DISCUSSION/PARAMETER/EXECUTION)、CardStatus 12态、QuestionPriority P0-P4、规范 Question/Decision 对象、dedup_key、validate_card 强制自检12项。
2. **三类卡片工厂** `modules/question_cards.py`：discussion_card/parameter_card/execution_card + decision_summary + card_from_question_set；执行卡无静默延后、无默认勾选。
3. **面板渲染**：header 放阶段标签，主问题=标题+一句话说明（符合用户此前反馈），技术依据放选项说明/question_meta。
4. **状态机**：Decision.confirm/authorize/mark_executed/mark_verified 严格区分 answered≠confirmed≠authorized≠executed≠verified。
5. **验收**：新增 `tests/test_v40_card_spec.py` 16条（规范12.4最低测试集8项+状态机+MUST）；全量98条通过；三张卡真实面板实测；报告 `docs/V40_CARD_SPEC_ACCEPTANCE.md`。

## 4.1.0-alpha（2026-11-26）— 三轴纵向切片（实现，非发布版）

依据对 4.0.1 的独立评审（"文档/脚本 ≠ 科研协作"），新增三轴纵向闭环骨架，不替换 4.0 默认流水线：

1. **Core 阶段门**：`core/gates.py` 新增 `ApprovalLedger`（只能由 `resolve_decision()` 写入，绑定 decision_id/context_version/answers_hash/channel）、`check_stage_gate`、`check_physics_gate`、`check_peak_capture`；`V41CoreDispatcher.dispatch()` 在 runner 前强制校验，未满足返回 BLOCKED。`full_pipeline_e2e.py` 式合成授权在 4.1 无效。
2. **M1/M2 多轮协商**（`modules/v41_interview.py`）：M1 三轮（对象/目标/围压来源 → 假设/变量/控制/交付 → 确认）；M2 四轮覆盖 13 类三轴字段，每字段记 unit/source/confirmed/default/missing_risk；不自动填入围压、粒径、接触模型或速率。
3. **M3 阶段化模型**（`modules/v41_modeling.py`）：8 阶段独立检查，围压/胶结/越界/重叠/墙间隙/时步/峰后逐项判定；失败即停留并进入 M5 诊断。
4. **M4 真实运行器**（`modules/v41_runner.py`）：仅经 Core I5 提交，保存真实 tool_task_id；桥离线或物理准入失败返回 BLOCKED；重跑版本化不覆盖旧证据。
5. **M5/M6 自动证据**（`modules/v41_analysis.py`）：自动读取真实 CSV/summary 计算峰值、峰值应变、E50、残余强度；峰后在末点或无 tool_task_id 时质量闸门 FAIL，拒绝 payload 预整理结论。
6. **验收**：新增 `tests/test_v41_stage_gates.py` 11 条全过；4.0 回归 43 条不变（42 通过 1 跳过，桥离线）；`examples/v41/triaxial_longitudinal_slice.py` 用 2026-11-26 真实数据回放跑通；报告 `outputs/v41_alpha/triaxial_slice_report.json`；分层结论 `V41_ACCEPTANCE.md`。

**未关闭**：真实 bridge 在线执行、C2/C3 峰后重采、细观参数标定、完整三轴曲线。不得作为正式发布版。

## 规划中（未实现）

- GUI 模式动态验证、AUQ 宿主集成验证（A6/A8）、跨实验类型验收矩阵；
- 完整应力-应变曲线独立标定（与 Skill 功能开发分离）；
- PR5 Web：仅当 Chat 无法满足独立监控/多实验视图需求时触发。
