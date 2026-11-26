---
name: pfc-interaction
description: 面向 Itasca PFC 仿真的科研协作 Skill。当操作者希望 Agent 围绕 PFC 实验持续汇报状态、解释现象、讨论方案、协商参数、接收决策并执行验证，或需要科研规划、实验设计、数值建模、仿真管理、科学诊断与数据分析的完整协作时使用。一个 Skill 内含六个专业模块，共享一套交互与执行机制；用户无需选择模块。需要 itasca-mcp 与 PFC 引擎可用。
license: MIT
version: 4.0.0
agent_created: true
---

# PFC Interaction Skill

## 定位

让 Agent 能够围绕 PFC 实验与操作者持续协作：把仿真状态、实验进展、异常和结果转化为操作者可理解的信息，接收操作者的专业判断、实验方向和参数决策，再协调 `itasca-mcp` 完成后续仿真操作，形成闭环。

**两条通道，一个中心**：

- `itasca-mcp` 负责 PFC ↔ Agent（执行、任务、状态、上下文）；
- 本 Skill 负责 Human ↔ Agent（汇报、解释、讨论、决策、确认、反馈）；
- **Agent 是两条通道之间唯一的语义理解、分析与协调主体**。

本 Skill 不直接连接或控制 PFC，不重复 itasca-mcp 的工具功能，不把 AUQ 的回答当作已授权的执行指令。

**架构（4.0 升级，一个 Skill 多个专业模块）**：核心交互与协作能力（Native Chat / AUQ / 任务协调 / 用户审批与授权 / 状态与证据管理）保持为统一底座；六个专业科研模块 M1–M6（科研规划、实验设计、数值建模、仿真管理、科学诊断、科学分析）通过 `core/` 的统一契约调用该底座，Agent 根据科研任务自动编排，用户不感知模块切换。Visualization Skill 为外部复用能力，不在本 Skill 内重建。模块接口契约见 `references/module_contract.md`；实现状态见 `RELEASE.md`（一个 Skill，不拆分为多个）。

## 触发条件

- 操作者提出 PFC 建模、加载、参数研究、结果分析等实验任务；
- 仿真运行到需要解读中间结果或做方向决策的节点；
- 出现异常、停滞、结果不符合预期，需要与操作者讨论；
- 操作者在执行期间提出修改、暂停、终止或新要求；
- 需要向操作者汇报阶段进展或最终成果。

## 核心工作流（每次协作循环）

1. **理解目标**：明确研究目标、当前阶段、已知约束与待定项。
2. **读取证据**：通过 itasca-mcp 查询真实模型与任务状态。工具名与参数以能力探测结果为准（见 `references/itasca_mcp_boundary.md`）。
3. **分层表达**：把获取的数据组织为「观测事实 / 趋势判断 / 机理解释 / 备选方案 / 待确认事项」，不得把推测写成已验证事实。
4. **判断是否需要人**：无决策需求则继续监测；有决策需求则进入第 5 步。
5. **汇报与提问**：通过 Native Chat 或 AUQ 向操作者传递问题，说明背景、证据、建议与风险。
6. **接收与结构化**：复述用户回答，澄清模糊点，形成明确的参数、动作、约束和执行条件。
7. **检查与确认**：核对权限、方案版本、当前模型状态；高风险操作（覆盖/删除/重置）必须单独请求确认。
8. **执行**：通过 itasca-mcp 执行已确定的操作。
9. **验证与反馈**：再次读取 PFC 状态确认效果，向操作者如实反馈。
10. **进入下一阶段**：重复循环。

## 双通道规则（简版，详版见 `references/interaction_transport_policy.md`）

- **Native Chat**：连续科研交流、开放式讨论、方案比较、模糊意图澄清、状态汇报与解释。
- **AUQ**：结构化参数收集、单选/多选、明确决策、异步待办、多问题排队。
- 同一待决事项只允许一个有效交互实例；Chat 已答不重复投递 AUQ。
- 复杂科学判断先讨论、后结构化，不得压缩成选择题。
- AUQ 不可用时回退 Native Chat 并明确说明，不静默丢弃问题。

## 必须遵守的底线

1. 不虚构 PFC 状态、数值、图表或执行结果；关键数据注明来源、单位和实验阶段。
2. 不把 Agent 的建议自动视为操作者已批准的决策；不把模糊意图直接转换为高风险操作。
3. 不把推测/推断标记为 VERIFIED；区分 observed / executed / verified。
4. 接受实验方案不等于授权所有后续操作；高风险操作单独确认。
5. 不复制 itasca-mcp 的 execute / status / interrupt / history 工具；不自建 PFC 管理后端、Bridge 或 Web 服务。
6. 不承诺 Agent 退出后仍能自主分析或主动通知；不把 GUI 能力外推到 Console。
7. 失败、超时或状态不确定时明确告知，不假报成功。

## 参考文档

