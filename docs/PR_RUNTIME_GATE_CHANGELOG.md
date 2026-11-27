# PR — 交互运行时闸门（Runtime Gate / Stop Protocol）

**分支：** `fix/interaction-runtime-gate`
**目标仓库：** `ywk20030521/pfc-interaction`
**日期：** 2026-11-27
**状态：** 可合并（单元测试 178/178 通过；真实宿主 UI 未验证）

---

## 1. 变更动机

`PFC_INTERACTION_FAILURE_DIAGNOSIS_2026-11-27` 指出：卡片数据生成与校验通过，但 Agent 未停机、宿主未显示卡片、执行链未校验授权；“协议测试通过”被误读为“用户交互已端到端通过”。本 PR 把“先提问、后执行”做成运行时边界，而不是行为说明。

## 2. 目标 / 非目标

**目标**

- 关键参数缺失或仅为 Agent 假设时，返回 `WAITING_FOR_USER` 且 `allowed_next_action: none`。
- 每次会话探测宿主能力 L0/L1/L2；没有结构化提问回调时返回 `PENDING_NATIVE_CHAT`、`delivered=False`，不声称已投递。
- 用户回答只更新上下文，不自动确认、不自动授权；仅明确执行卡 + 用户确认可生成授权。
- 上下文版本变化使既有授权失效；同一事项同一版本不重复投递。
- 产出与 `pfc-headless` 授权闸门对齐的字段映射。

**非目标**

- 不实现宿主 UI 渲染（HTML 仍为参考实现）。
- 不调用 `itasca-mcp` / PFC，不创建正式 Run。
- 不修改 AUQ 部署与 MCP 注册。
- 不宣称端到端宿主交互已通过。

## 3. 文件变更

| 文件 | 变更 |
|---|---|
| `core/host_interaction.py` | 新增：`probe_host_capability()`、`HostInteractionAdapter.ask()`、`AskOutcome`、`attach_host_ask()`；L0/L1/L2 分级与去重 |
| `core/stop_protocol.py` | 新增：`require_user_decision()`、`minimum_native_chat_requirements()`、`FormalRunAuthorization`、`gate_formal_execution()`；版本失效语义 |
| `tests/test_interaction_runtime_gate.py` | 新增 8 条运行时闸门验收测试 |
| `docs/INTERACTION_RUNTIME_GATE.md` | 新增能力状态矩阵、停机输出格式、授权链与验证结果 |
| `references/interaction_transport_policy.md` | 修正“当前宿主已实测可用”的外推表述，改为每次会话重新探测 |
| `README.md` / `SKILL.md` | 补充交互与执行边界、能力状态分层 |
| `benchmarks/benchmark_runtime_gate.py` | 新增可复现性能基准脚本 |
| `benchmarks/results.json` / `benchmarks/PERFORMANCE_REPORT.md` | 新增基准原始数据与分析报告 |
| `docs/PR_RUNTIME_GATE_CHANGELOG.md` | 本文档 |

## 4. 行为变更（破坏性说明）

- 缺少关键参数时不再“合理假设后继续”，而是停机等待用户；调用方必须处理 `WAITING_FOR_USER`。
- `ask()` 不再返回“已投递”；无宿主结构化通道时返回 `PENDING_NATIVE_CHAT`，Agent 必须在 Native Chat 提问并结束本轮。
- 同一 `research_task_id + stage_id + decision_topic + context_version` 的重复提问被阻塞为 `BLOCKED_DUPLICATE`。
- 执行授权必须来自明确的执行确认卡，且绑定模型/参数/矩阵版本；上下文变化后需重新确认。

## 5. 验证结果

### 5.1 单元测试

```
python -m unittest discover -s tests -v
Ran 178 tests in 34.716s
OK
```

新增 8 条闸门测试全部通过，覆盖诊断报告 §7 的七项条件与 Native Chat 最低回合校验。
既有协议测试（20 条）保持通过。

### 5.2 性能检测

```
python benchmarks/benchmark_runtime_gate.py --rounds 5
```

- 参数缺失停机：均值 **0.0180 ms**（P95 0.0260 ms）。
- Native Chat 待答 / 结构化投递：均值 **0.0243 / 0.0332 ms**。
- 授权生成 + 执行闸门：均值 **0.0778 ms**（P95 0.1198 ms）。
- 版本变化失效：均值 **0.0731 ms**。
- 10 个场景、17,500 次调用：**0 次非预期异常、输出全部确定、无单调内存增长**。
- 详情见 `benchmarks/PERFORMANCE_REPORT.md`。

### 5.3 未验证项

- 宿主 UI 是否真实渲染卡片并回写答案：未验证。
- Agent 在不同宿主中是否确实执行停机：未验证（需要宿主/Agent 层验收）。
- 真实 PFC 跨 Skill 授权链端到端：由 `pfc-headless` 闸门 PR 配套后另行验证。

## 6. 风险与回滚

| 风险 | 缓解 |
|---|---|
| Agent 不处理 `WAITING_FOR_USER` 仍继续调用工具 | 需宿主/Agent 层验收；本 PR 提供协议与返回结构，不替代平台约束 |
| 宿主无结构化通道导致交互体验退化 | 明确回退 Native Chat，并要求最低回合内容 |
| 历史文档“宿主已实测可用”被误用 | 已修正为按会话探测，禁止跨宿主外推 |
| 去重键只在实例内有效 | 已列为跨会话持久化改进项（P1） |

**回滚**：回退本分支提交即恢复原有纯协议行为；回滚后停机与授权边界消失，不建议在真实科研环境长期回滚。

## 7. 合并检查清单

- [x] 变更有明确问题来源与边界说明
- [x] 文档（README / SKILL / policy / docs）同步更新
- [x] 全套单元测试通过（178/178）
- [x] 关键场景性能与稳定性已记录
- [x] 与 `pfc-headless` 授权字段一一对应
- [x] 未验证的宿主 UI / 端到端交互如实标注
- [x] 能力状态表述拆分（协议 / 宿主通道 / UI / 闸门 / 端到端）
