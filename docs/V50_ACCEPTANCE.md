# PFC Interaction 5.0 验收记录

**日期：** 2026-11-27（含 bridge 在线补验）  
**对象：** `pfc-interaction` 5.0.0（基于 4.0.0 升级）  
**基线：** `docs/PFCI-ARCH-5.0.md`、`PFCI-MOD-5.0.md`、`PFCI-HUMAN-5.0.md`、`PFCI-CARD-5.0.md`、`docs/PFC_Interaction_5.0_技术报告.md`

## 1. 测试执行

命令（技能根目录）：

```bash
python -m unittest discover -s tests -p "test_*.py"
```

结果（bridge 在线）：**147 条通过，0 条跳过**。其中：

- 既有 4.0/4.1 回归 98 条：未回归；
- 5.0 新增 36 条：
  - `tests/test_v50_core.py` 13 条：上下文/证据/参数状态、讨论质量、阶段推进与回退；
  - `tests/test_v50_decisions.py` 8 条：建议/确认/授权分离、版本失效、双通道去重、取消/超时/切换；
  - `tests/test_v50_calibration.py` 9 条：目标/矩阵/真实工具证据门槛/可信度/误差/接受标准/迭代上限；
  - `tests/test_v50_interaction.py` 6 条：卡片批次、面板渲染、提交反馈、执行授权边界；
  - `tests/test_v50_execution.py` 6 条：4.0 Envelope→5.0 module_result、授权失效/桥不可用不伪造 ID、真实桥接证据（在线时执行）；
  - `tests/test_v50_discussion_depth.py` 7 条：浅讨论不得转卡片、高影响档需两个备选、深度不足时准备卡片被拒绝。
- 工具层补验：`tests/test_v40_tooling.py` 3 条在 bridge 0.6.17 / PFC2D Console 上真实通过（PR-B3、PR-C1、健康检查）。

## 2. 离线端到端演练

```bash
python examples/v50/full_stage_walkthrough.py --out outputs/v50/walkthrough_report.json
```

结果：`OFFLINE_REPLAY_PASS`；覆盖 S1→S6 六阶段、两轮标定（首轮误差 0.14 超容差，调整后 0.05 达标）、参数确认、数据可信度诊断、误差与敏感性分析、证据驱动的 S6→S4 回退（1 个决策失效）。

报告关键字段：`current_stage=S4`、`evidence=12`、`transitions` 含 ENTER/COMPLETE/ROLLBACK、`acceptance_scope.real_pfc_tool_execution=NOT_EXECUTED_IN_THIS_SCRIPT`、`scientific_validation=NOT_VALIDATED`。

历史 `tool_task_id` 仅用于协议回放标识，**不构成此次真实执行证据**。

## 2.5 真实 bridge 补验（2026-11-27）

启动方式：PFC2D Console + `pr0/poc/start_bridge_p2d.dat`（`auto_upgrade=False`），工作目录 `D:\Python\itasca-mcp`。
健康检查：`status=success`、`version=0.6.17`、`runtime_mode=console`；真实 `execute_code` 往返返回 `pfc-91953ca2` 与输出 `PFC_BRIDGE_ROUNDTRIP 0`。

真实工具层证据（4.0 工具层，本次在线通过）：

- PR-B3：M3 生成的 sample-preparation `.dat` 经 Core I5 真实执行，`tool_task_id=pfc-d9040b69`，`state=COMPLETED`；
- PR-C1：M4 绑定真实 `tool_task_id=pfc-2c4e3299`，证据链 `decision→authorization→tool→evidence→artifact` 完整。

5.0 真实执行载体：

- 新增 `modules/v50_execution.py`：`ModuleResult` 统一接口（4.0 Envelope 转换）、`V50ModuleBus`（按需模块调用）、`V50ExecutionGateway`（Core 授权校验后调用真实 bridge）。
- `python examples/v50/real_bridge_execution.py --out outputs/v50/real_bridge_report.json` → `REAL_BRIDGE_PASS`；真实 `tool_task_id=pfc-1f2c971a`，脚本输出 `BALL_COUNT=10`，误差 0.0，S4 标定闭环（目标/工具证据/可信度/误差/接受标准/用户确认）全部通过。
- 报告明确标注 `real_pfc_tool_execution=PASS`、`protocol_and_evidence_chain=PASS`、`scientific_calibration=NOT_VALIDATED`：颗粒计数仅验证工具链与协议，不是物理标定。

## 2.6 PFC3D 复验（2026-11-27）

