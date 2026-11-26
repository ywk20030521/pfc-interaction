# PFC Interaction 4.0 接口冻结规范（IF0）

**版本：** IF0-1.0.0
**日期：** 2026-11-25
**状态：** 已冻结（接口契约冻结，非模块实现冻结）
**设计基线：** `PFC_Interaction_4.0_技术报告.md`（目标架构与模块职责的唯一定义源）
**适用范围：** PFC Interaction Core 与 M1–M6 六个专业模块之间的全部交互

---

## 0. 冻结目的与禁止事项

本规范解决一个具体问题：**模块各自能运行，但组合起来无法形成科研闭环**。

这类失败不是模块功能不足，而是接口语义不一致：模块 A 的"完成"不等于模块 B 的"可输入"；用户批准被当成执行成功；一个模块自己问用户，另一个模块也问；上层无法把决策、执行和证据串成一条链。

因此本轮**只冻结接口，不开发六个模块**。

**本轮明确禁止：**

- 禁止编写 M1–M6 的业务实现代码；
- 禁止并行启动六个模块的开发任务；
- 禁止把"接口已冻结"解释为"模块已实现"或"4.0 已验收"；
- 禁止在接口未变更评审的情况下，由模块私自扩展契约字段。

**本轮交付：** 接口契约（§2–§7）、可组合性校验用例（`IF0_可组合性校验用例.md`）、基线登记（`BASELINE_REGISTRY.md`）。

---

## 1. 冻结范围

### 1.1 冻结的（契约）

| 编号 | 冻结对象 | 条款 |
|---|---|---|
| C1 | Core ↔ Module 六个接口的方向、触发条件、必填字段 | §2、§3 |
| C2 | 统一输入输出信封 + M1–M6 最小契约字段 | §4 |
| C3 | 三层状态机、唯一写入者、映射与转换硬规则 | §5 |
| C4 | 决策—授权—执行—证据关联链 | §6 |
| C5 | 跨模块迭代回退契约 | §7 |
| C6 | 不重复建设的职责边界 | §2.2 |

### 1.2 未冻结的（留给模块实现）

模块内部算法、知识库组织、脚本生成细节、文件在磁盘上的物理布局、具体工具调用顺序、UI 呈现方式、模块版本节奏。这些不影响跨模块闭环，不纳入本轮。

### 1.3 基线报告的效力

4.0 技术报告定义**目标架构、模块职责与建设批次**；本规范定义**模块之间如何对话**。两者职责分离：

- 报告说"M3 应当构建模型"；
- IF0 说"M3 完成时必须返回什么信封字段、谁能把它标记为完成、M4 凭什么认为可以执行"。

若两者冲突，**架构目标以报告为准，运行时接口以 IF0 为准**，冲突须登记到 `BASELINE_REGISTRY.md`。

---

## 2. 参与方与职责边界

### 2.1 角色定义

| 角色 | 拥有 | 不得拥有 |
|---|---|---|
| **PFC Interaction Core** | 科研任务状态、交互状态、授权、证据链、模块调度、唯一用户交互入口、唯一 Itasca MCP 调用入口 | 专业科研方法本身；PFC 数值计算 |
| **M1–M6 专业模块** | 专业方法、专业产出、专业诊断与建议 | 直接向用户提问；直接执行 PFC；自行改写状态；自行持有 Itasca MCP 句柄 |
| **Itasca MCP / Bridge** | PFC 工具访问与真实执行证据 | 科研语义判断；用户交互 |
| **AUQ** | 结构化问题投递与回答取回 | 执行授权；PFC 操作；科研判断 |
| **Visualization Skill** | 图表输出 | 在六模块内重建可视化能力 |

### 2.2 三条硬边界（防止重复建设与闭环断裂）

1. **交互唯一入口**：所有需要用户参与的事项，模块只能发 `DecisionRequest` 给 Core，由 Core 按双通道去重协议投递。**模块不得直接调用 AUQ，也不得假定自己发出的消息已被用户看到。**
2. **执行唯一通道**：M3/M4 需要执行 PFC 时，只能发 `ExecutionRequest` 给 Core，由 Core 调用 Itasca MCP/Bridge。**模块不得直接持有引擎进程或 Python 会话。**
3. **状态单一写入者**：`interaction_state` 与 `module_state` 仅 Core 可写；`task_state` 仅由 Itasca MCP 返回的执行信息写入，任何模块不得凭主观判断改写。

