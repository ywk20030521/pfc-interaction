# PFC Interaction 5.0 — 总体架构与科研工作流规范

**规范编号：** PFCI-ARCH-5.0  
**规范级别：** 强制  
**适用对象：** PFC Interaction Skill、Core、所有专业模块及其 Agent 运行环境  
**关联规范：** `02_科研专业模块与技术能力规范.md`、`03_人机协作与决策协议规范.md`、`04_提问卡片强制设计规范_V2.md`

---

## 1. 目的与适用范围

本规范定义 PFC Interaction 5.0 的总体产品边界、系统分层、科研工作流、阶段状态、Core 职责和阶段推进约束。所有 Skill 入口指令、模块说明、工作流模板和示例必须遵守本规范。

PFC Interaction 是面向 PFC2D/PFC3D 数值模拟研究的轻量化科研协作 Skill。它围绕研究人员的科研问题组织持续讨论、实验设计、技术方案、参数确定、仿真执行、异常干预和结果分析。

本规范定义目标架构，不代表其中所有能力已经实现。实现状态必须另行记录并提供证据。

## 2. 不可违反的架构原则

1. **一个 Skill、一个协作主体：** 用户面对一个持续协作的 PFC 科研助手，不要求用户分别启动六个模块。
2. **Agent 主导、用户决策：** Agent 负责理解、分析、建议、协调和推进；研究人员保留科学判断及关键决策权。
3. **工作流与模块分离：** 六个科研阶段是用户可见工作流程；M1–M6 是按需调用的专业能力，不得一一强制绑定。
4. **交互贯穿全过程：** 人机交互不是独立的前置问卷，也不是第七个专业模块。
5. **证据驱动：** 用户陈述、Agent 建议、工具事实、计算结果、推断和待验证假设必须区分。
6. **复用既有工具：** 不重复开发 Itasca MCP/Bridge、PFC 执行器或 Scientific Visualization Skill 已有能力。
7. **轻量优先：** 默认以 Skill + Agent Harness + 现有工具链实现，不强制引入独立 Web、数据库或后台服务。
8. **允许回退与重开：** 科研流程不是不可逆的线性流水线。
9. **不以问答数量作为进度：** 不得以固定问题数、固定轮数或表单完成率判断阶段完成。
10. **实现与验证分开：** 设计完成、代码实现、工具可调用、真实 PFC 执行和科学有效性验证是不同状态。

## 3. 总体分层架构

```text
研究人员
   │
   ▼
交互层
   ├── Agent Native Chat：开放式、连续科研讨论
   └── AUQ：结构化、异步问题与明确决策
   │
   ▼
PFC Interaction Core
   ├── Context Manager
   ├── Discussion Manager
   ├── Reasoning & Proposal
   ├── Decision Manager
   └── Workflow Orchestrator
   │
   ▼
科研工作流层
   ├── S1 研究对象与科研目标
   ├── S2 实验类别与实验设计
   ├── S3 技术方案与建模路线
   ├── S4 参数确定与标定
   ├── S5 仿真执行与异常干预
   └── S6 结果分析与科研总结
   │
   ▼
专业能力层
   ├── M1 Research Planning
   ├── M2 Experiment Design
   ├── M3 PFC Modeling
   ├── M4 Simulation Management
   ├── M5 Scientific Diagnosis
   └── M6 Scientific Analysis
   │
   ▼
工具层
   ├── Itasca MCP / Bridge
   ├── PFC2D / PFC3D
   ├── Python API / 文件数据
   └── Scientific Visualization Skill
```

### 3.1 层级职责

- **交互层**只负责人与 Agent 的信息交换和结构化呈现，不拥有科研决策权。
- **Core**负责跨轮次上下文、讨论状态、决策状态和工作流协调。
- **工作流层**定义当前科研任务正在完成什么工作。
- **专业能力层**提供科研知识、分析和技术实现能力。
- **工具层**负责实际执行和数据访问。工具成功不自动代表科学结论成立。

### 3.2 禁止的架构混淆

- 不得把阶段名称当作模块名称。
- 不得把 AUQ 当作科研推理引擎。
- 不得把 Itasca MCP 当作人机交互层。
- 不得把模块调用成功当作阶段完成。
- 不得把脚本生成成功当作模型验证通过。
- 不得把仿真运行完成当作科学结果可信。
- 不得把卡片提交当作执行授权。

