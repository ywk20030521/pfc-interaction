# 模块接口契约（4.0 / IF0-1.0.0）

**性质：** 六模块（M1–M6）与 Core 之间的**唯一运行时契约**。
**与其他规范的关系（重要）：** 本文件定义**机器可校验的字段与格式**；语义规则继续以既有 references 为准：

| 语义主题 | 权威文档 | 本文件如何引用 |
|---|---|---|
| 七类交互语义、消息结构 | `interaction_protocol.md` | I3/I4 的字段顺序与之一致 |
| 事实/推断/建议分层、数据可信度 | `reporting_policy.md` | §4 证据五类枚举与其五层表达对齐 |
| 决策形成、风险分级、Execution Gate | `decision_workflow.md` | §3 批准≠执行沿用其 Gate 逻辑 |
| 通道路由、四字段事项键、SUPERSEDED | `interaction_transport_policy.md` | I3 直接复用，不重新定义 |
| 工具边界、能力探测、PFC 常识 | `itasca_mcp_boundary.md` | I5 真实适配器实现依据 |
| 主动协作、检查点 | `active_collaboration.md` | M4 检查点复用 |

**原则：** 语义文档在 references，机器枚举在 `core/contract.py`；两者互相引用，**不互相覆盖**。不得出现两套"批准状态"或"证据等级"定义。

---

## 1. 统一信封（所有模块 I2 返回）

字段来自 IF0 §4.1，实现于 `core/contract.py::Envelope`：

| 字段 | 说明 |
|---|---|
| `contract_version` | 固定 `IF0-1.0.0`；不匹配拒绝派发（C01） |
| `module_id` / `module_version` | 模块标识 |
| `research_task_id` / `module_task_id` / `parent_task_id` | 任务链，回退时新建子任务 |
| `input_refs` | `artifact_id + version + hash`，不允许"最新文件"模糊引用（C02） |
| `preconditions` / `status` / `output` | 前置条件、状态、结构化输出与产物 |
| `evidence` | 每项必须标注五类来源之一（§4） |
| `decisions` / `limitations` | 关联决策事项与已知限制 |

模块**不得**在 Result 中声明 `verified_by_execution=True`——只有 Core I5 拿到真实 `tool_task_id` 才能回填（C04）。

## 2. 六个接口

| 接口 | 方向 | Core 实现 |
|---|---|---|
| I1 Dispatch | Core → Module | `CoreDispatcher.dispatch()` |
| I2 Result | Module → Core | `CoreDispatcher.accept_result()` |
| I3 DecisionRequest | Module → Core → 用户 | `request_decision()`；走 `interaction_transport_policy.md` 四字段事项键 |
| I4 DecisionResolution | Core → Module | `resolve_decision()`；`APPROVED` 必须绑定 `context_version` |
| I5 Execution | Module ↔ Core ↔ itasca-mcp | `execute()` + `adapters/itasca_mcp.py` |
| I6 Iteration | Module → Core → 目标模块 | `iterate()`；新建子任务、假设变更需重新授权 |

**三条硬边界**：交互唯一入口（Core）、执行唯一通道（Core→adapter）、状态单一写入者（交互态/模块态 Core 写，执行态只认工具返回）。

## 3. 三层状态（实现于 `core/state_machine.py`）

三层正交、不得互相替代：

- `interaction_state`（Core 写）：PENDING / PRESENTED / APPROVED / REJECTED / EXPIRED / EXECUTED / FAILED
- `task_state`（只认 itasca-mcp 返回）：CREATED / READY / RUNNING / PAUSED / COMPLETED / FAILED / CANCELLED / RECOVERING
- `module_state`（Core 汇总）：NOT_STARTED / READY / RUNNING / WAITING_FOR_USER / COMPLETED / FAILED / BLOCKED / CANCELLED

**六条硬规则**（与 `decision_workflow.md` 的 Gate 逻辑一致）：批准≠执行；完成≠科学有效；拒绝不重投同事项；参数变化旧授权失效；执行态只认工具证据；超时≠拒绝。

## 4. 证据五类（实现于 `core/contract.py::EvidenceSource`）

`user_provided` / `pfc_executed`（必须带 `tool_task_id`）/ `derived_computed` / `agent_inferred` / `pending_assumption` / `invalid_evidence`（4.0.1 新增）。

与 `reporting_policy.md` 五层表达对齐：前两类可支撑确定结论，中间两类不能单独支撑 `COMPLETED`。**声明为 PFC 执行证据却无 `tool_task_id` 的引用必须标 `invalid_evidence`，不得降级为 `agent_inferred`；必须触发 M6 质量闸门 FAIL、结论强度降为 hypothesis、模块 BLOCKED。** 诊断中的"待复核技术诊断"标 `agent_inferred`。

## 5. 闭环最小链

`decision_id → authorization_id → tool_task_id → evidence_id → artifact_id`。任一环缺失，结论只能标"待验证"，不得作为下游确定输入。

## 6. 跨模块迭代

M5→M3（模型问题）、M6→M4（数据问题）、M6→M2（指标不足）、结果→M1（假设不符）。回退必须带 `evidence_refs`、`context_version`、`changes_research_assumption`；后者为真时必须重新授权。

## 7. 模块最小字段速查

| 模块 | 必须产出的结构化字段 |
|---|---|
| M1 | research_objective / research_scope / hypotheses[] / independent_vars[] / dependent_vars[] / control_vars[] / constraints[] / expected_outputs[] / fact_vs_suggestion[] / confirmation_state |
| M2 | experiment_type / parameter_schema[] / cases[] / control_groups[] / measurement_plan[] / trace_to_vars[] |
| M3 | dimension / case_id / model_parameters[] / scripts[] / validation(syntax/structure/physics) / manifest / verified_by_execution |
| M4 | sim_task_id / case_id / model_ref / tool_task_id / task_state / checkpoints[] / artifacts[] / evidence_refs |
| M5 | diagnosis_layer / confidence / findings[] / correction_proposals[] / requires_user_confirmation / suggests_recompute / target_module |
| M6 | raw_manifest[] / unit_system / metric_definitions[] / results[] / quality_gate / interpretation[] |

完整字段与标准输出文件见 `docs/FIRST_BATCH_ACCEPTANCE.md` 与 `docs/PFC_Interaction_4.0_技术报告.md` §4。