---

## 3. 六个接口

所有接口均为 Core 与模块之间的**逻辑契约**，不预设实现方式（函数调用、事件、文件交换均可），但字段与语义必须一致。

### I1 — Dispatch（Core → Module）

**触发：** Core 判定某模块应开始一次任务实例。
**必填字段：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `contract_version` | string | 固定 `IF0-1.0.0`；不匹配则拒绝执行 |
| `research_task_id` | string | 顶层科研任务 |
| `module_task_id` | string | 本次模块实例唯一 ID（重跑生成新 ID） |
| `module_id` | string | `M1`…`M6` |
| `input_refs` | array | 上游产物引用（artifact_id + version + hash） |
| `context_version` | string | 当前实验/模型上下文版本；用于授权绑定与去重 |
| `authorizations` | array | 已获批且仍有效的授权（authorization_id + scope） |

**约束：** 输入引用必须可解析到具体版本；不得传"最新文件"这类模糊引用。

### I2 — Result（Module → Core）

**触发：** 模块完成一次执行、失败或需要阻塞。返回统一信封（§4）。
**约束：**

- `status.module_state` 必须是 §5.2 枚举值；
- `output.artifacts` 每项必须有 `artifact_id`、`path`、`version`、`hash`；
- `evidence[]` 每项必须标注 `source`（§6.3 五类枚举）；
- 模块**不得**在 Result 中声称"用户已批准"或"PFC 已执行成功"——这两类事实不由模块产生。

### I3 — DecisionRequest（Module → Core → 用户）

**触发：** 模块遇到科研假设、参数选择、高影响操作或检查点，需要人决策。
**必填字段：**

| 字段 | 说明 |
|---|---|
| `decision_id` | 全局唯一，贯穿授权与证据链 |
| `事项键四字段` | `experiment_id`、`stage_id`、`决策主题`、`context_version`（沿用既有去重协议） |
| `question` | 面向人的问题陈述 |
| `options` | 候选项 + 各自影响 |
| `evidence_refs` | 支撑该问题的证据 |
| `authorization_scope` | 若选择"同意"，允许执行的具体操作范围；无范围则视为仅讨论 |
| `blocks_module_task_id` | 阻塞哪个模块任务 |

**约束：** 模块发出的是**请求**，不是对用户说话。Core 按去重判定后选择 Native Chat 或 AUQ 投递，并回写 `delivery_status`。

### I4 — DecisionResolution（Core → Module）

**必填字段：** `decision_id`、`resolution`（`APPROVED`/`REJECTED`/`ANSWERED`/`EXPIRED`）、`authorization_id`（若批准）、`bound_context_version`、`resolved_at`。

**约束：**

- `REJECTED` 必须写明被拒绝的操作，模块不得换个名字重试；
- `APPROVED` 必须绑定 `context_version`：参数或模型状态变化后旧授权自动失效，不得沿用（对应报告 §3.6）；
- `APPROVED` 只代表获得授权，**不代表已执行**（§5.4）。

### I5 — ExecutionRequest / ExecutionResult（Module ↔ Core ↔ Itasca MCP）

**ExecutionRequest 必填：** `requester_module_id`、`module_task_id`、`operation`（建模检查/运行/检查点查询/中断等）、`model_ref`、`case_id`、`authorization_id`、`expected_effect`。
**ExecutionResult 必填：** `tool_task_id`（Itasca MCP 真实返回的任务 ID）、`task_state`、`evidence_refs`、`output_artifacts`、`error`（若有）。

**约束：**

- `task_state` 必须来自工具返回，不得由 Agent 或模块推断；
- 无有效 `authorization_id` 的执行请求，Core 必须拒绝；
- 重复执行造成覆盖或任务重复，不得标记为 `COMPLETED`（报告 §4.4.5）。

### I6 — IterationRequest（Module → Core → 目标模块）

**触发：** 诊断或分析发现需要回退到前序模块（§7）。字段见 §7.2。
**约束：** 回退通过**新建子任务**实现，不改写原任务历史。

---

## 4. 统一输入输出信封

### 4.1 信封（所有模块 I2 返回必须使用）