## 4. 六阶段科研工作流

### S1 研究对象与科研目标

核心问题：研究什么、为什么研究、需要回答什么科学问题？

必须覆盖：研究对象、背景与意义、研究目的、科学问题、研究假设、研究范围、约束条件、预期成果，以及 PFC 方法适用性。

阶段产物：
- `research_brief.md`
- `research_question.md`
- `research_hypotheses.md`
- `research_scope.md`

完成条件：研究对象、核心目标、主要科学问题和研究边界足以指导实验设计；未解决的关键假设已记录；用户同意推进或明确要求暂定推进。

### S2 实验类别与实验设计

核心问题：通过什么实验回答研究问题？是否需要对照组、基准组或控制变量？

必须覆盖：实验类别、对照策略、自变量、因变量、控制变量、工况矩阵、重复试验、混杂因素、观测指标、数据采集和比较方法。

对照组不是强制存在，但必须讨论是否需要，并说明设置或不设置的科学理由。

阶段产物：
- `experiment_design.md`
- `experiment_matrix.csv`
- `variable_schema.json`
- `measurement_plan.md`

完成条件：实验类型、变量关系、工况逻辑、对照策略、观测指标及比较方法清晰，关键设计选择已确认。

### S3 技术方案与建模路线

核心问题：如何将实验设计转化为合理、可执行的 PFC 模型？

必须讨论：PFC2D/PFC3D 选择、几何与试样、颗粒生成和级配、接触模型、边界条件、加载方式、伺服与停止条件、测量方式、数据输出和模型验证。

必须区分：
1. 语法/命令检查；
2. 模型结构检查；
3. 初始状态和平衡检查；
4. 参数与边界一致性检查；
5. 物理合理性检查；
6. 真实 PFC 环境执行验证。

阶段产物：
- `technical_route.md`
- `model_design.md`
- `model_requirements.json`
- `measurement_schema.json`
- `model_validation_plan.md`

### S4 参数确定与标定

核心问题：参数从哪里来、如何确定、如何证明其能产生目标宏观响应？

必须包括：参数分类、单位和来源、初始值、标定目标、待标定参数、参数范围、标定工况、误差指标、敏感性与耦合、迭代记录、版本管理和确认状态。

参数标定是跨模块工作流，不属于某一个模块的独占职责。M2 设计标定工况，M3 配置模型，M4 执行任务，M5 诊断可信度，M6 计算误差和敏感性，Core 组织讨论与决策。

阶段产物：
- `parameter_register.csv`
- `calibration_plan.md`
- `calibration_matrix.csv`
- `calibration_history.csv`
- `calibration_results.json`
- `calibrated_parameters.json`

完成条件：参数来源、单位、范围和状态明确；标定已按方案执行并有记录；达到预设标准，或如实记录未达到标准及原因。未经验证不得标记为已标定。

### S5 仿真执行与异常干预

核心问题：如何可靠执行仿真，并在异常发生时及时控制和处理？

必须覆盖：执行环境检查、模型与参数版本检查、任务提交、状态监测、检查点、暂停/停止/恢复/重跑、日志与数据完整性、异常诊断和修正决策。

M4 负责运行控制；M5 负责科学诊断。M4 可按预设安全条件刹车，但不得擅自给出科学归因。重大修正由用户决策。

阶段产物：
- `simulation_config.json`
- `simulation_status.json`
- `simulation_log/`
- `checkpoint_manifest.json`
- `anomaly_records.json`
- `execution_report.md`

### S6 结果分析与科研总结

核心问题：得到了什么结果，结果是否可信，能够支持什么结论？

必须覆盖：原始数据清单、完整性、单位与口径、指标计算、多工况比较、统计与不确定性、结果可信度、研究假设对照、结论边界和后续研究建议。

M5 判断异常与可信度；M6 计算指标、统计、比较和解释。Scientific Visualization Skill 负责图表和三维可视化实现。

阶段产物：
- `raw_data_manifest.json`
- `processed_data/`
- `analysis_config.json`
- `analysis_results.json`
- `comparison_report.md`
- `diagnosis_report.md`
- `analysis_report.md`
- `research_conclusion.md`

## 5. 阶段关系与迭代

默认主线为 S1 → S2 → S3 → S4 → S5 → S6，但必须允许：

