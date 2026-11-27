# PFC Interaction 5.0 升级 PR 拆分与执行台账

**基线：** `pfc-interaction` 4.0.0（六模块契约 + v41 阶段门 + 提问卡片 V2）  
**目标：** 按 PFCI-ARCH/MOD/HUMAN/CARD-5.0 与《PFC_Interaction_5.0_技术报告》升级为 5.0.0  
**原则：** 新增 v50 实现载体，保留 4.0 接口与既有回归；设计完成 ≠ 实现 ≠ 工具可调用 ≠ 科学验证。

---

## PR-0 规格入库与验收基线 ✅ 已完成

- 内容：四份强制规范与 5.0 技术报告纳入 `docs/`，SKILL.md 强制引用；建立实现状态矩阵。
- 交付：`docs/PFCI-ARCH-5.0.md`、`PFCI-MOD-5.0.md`、`PFCI-HUMAN-5.0.md`、`PFCI-CARD-5.0.md`、`PFC_Interaction_5.0_技术报告.md`、`README_四规范总索引.md`、`docs/V50_IMPLEMENTATION_STATUS.md`。
- 验收：SKILL.md 可追溯到四规范；能力状态逐条标注，不把目标写成已实现。

## PR-1 统一科研上下文与状态模型 ✅ 已完成

- 内容：`core/v50_context.py`：S1–S6、阶段/模块状态、六类证据、参数记录、决策记录、交互事件、ResearchTask 上下文与 provenance。
- 依据：ARCH §4/§7/§8/§9；技术报告 §8。
- 验收：阶段状态与模块状态分离；证据六分类；`cv` 版本随变更递增。

## PR-2 决策、授权与双通道去重 ✅ 已完成

- 内容：`core/v50_decisions.py`：决策状态机、影响失效、授权绑定（操作/对象/版本/上下文）、High-impact 操作、Native Chat/AUQ 事项键去重、取消/超时/通道切换。
- 依据：HUMAN §7–§10、§13；技术报告 §9。
- 验收：建议不自动确认；回答不自动确认；参数/模型版本变化使旧授权失效；同一事项只有一个有效交互实例。

## PR-3 持续讨论与方案建议引擎 ✅ 已完成

- 内容：`core/v50_discussion.py`：讨论轮次七要素、先分析后追问、备选方案比较（ pros/cons/适用条件/依据）、阶段总结、按完成条件推进（无固定问题数）。
- 依据：HUMAN §2–§6；技术报告 §6。
- 验收：无分析追问被拒绝；推荐无依据被拒绝；阶段推进由完成条件决定。

## PR-4 六阶段工作流编排与回退 ✅ 已完成

- 内容：`core/v50_workflow.py`：主线推进、模块按需调用计划、产物审核、完成条件、回退/重开及影响分析（证据、失效决策、重做产物）。
- 依据：ARCH §4–§6；技术报告 §3/§9。
- 验收：阶段≠模块；无证据不得回退；回退必须列出受影响决策与产物。

## PR-5 参数标定跨模块闭环 ✅ 已完成

- 内容：`modules/v50_calibration.py`：参数登记/目标/标定工况矩阵（M2）、版本化参数应用（M3）、真实任务证据（M4）、可信度诊断（M5）、误差与敏感性（M6）、用户确认与迭代历史。
- 依据：MOD §11；ARCH §4-S4；技术报告 §3.4。
- 验收：无 tool_task_id 不得入账；无目标/误差/接受标准不得标记已标定；失败如实记录；迭代需用户确认。

## PR-6 卡片交互适配与执行授权 ✅ 已完成

- 内容：`modules/v50_interaction.py`：复用 04 规范 Question/validate_card；单卡单决策、最多三卡；提交回写、反馈要求；执行卡单独授权。
- 依据：CARD §2–§10；HUMAN §12。
- 验收：卡片不绕过 Core 直接执行；执行确认卡无默认勾选/静默延后；提交解释影响。

## PR-7 测试与离线端到端演练 ✅ 已完成

- 内容：`tests/test_v50_*.py`；`examples/v50/full_stage_walkthrough.py`；全部旧回归复测。
- 验收：四规范可离线验收项全部有测试；端到端演练覆盖六阶段、回退、标定闭环；4.0 既有测试不回归。

## PR-8 文档与版本发布 ✅ 已完成

- 内容：SKILL.md 升 5.0.0；README/CHANGELOG/RELEASE；`docs/V50_ACCEPTANCE.md`；明确工具层/科学层未验证项。
- 验收：状态用语（已实现 / 接口通过 / 工具未验证 / 科学未验证）与证据一致。

## PR-9 打包与安装同步 ✅ 已完成

- 内容：打包 `pfc-interaction-v5.0.0.zip`（排除 .git/__pycache__/.sav）；同步 `~/.workbuddy/skills/pfc-interaction`；写工作日志。
- 验收：包内文件校验通过；安装目录与源码一致；Skill 元数据版本 5.0.0。

## PR-10 真实 bridge 在线补验 ✅ 已完成

- 内容：启动 PFC2D Console + bridge 0.6.17；运行 `tests/test_v40_tooling.py`；新增 `modules/v50_execution.py` 与 `tests/test_v50_execution.py`；`examples/v50/real_bridge_execution.py` 完成真实工具证据闭环。
- 验收：全量 140 条通过、0 跳过（PFC2D 与 PFC3D 均通过）；bridge 工具层 3 条真实通过；5.0 网关取得真实 `tool_task_id`；修复 FISH 回归的 2D 硬编码；科学层仍未通过。

## PR-11 讨论深度修复与三轴案例重划分 ✅ 已完成

- 内容：新增 `gate_for_card()` 内容维度深度门槛并接入卡片准备；三轴交互验证从 4 轮重划为 11 个子阶段，补上 S2c 观测指标决策。
- 验收：7 条新测试；全量 147 条通过、0 跳过；用户确认峰值强度+峰值应变+E50；报告 `outputs/v50_interaction_validation/triaxial_interaction_report.md`。

---

## 执行顺序与依赖

PR-0 → PR-1 → PR-2/PR-3 → PR-4 → PR-5/PR-6 → PR-7 → PR-8 → PR-9 → PR-10 → PR-11。

PR-5/PR-6 可并行；PR-7 需要 PR-1~PR-6 完成；PR-9 需要全部验收记录完成。

## 未纳入本次自动验收的项

真实 PFC2D/PFC3D 执行、桥在线状态、宏细观参数标定物理有效性、宿主 UI 徽章/窄屏视觉：需在具备环境时单独验收，不得因单元测试通过而宣称通过。