```json
{
  "contract_version": "IF0-1.0.0",
  "module_id": "M3",
  "module_version": "0.1.0",
  "research_task_id": "R-...",
  "module_task_id": "M3-...",
  "parent_task_id": "M2-...",
  "input_refs": [{"artifact_id": "...", "version": "...", "hash": "..."}],
  "preconditions": ["..."],
  "status": {"module_state": "COMPLETED", "task_state_ref": "..."},
  "output": {
    "structured": {"...": "模块最小契约字段，见 4.2"},
    "artifacts": [{"artifact_id": "...", "path": "...", "version": "...", "hash": "..."}]
  },
  "evidence": [{"source": "pfc_executed", "ref": "..."}],
  "decisions": [{"decision_id": "...", "delivery_status": "ANSWERED"}],
  "limitations": ["..."]
}
```

报告 §6.1 的 11 个字段全部保留；新增 `contract_version`（防止契约漂移）与 `parent_task_id`（跨模块迭代可追溯）。

### 4.2 各模块最小契约字段

字段名一经冻结，下游模块按此读取；模块可增加内部字段，但不得改变这些字段的语义或类型。

| 模块 | 必读上游输入 | 必须产出的结构化字段 | 标准输出文件（沿用报告） |
|---|---|---|---|
| **M1** | 用户自然语言 / 项目资料 | `research_objective`、`research_scope`、`hypotheses[]`、`independent_vars[]`、`dependent_vars[]`、`control_vars[]`、`constraints[]`、`expected_outputs[]`、`fact_vs_suggestion[]`、`confirmation_state` | `research_question.md`、`research_plan.md`、`research_hypotheses.md`、`research_workflow.md`、`research_requirements.json` |
| **M2** | `research_requirements.json` | `experiment_type`、`parameter_schema[]`（`name`/`unit`/`range`/`default`/`source`/`confirmed`）、`cases[]`（`case_id` + 参数值）、`control_groups[]`、`measurement_plan[]`（指标 + 计算口径）、`trace_to_vars[]` | `experiment_design.md`、`parameter_schema.json`、`experiment_matrix.csv`、`control_groups.md`、`measurement_plan.md` |
| **M3** | `parameter_schema.json`、`experiment_matrix.csv`、`measurement_plan.md` | `dimension`（2D/3D）、`case_id`、`model_parameters[]`（继承 M2 并带 `source`）、`scripts[]`、`validation`（`syntax`/`structure`/`physics` 三层结果）、`manifest`、`verified_by_execution`（布尔，默认 false） | `model_design.md`、`model.dat`、`model_parameters.json`、`model_validation.md`、`model_manifest.json` |
| **M4** | `model_manifest.json`、`cases[]` | `sim_task_id`、`case_id`、`model_ref`、`tool_task_id`、`task_state`、`checkpoints[]`、`artifacts[]`、`evidence_refs` | `simulation_config.json`、`simulation_log`、`simulation_status.json`、`checkpoint_manifest.json`、`execution_report.md`、`simulation_artifacts/` |
| **M5** | `simulation_status.json`、`execution_report.md`、`simulation_artifacts/`、`model_validation.md` | `diagnosis_layer`（model/numerical/physical/data/result）、`confidence`（confirmed/possible/hypothesis）、`findings[]`（问题描述+依据+证据）、`correction_proposals[]`、`requires_user_confirmation`、`suggests_recompute`、`target_module` | `diagnosis_report.md`、`diagnostic_evidence.json`、`anomaly_records.json`、`correction_proposals.md`、`revalidation_plan.md` |
| **M6** | `simulation_artifacts/`、`measurement_plan.md`、`analysis_config` | `raw_manifest[]`（来源+hash）、`unit_system`、`metric_definitions[]`、`results[]`、`quality_gate`（pass/fail + 理由）、`interpretation[]`（必须关联 evidence） | `raw_data_manifest.json`、`processed_data/`、`analysis_config.json`、`analysis_results.json`、`comparison_report.md`、`analysis_report.md` |

**跨模块继承硬规则：**

- M3 的 `model_parameters[].source` 必须指回 M2 的参数定义；未经用户确认的改动必须标记 `changed_without_confirmation=true`，且不得进入已授权执行；
- M4 的 `case_id` 必须存在于 M2 的 `cases[]`；
- M6 的 `metric_definitions[]` 必须能追溯到 M2 的 `measurement_plan[]`，不能临时发明口径；
- 任何模块不得覆盖上游原始数据文件（`raw_data_manifest` 中的条目只读）。

---

