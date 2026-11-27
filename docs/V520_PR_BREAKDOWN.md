# PFC Interaction 5.2 — 参数识别与标定核心子系统（S4）PR 拆分

**基线：** 5.1.0（跨会话恢复/模式路由/M1–M6 深度包装/卡片 UI/科学层围压闸门，170 条测试通过）
**目标：** 把《05_参数识别与标定核心子系统技术规范》V2.0 从"设计规范"落地为可调用的 S4 核心子系统，发布通用 **5.2.0**
**原则：**

- 保留 S1–S6 工作流与 M1–M6 模块；S4 是独立核心子系统，不新增第七个 M 模块，不并入 M4。
- 新增能力一律用 `core/s4_*.py` / `modules/s4_calibration.py` 新载体，**不改** 4.0 / 5.0 / 5.0.1 / 5.1 旧实现。
- 三条不可降级原则：科学关系先于调参；每参数独立论证但不孤立确定（B 方案）；科研判断决定参数冻结。
- 本版本实现的是**设计与协议闭环**（关系/协商/规则/试算决策/冻结的强制逻辑）。真实 PFC 数值标定结论仍须真实运行与独立验证，不由本版本自动宣称。

## PR-S4-0 规格入库与台账 ✅

- `docs/S4_SPEC.md`：V2.0 专项规范全文入库（与工作区 `05_...md` 一致）。
- `docs/V520_PR_BREAKDOWN.md`：本台账。
- 载体规划：`core/s4_contracts.py`、`s4_relation.py`、`s4_identifiability.py`、`s4_negotiation.py`、`s4_rules.py`、`s4_next_experiment.py`、`modules/s4_calibration.py`。

## PR-S4-1 数据契约与关系分析引擎

- `core/s4_contracts.py`：MacroTarget/MicroParameter/ParameterRelation/CalibrationConstraint/CalibrationPlan/CalibrationRun/CalibrationResult/CalibrationDecision/CalibrationValidation/ExperienceRecord/ParameterGroup/CalibrationProject；参数五分类、关系六状态、证据 E0–E5、参数六态、数据状态、条件指纹。
- `core/s4_relation.py`：五层关系录入、关系知识库（带状态/证据/适用条件）、静态映射表拒绝、局部敏感性 S_ij、关系可迁移性限制。
- 验收：`tests/test_s4_contracts.py` + `tests/test_s4_relation.py`。禁止无模型/无条件的"弹性模量↔接触刚度"式静态映射被标为 validated；文献支持不得升级为项目验证。

## PR-S4-2 可辨识性与逐参数协商 / 参数组联合

- `core/s4_identifiability.py`：五问判断、等效解/秩/相关性、耦合四问、不可辨识时拒绝继续盲目扩大搜索并建议新增观测。
- `core/s4_negotiation.py`：七步协商、协商卡片"提交≠确认≠授权"、参数状态流转、B 方案（每个参数独立档案 + 参数组联合识别必须同时存在）。
- 验收：`tests/test_s4_identifiability.py` + `tests/test_s4_negotiation.py`。不可辨识不得输出唯一解；组内每个参数必须有独立档案；卡片提交不得改变参数状态。

## PR-S4-3 规则库经验库与下一步最优试算

- `core/s4_rules.py`：12 条规则结构化、通用/模型专属/项目验证三类及优先级、PBM 示例映射（标注适用模型）、E0–E5 经验记录（含适用范围/反例）、E5 不跨模型/维度迁移、旧经验被新证据否定机制。
- `core/s4_next_experiment.py`：候选动作集、信息增益/成本/参数不确定性/科学价值评分、补偿关系检测触发"增加独立观测而非继续搜索"、暂停参数搜索转协商。
- 验收：`tests/test_s4_rules.py` + `tests/test_s4_next_experiment.py`。LPB 经验不得套用 Linear/Flat-Joint；检测到补偿时不得推荐"继续参数搜索"。

## PR-S4-4 S4 子系统编排与验证冻结

- `modules/s4_calibration.py`：C1–C8 八环节门面、拟合/标定/独立验证三分、冻结条件、科研闭环（关系/经验库随每轮更新）、Next-Best 试算接入、与 DecisionManager 的用户授权衔接。
- 验收：`tests/test_s4_orchestration.py`。拟合良好不得直接标记 validated；无独立验证不得冻结；自动优化结果不得自动获得用户确认。

## PR-S4-5 全量测试、文档与发布 5.2.0

- 全量回归（旧 170 条不回退）+ 新增 S4 测试；SKILL/README/CHANGELOG/RELEASE 升 5.2.0；`docs/V520_ACCEPTANCE.md`、`docs/V520_IMPLEMENTATION_STATUS.md`。
- 打包 `pfc-interaction-v5.2.0.zip`，完整性校验，同步安装目录，安装目录全量通过。