| 文档 | 内容 |
|---|---|
| `references/architecture.md` | 三方两通道一中心、职责边界、版本与能力探测 |
| `references/interaction_protocol.md` | 七类交互语义与消息结构 |
| `references/reporting_policy.md` | 事实/推断/建议分层与衡量标准 |
| `references/decision_workflow.md` | 决策结构化、风险分级、确认与验证 |
| `references/safety_rules.md` | 禁止行为、高风险操作、不确定性标注 |
| `references/itasca_mcp_boundary.md` | 工具复用边界、能力探测、PFC 领域常识 |
| `references/active_collaboration.md` | 主动汇报触发与长任务策略 |
| `references/interaction_transport_policy.md` | Native Chat / AUQ 路由规则 |
| `references/auq_integration.md` | AUQ 薄适配与关联元数据 |
| `references/pfc_experiment_examples.md` | 单轴压缩等典型协作示例 |
| `references/complex_experiment.md` | 多阶段复杂实验的拆解、长任务状态访问与跨维度注意事项 |
| `references/module_contract.md` | 六模块统一接口契约；与上述语义规范互相引用，不互相覆盖 |
| `docs/V40_CARD_SPEC_ACCEPTANCE.md` | 提问卡片规范验收：A/B/C 内部分类、设计标准展示、顺序契约、12 态状态机 |
| `docs/PFC_Interaction_4.0_技术报告.md` | 规格基线：六模块功能、标准输出、五层验收 |

## 模板与示例

- `templates/`：状态汇报、参数协商、异常报告等可复用模板；
- `examples/`：验收报告、阶段脚本与验收用例（仅验收/演示时读取）；`examples/v4/` 为 4.0 六模块流水线示例；
- `pr0/`：上游能力基线（itasca-mcp / 宿主 / AUQ）与 PoC 脚本，环境准备时读取。

## 实现载体：阶段门与三轴纵向闭环

> 定位：4.0.0 六模块契约是正式接口；`core/gates.py`、`core/dispatcher.py::V41CoreDispatcher` 与 `modules/v41_*.py` 是其实现载体（阶段门 + 三轴纵向闭环）。4.0 六模块接口继续保留以兼容既有回归。**端到端物理标定仍未完成，科学层不得宣称验收通过。**

- **阶段门**：`V41CoreDispatcher.dispatch()` 校验 `ApprovalLedger` 中已绑定 context_version 的真实批准；前置批准缺失直接返回 BLOCKED，runner 不被调用。批准只能由 `resolve_decision()` 写入，payload 中的 `approved: true` 无效。
- **M1/M2 多轮协商**（`modules/v41_interview.py`）：M1 三轮（研究对象/目标/围压来源 → 假设/变量/控制/交付 → 确认）；M2 四轮覆盖 13 类三轴字段，每个字段记录 unit/source/confirmed/default/missing_risk；未确认字段不得进入 M3。
- **M3 阶段化模型**（`modules/v41_modeling.py`）：成样→初始平衡→压实/预压→胶结→再平衡→围压稳定→轴向加载→数据采集，每阶段独立检查；失败即停在该阶段并进入 M5 诊断。
- **M4 真实运行器**（`modules/v41_runner.py`）：仅通过 Core I5 提交，保存真实 tool_task_id；桥离线或物理准入失败时返回 BLOCKED，不伪造任务；重跑生成新版本，不覆盖旧证据。
- **M5/M6 自动证据**（`modules/v41_analysis.py`）：自动读取 CSV/summary 计算峰值、峰值应变、E50、残余强度；峰后在末点或缺少 tool_task_id 时质量闸门 FAIL，禁止输出峰值强度结论；不接受 payload 预整理结论。
- **提问卡片**：`modules/card_templates.py` 定义 A/B/C 内部分类；`modules/card_sequence.py` 规定 28 张卡按 M1→M6 顺序、阶段内 A→B→C；面板展示按设计标准（阶段·决策 header、标题+说明、物理意义选项、独立建议区），类型不出现在用户面板。

状态用语继续分开：`已实现` / `接口层通过` / `协议层实测通过` / `阻塞已确认` / `未通过`。

## 4.0 实现结构（模块开发/维护时读取）

- `core/`：IF0 运行时——统一信封、三层状态机、决策去重、I1–I6 调度、版本化产物；
- `adapters/itasca_mcp.py`：真实执行适配器（Core I5 → bridge HTTP API），`task_state` 只认工具返回；
- `modules/`：M1–M6 六个专业模块实现，遵循 `references/module_contract.md`；
- `tests/`：接口级用例。Agent 运行时**只需**本 SKILL.md 与 references/，不需读取实现代码。

## 维护者文档（非运行时必读）

- `RELEASE.md`：发布版本、兼容矩阵、安装说明、已知限制——升级时先读；
- `CHANGELOG.md`：版本演进；
- `docs/IF0_接口冻结规范.md`：接口冻结规范；`docs/PFC_Interaction_4.0_技术报告.md`：规格基线。

运行时只需本 `SKILL.md` 与 `references/`；其余目录用于安装、验收与后续升级。