## 5. 状态规范（冻结）

### 5.1 报告中的三套状态必须分层，不得混用

| 层 | 状态枚举（来源） | 描述对象 | 唯一写入者 |
|---|---|---|---|
| **交互态** `interaction_state` | `PENDING`/`PRESENTED`/`APPROVED`/`REJECTED`/`EXPIRED`/`EXECUTED`/`FAILED`（报告 §3.4） | 一次用户决策事项 | Core |
| **执行态** `task_state` | `CREATED`/`READY`/`RUNNING`/`PAUSED`/`COMPLETED`/`FAILED`/`CANCELLED`/`RECOVERING`（报告 §4.4.3） | 一次 PFC 仿真任务 | Itasca MCP 返回信息 |
| **模块态** `module_state` | `NOT_STARTED`/`READY`/`RUNNING`/`WAITING_FOR_USER`/`COMPLETED`/`FAILED`/`BLOCKED`/`CANCELLED`（报告 §6.2） | 一次模块实例 | Core（汇总前两者推导） |

**裁定：** 这三套状态**正交**，不是同一状态机的三种写法。报告未给出映射，IF0 冻结如下映射与写入规则。任何模块不得用其中一套去替代另一套。

### 5.2 三态映射规则

| 场景 | interaction_state | task_state | module_state |
|---|---|---|---|
| 模块已派发、等待上游产物 | — | — | `NOT_STARTED` / `READY` |
| 模块正在做专业工作（未执行 PFC） | — | — | `RUNNING` |
| 模块请求用户决策，Core 已投递 | `PRESENTED` | — | `WAITING_FOR_USER` |
| 用户批准，等待执行 | `APPROVED` | `READY` | `WAITING_FOR_USER` → `RUNNING` |
| PFC 任务真正在跑 | `APPROVED` | `RUNNING` | `RUNNING` |
| 用户在检查点拒绝继续 | `REJECTED` | `PAUSED` 或 `CANCELLED`（按 M4 实际状态） | `BLOCKED` 或 `CANCELLED` |
| 工具返回任务完成 | `EXECUTED` | `COMPLETED` | `COMPLETED`（仅表示模块任务按定义完成） |
| 工具返回失败 | `FAILED` | `FAILED` | `FAILED` |
| 决策超时 / 上下文已变 | `EXPIRED` | 不变 | `BLOCKED`（需新决策） |
| 异常后按证据恢复 | — | `RECOVERING` | `RUNNING` |

### 5.3 状态转换硬规则

1. **批准 ≠ 执行**：`APPROVED` 只能由 Core 根据用户回答写入；只有拿到 `ExecutionResult` 才能写 `EXECUTED`。禁止把"已批准"表述为"PFC 已执行成功"（报告 §3.4/§3.6）。
2. **完成 ≠ 科学有效**：`module_state=COMPLETED` 仅表示模块任务按定义完成，不代表结论已验证（报告 §6.2）。M3 生成脚本不等于模型验证，M4 跑完不等于 M5 已确认物理合理性。
3. **拒绝不可绕过**：`REJECTED` 后不得通过改换措辞重新投递同一 `事项键`；新提问必须带新的 `context_version` 或新证据。
4. **参数变化使授权失效**：`bound_context_version` 与当前不一致时，旧 `APPROVED` 自动失效，模块必须重新请求决策。
5. **执行态只认工具证据**：`task_state` 不得由 Agent 主观判定；无 `tool_task_id` 的 `COMPLETED` 视为无效回执。
6. **超时 ≠ 拒绝**：`EXPIRED` 只表示决策条件失效，不得解释为"用户不同意"。

---

## 6. 决策—授权—执行—证据关联链

### 6.1 闭环最小链

```
decision_id（用户决策）
   └─ authorization_id + authorization_scope + bound_context_version（授权）
         └─ tool_task_id（Itasca MCP 真实执行）
               └─ evidence_id + evidence.source（执行证据）
                     └─ artifact_id + version + hash（可复核产物）
```

**验收要求：** 给定任一科研结论，必须能沿这条链回溯到具体用户决策与具体执行证据；链中任一环缺失，结论只能标为"待验证"，不得作为后续模块的确定输入。

### 6.2 授权三态（报告 §3.5）