切换为 PFC3D Console + bridge 0.6.17（CWD 同上），以真实命令确认 3D 环境：六参数 domain extent 与 `ball create position=(0,0,0)` 成功，输出提示为 `pfc3d>`，探针 `pfc-f1058814` / `DIM3D_OK count=1`。

- 工具层：`tests/test_v40_tooling.py` 3 条在 PFC3D 上全部通过；PR-B3 `pfc-83413d94`、PR-C1 `pfc-1b82f099`，证据链完整。
- 5.0 执行载体：`examples/v50/real_bridge_execution.py --dimension 自动检测` → `REAL_BRIDGE_PASS`、`dimension=3D`、真实 `tool_task_id=pfc-b9f18288`、`BALL_COUNT=10` 误差 0。报告 `outputs/v50/real_bridge_report_3d.json`。
- 全量测试：**140 条通过、0 跳过**（PFC3D，补加深度门槛测试后为 147 条）。期间修复一个 2D 硬编码回归用例：`tests/test_v401_regressions.py` 的 FISH 块测试现在自动探测 2D/3D 并选择正确的 domain extent 与 position 格式，FISH 原生 splitter 行为不变。

结论：工具层与 5.0 执行载体在 **PFC2D 与 PFC3D 两种引擎上均通过**；科学层未因维度复验而改变状态。

## 2.7 三轴交互验证与讨论深度修复（2026-11-27）

- 初版交互验证为 4 轮粗粒度，用户反馈“讨论详细程度不够”。定位为：旧实现只禁止无分析追问，没有检查进入卡片前的理解/证据/备选/影响是否齐全。
- 修复：`core/v50_discussion.py` 新增 `gate_for_card()` / `require_depth()` 与 `DEPTH_PROFILES`，`modules/v50_interaction.py::prepare()` 接入后深度不足直接拒绝生成卡片；新增 7 条测试。
- 重新划分：三轴案例从 4 轮重划为 11 个子阶段（S1a–S6），并补上遗漏的 S2c 观测指标决策。用户确认采用“峰值强度 + 峰值应变 + E50”，峰后行为列为局限；报告见 `outputs/v50_interaction_validation/triaxial_interaction_report.md`（修订版）。
- 仍属宿主边界：面板不显示阶段/卡片类型 header、状态徽章、折叠依据与显式暂缓按钮；由对话正文补偿。

## 3. 规范验收映射

| 规范 | 验收项 | 结果 |
|---|---|---|
| ARCH 01 §12 | 单一 Skill、六阶段、阶段/模块分离、上下文、非固定问答、回退、跨模块标定、M4/M5/M6 分离、复用工具、状态区分 | 全部有代码与测试/演练证据 |
| MOD 02 §12 | 统一接口、对照组判断、M3 分层检查、M4 不复制执行器、M5/M6 边界、标定闭环 | 接口与协议项通过；逐模块六类案例仅部分覆盖 |
| HUMAN 03 §14 | 持续讨论、有依据建议、无固定问题数、双通道去重、AUQ 回退、状态分离、授权失效、异常证据、拒绝/暂缓不执行、工具反馈 | 全部有测试证据；宿主主动推送未验证 |
| CARD 04 §12 | 三类卡片、长度与数量、先讨论后结构化、推荐依据、来源/单位、状态分离、提交反馈、不绕过 Core | 全部有测试证据；徽章/窄屏属宿主边界 |

## 4. 未关闭项（不得宣称通过）

1. **科学层**：围压维持、胶结保留率、峰后采样与细观参数物理标定未通过；历史问题未关闭。
2. **bridge 并发**：同一 PFC Console 的 bridge 不支持并发测试；并行跑两套全量用例会造成 `SystemExit: 1` 状态污染，需重启 Console 后串行执行。本次最终 147 条结果为重启后串行复验。
2. **宿主 UI**：徽章、按钮文案、窄屏视觉由宿主面板决定。
3. **端到端真机科研案例**：规范要求在真实 PFC 环境完成至少一例完整科研任务（非协议颗粒计数），本次未执行。

已关闭：工具层（bridge 0.6.17 在线 3 条全通过）、5.0 执行载体（`module_result` 转换 + Core 授权网关 + 真实工具证据闭环）。

## 5. 结论

5.0 升级在**协议、离线逻辑与真实工具层**通过验收：四规范已入库，Core 五能力、六阶段工作流、参数标定跨模块闭环、双通道去重与卡片授权边界均已实现并有证据；4.0 回归无破坏；真实 PFC2D bridge 执行取得真实 `tool_task_id` 与证据链。

整体科研验收**仍未通过**：科学层物理标定未达标。状态表述统一为「协议层通过 / 工具层在线通过 / 科学层未通过」。
