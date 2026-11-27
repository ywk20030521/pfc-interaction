# 交互运行时闸门：状态与验收

本文件修正"交互能力已实现"的笼统表述，区分协议、宿主通道与执行授权。
来源：`PFC_INTERACTION_FAILURE_DIAGNOSIS_2026-11-27.md`。

## 能力状态矩阵

| 能力 | 状态 | 依据 |
|---|---|---|
| 卡片数据生成与校验 | 已实现 | `modules/v50_interaction.py`，20 条既有测试 |
| 决策/授权状态模型 | 已实现 | `core/v50_decisions.py` |
| 宿主结构化提问通道 | 运行时探测，不假定可用 | `core/host_interaction.py` L0/L1/L2 |
| 卡片自动渲染与回写 | 参考实现，未端到端通过 | `assets/v510_cards.html` |
| 提问后强制停机 | 已实现（协议层） | `core/stop_protocol.py::require_user_decision()` |
| 正式 Run 授权闸门 | 交互侧已实现 | `core/stop_protocol.py::gate_formal_execution()` |
| Headless 执行前授权校验 | 由 `pfc-headless` PR 提供 | `pfc_headless.authorization` |
| 端到端宿主交互 | 未通过 | 宿主 UI 渲染与实际停机仍依赖 Agent/平台 |

## 最小 Native Chat 回合

即使没有 AUQ 与卡片 UI，关键参数缺失时 Agent 必须：

1. 复述当前理解；
2. 给出至少两个方案及各自影响；
3. 列出仍未确定的参数；
4. 只问最关键的一到三个问题；
5. 结束本轮等待用户回答（`stopped=True`）。

校验见 `minimum_native_chat_requirements()`；输出格式见 `GateResult.to_dict()`。

## 停机输出格式

```text
status: WAITING_FOR_USER
pending_decision_id: dec-...
question: 请先确认以下未定事项：...
allowed_next_action: none
```

用户回答后只更新上下文，不自动确认、不自动授权。恢复到 S2/S3 后必须重新计算
`context_version` 并重新请求确认。

## 正式 Run 授权链

1. 用户通过执行确认卡明确选择 `CONFIRM_EXECUTE`；
2. `InteractionCoordinator.authorize_execution()` 生成绑定操作/对象/版本的授权；
3. `gate_formal_execution()` 校验授权有效且版本未变；
4. `FormalRunAuthorization.to_headless_args()` 将授权字段传给
   `pfc-headless run prepare`；
5. `pfc-headless` 将元数据写入 Run 记录，并在提交前再次校验；
6. 无授权只能显式 `--pilot`，结果标记为 `UNACCEPTED_TECHNICAL_PILOT`，
   不得作为正式科研结论。

## 验收

`tests/test_interaction_runtime_gate.py` 8 条测试覆盖诊断报告 7 项条件：

- 参数不足时产生 `WAITING_FOR_USER` 且不执行；
- 待回答交互处于 `PENDING` 且未投递；
- 回答不确认、不授权、不执行；
- 明确执行卡 + 用户确认才生成授权；
- 无授权不能通过执行闸门；
- 上下文版本变化使授权失效；
- 同一事项与上下文版本不重复投递；
- Native Chat 最低回合内容校验。