| 行为 | 是否产生授权 | 接口表现 |
|---|---|---|
| 讨论 | 否 | 仅 Chat 语义，无 `decision_id` |
| 确认 | 否（仅认可方案） | `decision_id` + `resolution=ANSWERED`，无 `authorization_id` |
| 授权 | 是（允许高影响操作） | `decision_id` + `APPROVED` + `authorization_id` + `scope` |

AUQ 返回的选项结果**不自动等于执行授权**；Core 必须结合任务状态、作用域和执行策略判断。

### 6.3 证据来源五类枚举（报告 §6.3）

`evidence.source` 取值固定为：

| 枚举 | 含义 |
|---|---|
| `user_provided` | 用户提供的事实或参数 |
| `pfc_executed` | PFC 实际执行获得（必须带 `tool_task_id`） |
| `derived_computed` | 数据处理计算得到（必须带计算口径/脚本引用） |
| `agent_inferred` | Agent 基于证据的推断（必须带所依据的证据 ID） |
| `pending_assumption` | 尚待用户确认的假设 |

**硬规则：** `agent_inferred` 与 `pending_assumption` 不能单独支撑 `COMPLETED` 或科研结论。诊断中的"待复核技术诊断"必须标为 `agent_inferred`（这是 0.1.0 复审已确立的规则）。

---

## 7. 跨模块迭代契约（冻结）

### 7.1 报告定义的四条回退路径

| 触发 | 源 → 目标 | 典型原因 |
|---|---|---|
| M5 发现模型设置问题 | M5 → M3 | 接触模型/边界与研究假设不符 |
| M6 发现数据质量问题 | M6 → M4 | 测量点不足、工况数据缺失 |
| M6 发现研究指标不足 | M6 → M2 | 测量计划未覆盖所需指标 |
| 结果与假设不符 | M6/M5 → M1 | 重新审视研究问题 |

### 7.2 IterationRequest 必填字段

| 字段 | 说明 |
|---|---|
| `source_module` / `target_module` | 回退两端 |
| `trigger_layer` | 对应 M5 分层诊断：model/numerical/physical/data/result |
| `evidence_refs` | 触发回退的证据（不得只有推断） |
| `context_version` | 回退时的上下文版本 |
| `changes_research_assumption` | 是否改变科研假设/边界 |
| `parent_task_id` | 指向原任务，保留历史 |

### 7.3 回退硬规则

1. 回退**新建子任务**，不把原任务状态倒退；原 `research_task_id` 保持一致，`module_task_id` 链可追溯。
2. `changes_research_assumption=true` 时，Core **必须**发起新的用户决策，不得沿用旧授权（§5.3 规则 4）。
3. 回退不得覆盖上游产物；新产物以新 `version` 记录，`parent_task_id` 指向旧版本。
4. 回退完成后必须重新走一遍受影响的下游校验，不能只替换文件。

---

## 8. 变更控制

- `contract_version` 采用 `IF0-<major>.<minor>.<patch>`。
- **破坏性变更**（改字段名/语义/状态枚举/接口方向）需升 major，并对 M1–M6 全部接口做一次可组合性回归；
- 新增可选字段升 minor；仅修文档表述升 patch。
- 任何模块不得私自扩展契约；扩展需求先登记到 `BASELINE_REGISTRY.md` 的"待裁定"区。
- 本规范冻结后，六模块开发才能启动；启动前先跑 `IF0_可组合性校验用例.md` 的接口级用例。

---

## 9. 反模式清单（本规范要拦截的失败）

| 反模式 | 拦截条款 |
|---|---|
| M3 生成脚本后直接标 `COMPLETED`，M4 拿去执行才发现跑不通 | §4.2 `verified_by_execution`、§5.3 规则 2 |
| 用户批准参数 X 后参数改成 Y，模块仍用旧授权执行 | §5.3 规则 4、I4 `bound_context_version` |
| 模块自己问用户，Core 又问一遍 | §2.2 边界 1、I3 |
| Agent 写 `task_state=COMPLETED` 但无 `tool_task_id` | §2.2 边界 3、§5.3 规则 5 |
| 用 `agent_inferred` 当确定证据写进结论 | §6.3 |
| M5 发现问题后直接改 M3 文件，无记录 | §7.3 |
| 六模块各自保存一份"用户已确认"，内容冲突 | §6.1 关联链、§2.2 边界 1 |
| 模块输出只有自然语言总结，下游无法读取 | §4.1 信封、§4.2 最小字段 |
