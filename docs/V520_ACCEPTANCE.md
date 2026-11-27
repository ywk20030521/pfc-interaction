# PFC Interaction 5.2.0 — 验收报告（S4 参数识别与标定核心子系统）

**日期：** 2026-11-27
**基线：** 5.1.0（170 条测试通过）
**规范：** `docs/S4_SPEC.md`（《05_参数识别与标定核心子系统技术规范》V2.0）

## 1. 验收状态总览

| 层次 | 状态 | 说明 |
|---|---|---|
| 接口/契约层 | 通过 | 12 类数据对象、参数五分类、证据 E0–E5、关系六状态、参数六态、条件指纹均有测试 |
| 设计逻辑层 | 通过 | 三条不可降级原则、五层关系、七步协商、B 方案、Next-Best 决策、拟合/标定/验证三分全部有强制测试 |
| 全量回归 | 通过（含环境说明） | 219 条中 218 通过/5 跳过；1 ERROR 为离线 PFC bridge 连接失败，与本次改动无关 |
| 真实 PFC 数值标定 | 不在本版本范围 | 本版本为设计与协议闭环，不自动宣称材料参数定量标定成功 |

## 2. 功能验收对照（规范 §13.1）

| ID | 验收项 | 状态 | 证据测试 |
|---|---|---|---|
| S4-F01 | 创建标定项目 | 通过 | test_s4_contracts.test_project_snapshot_is_traceable |
| S4-F02 | 参数语义识别与分类 | 通过 | test_parameter_class_and_state_transition |
| S4-F03 | 基准快照/条件指纹 | 通过 | test_condition_fingerprint_changes_with_structure |
| S4-F05 | 五层关系分析 | 通过 | test_five_layers_must_be_complete / test_static_mapping_table_is_rejected |
| S4-F06 | 关系库与经验库 E0–E5 | 通过 | test_relation_upgrade_needs_project_evidence / test_experience_grade_and_scope |
| S4-F07 | 敏感性矩阵 | 通过 | test_local_sensitivity_is_named_local |
| S4-F08 | 参数交互分析 | 通过 | test_coupling_four_questions |
| S4-F09 | 可辨识性诊断 | 通过 | test_unidentifiable_refuses_blind_search / test_high_correlation_detects_compensation |
| S4-F10 | 逐参数协商七步 | 通过 | test_seven_steps_must_be_in_order / test_card_submit_is_not_confirm_nor_authorize |
| S4-F11 | 参数组联合（B 方案） | 通过 | test_scheme_b_group_needs_independent_archives / test_joint_decision_requires_all_coupling_answers |
| S4-F12 | 规则库执行与模型隔离 | 通过 | test_twelve_rules_present / test_pbm_mapping_is_model_isolated |
| S4-F13 | 下一步最优试算 | 通过 | test_compensation_forbids_blind_search / test_equivalent_solutions_trigger_new_condition |
| S4-F14 | 预算/授权门槛 | 通过 | test_c5_approve (编排) / test_decision_requires_full_seven_steps |
| S4-F15 | 结果反馈与闭环 | 通过 | test_snapshot_traceable / test_experience_can_be_negated_with_counterexample |
| S4-F16 | 独立验证与冻结 | 通过 | test_freeze_requires_independent_validation / test_fit_status_is_not_calibration_or_validation |
| S4-F17 | 冻结快照可追溯 | 通过 | test_freeze_succeeds_only_with_confirmed_param_and_validation |
| S4-F18 | 失败处理 | 通过 | test_calibration_run_rejects_fake_tool_ids |

## 3. 三条不可降级原则的守护测试

1. **科学关系先于数值调参**：`test_static_mapping_table_is_rejected`（拒绝无条件的"E↔接触刚度"静态映射）、`test_literature_cannot_upgrade_to_project_validation`（文献 E2 不得升级为项目验证）。
2. **每个参数独立论证但不孤立确定（B 方案）**：`test_scheme_b_group_needs_independent_archives`（无独立档案不得入组）、`test_joint_decision_requires_all_coupling_answers`（耦合四问未答不得联合决策）。
3. **科研判断决定参数冻结**：`test_freeze_rejects_unconfirmed_parameter`（未确认不得冻结）、`test_card_submit_is_not_confirm_nor_authorize`（卡片提交≠确认≠授权）、`test_confirm_state_needs_approved_decision`（决策未确认不得流转状态）。

## 4. 关键设计决策覆盖

| 三段讨论决策 | 落地位置 | 测试 |
|---|---|---|
| A 方案：S4 独立子系统 | `modules/s4_calibration.py` | test_c_stages_are_ordered |
| C1–C8 八环节 | `S4CalibrationSubsystem` + C1_C8 | test_c_stages_are_ordered |
| 五层关系机制 | `FiveLayerRelation` / `RelationEngine` | test_five_layers_must_be_complete |
| 关系六状态 | `RelationStatus` | test_relation_upgrade_needs_project_evidence |
| 七步协商 | `SEVEN_STEPS` / `NegotiationEngine` | test_seven_steps_must_be_in_order |
| 协商卡片提交≠确认≠授权 | `NegotiationCard` | test_card_submit_is_not_confirm_nor_authorize |
| B 方案（推荐，已采用） | `create_group` + `confirm_state` | test_scheme_b_group_needs_independent_archives |
| 12 条高效率规则 | `RULES` | test_twelve_rules_present |
| E0–E5 经验可信等级 | `EvidenceGrade` / `ExperienceRecord` | test_e5_does_not_migrate_across_* |
| 下一步最优试算 | `NextExperimentEngine` | test_compensation_forbids_blind_search |
| 拟合/标定/验证三分 | `c8_fit_status` / `c8_validate` | test_fit_status_is_not_calibration_or_validation |
| 失败与反例保留 | `negate_experience` | test_experience_can_be_negated_with_counterexample |

## 5. 未关闭 / 边界

- 真实 PFC 数值标定与独立工况验证不由本版本自动完成；需按 S4 规范配合 M4/M5/M6 与真实运行证据执行。
- 本次全量测试中 `test_v401_regressions` 的桥接用例因 PFC bridge 未启动而 ERROR（连接 localhost:9001 被拒绝）。该 bridge 此前已按项目记录停止；此 ERROR 与 S4 改动无关，重连 bridge 后应恢复。
- 宿主 UI 卡片渲染仍由宿主平台决定，本 Skill 提供数据结构与参考元数据。

**结论：5.2.0 在"设计与协议闭环"范围内通过验收。** 不宣称材料参数定量标定通过。