- S2 返回 S1：实验设计暴露研究问题不清；
- S3 返回 S2：技术条件要求调整实验设计；
- S4 返回 S3：参数标定表明模型结构或接触模型不适配；
- S5 返回 S3/S4：运行异常要求修改模型或参数；
- S6 返回任一前序阶段：结果暴露假设、设计、模型或数据问题。

每次回退必须说明触发证据、影响范围、需要重做的产物和旧决策是否失效。不得无差别推翻未受影响的工作。

## 6. Core 的强制职责

Core 必须完成以下职责：

- 维护统一科研上下文；
- 维护当前阶段和讨论主题；
- 区分已确认、待确认、已否决、暂缓和失效事项；
- 判断需要调用的专业模块；
- 组织模块输入输出和证据；
- 判断是否需要用户讨论、确认或授权；
- 识别阶段完成条件；
- 管理回退、重开和变更影响；
- 防止重复提问和重复执行；
- 在每轮重要进展后给出可理解的反馈。

Core 不得退化为单纯路由器，也不得替代 Agent 的科研推理。

## 7. 状态模型

阶段状态：
`NOT_STARTED`、`DISCUSSING`、`IN_PROGRESS`、`WAITING_FOR_USER`、`READY_FOR_REVIEW`、`COMPLETED`、`BLOCKED`、`REOPENED`、`CANCELLED`。

模块任务状态：
`NOT_STARTED`、`READY`、`RUNNING`、`WAITING_FOR_USER`、`COMPLETED`、`FAILED`、`BLOCKED`、`CANCELLED`。

阶段状态、模块状态、讨论状态、决策状态和 PFC 任务状态必须分开管理，不得共用一个含义模糊的 `status` 字段。

## 8. 统一科研上下文最小结构

```yaml
research_task:
  research_task_id: unique_id
  title: ""
  current_stage: S1
  stage_status: DISCUSSING
  objectives: []
  research_questions: []
  hypotheses: []
  constraints: []
  discussion:
    current_topic: ""
    confirmed: []
    pending: []
    rejected: []
    unresolved: []
  decisions: []
  parameters: []
  experiments: []
  models: []
  simulations: []
  diagnoses: []
  analyses: []
  artifacts: []
  provenance: []
```

逻辑结构不强制使用数据库。初期可用 Skill 上下文、文件和 JSON；只有出现明确需求后才评估独立持久化服务。

## 9. 证据与事实分类

所有重要陈述必须能归入以下类别：

- `USER_INPUT`：用户明确提供；
- `AGENT_PROPOSAL`：Agent 建议；
- `TOOL_EVIDENCE`：工具实际返回；
- `COMPUTED_RESULT`：从数据计算；
- `INFERENCE`：基于证据的推断；
- `UNVERIFIED_ASSUMPTION`：待验证假设。

不得把建议写成用户决定，不得把推断写成工具事实，不得把未验证假设写成模型已验证条件。

## 10. 实施与验收约束

验收必须同时覆盖：
- 六阶段完整性；
- 阶段回退和重开；
- Core 跨轮次上下文维护；
- 讨论、确认、授权和执行状态分离；
- 参数标定跨模块闭环；
- 真实 PFC 工具证据；
- 失败、取消、超时和恢复；
- 数据与结论可追溯。

不得以文档齐全、模块数量、卡片数量或单元测试通过替代端到端科研案例验收。

## 11. 与其他三份规范的关系

- 模块职责、模块接口和专业技术方法以规范 02 为准。
- 人机交互、讨论、双通道、授权和异常协作以规范 03 为准。
- 任何结构化提问卡片的视觉和组件要求以规范 04 为准。
- 若发生冲突，本规范负责总体边界；专业实现细节分别由 02、03、04 约束。不得通过局部实现绕过总体边界。

## 12. 强制验收清单

- [ ] 用户面对单一 PFC Interaction Skill。
- [ ] 六个阶段覆盖完整科研流程。
- [ ] 阶段与专业模块没有一一绑定限制。
- [ ] Core 能持续维护研究上下文和讨论状态。
- [ ] 不以固定问题数量推进阶段。
- [ ] 支持回退、重开和影响分析。
- [ ] 参数标定不是单次参数填写。
- [ ] M4 运行控制与 M5 科学诊断分离。
- [ ] M5 数据可信度判断与 M6 定量分析分离。
- [ ] 不重复实现既有 PFC 工具和可视化能力。
- [ ] 设计、实现、运行和科学验证状态明确区分。
