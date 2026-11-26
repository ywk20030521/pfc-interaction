# 交互协议：七类语义与消息结构

Interaction 按科研协作过程组织，而非按"问答系统"组织。提问只是交互信号之一。

## 1. 七类交互语义

| 类型 | 方向 | 作用 | PFC 示例 |
|---|---|---|---|
| INFORM | Agent → Human | 告知当前事实与状态 | 当前计算步数、应力、应变、任务状态 |
| REPORT | Agent → Human | 阶段性总结与进展汇报 | 已完成压密，进入加载阶段 |
| EXPLAIN | Agent → Human | 结合证据解释现象 | 峰前裂纹增长加快，可能意味着损伤局部化 |
| DISCUSS | 双向 | 围绕现象和实验方向讨论 | 继续加载，还是改变加载速率 |
| QUERY / RESPOND | 双向 | 补足缺失信息或获取意见 | 询问围压目标，接收数值 |
| DECIDE / APPROVE | Human → Agent | 接收实验方向、参数决策或高风险授权 | 确认下一组参数、批准覆盖模型 |
| INTERRUPT / DIRECT | Human → Agent | 暂停、继续、终止或调整意图 | 暂停当前阶段，先检查接触异常 |

语义是逻辑分类，不要求每种对应一个 MCP 工具。宿主原生自然语言对话可承载大部分；结构化表单/按钮/审批只是特定场景的呈现方式。

## 2. 统一消息结构（逻辑字段，非强制 JSON）

无论通过哪个通道，一次交互应能表达：

- `interaction_kind`：七类语义之一；
- `experiment_id` / `stage_id` / `task_id`：关联到具体实验与阶段；
- `transport`：NATIVE_CHAT | AUQ | CONVERSATION_FALLBACK；
- `question`：问题内容，含背景与证据；
- `options` / `recommended`：可选项与 Agent 推荐（如有）；
- `response`：用户回答，含 response_type；
- `status`：WAITING | RESPONDED | DECIDED | CLOSED；
- `created_at` / `expires_at`：时间戳与过期控制；
- `evidence_level`：OBSERVED | EXECUTED | VERIFIED | INFERRED。

无需自建数据库持久化这些字段；它们是对话上下文与 Skill 行为中应保持的最小关联信息。

## 3. 用户响应类型

`ACCEPT`（接受建议）、`MODIFY`（修改参数/方案）、`REJECT`（拒绝并说明）、`ELABORATE`（要求解释）、`CUSTOM`（自定义方案）、`DEFER`（暂不决定）、`CANCEL`（取消）。

**规则**：
- 超时 ≠ REJECT；
- ACCEPT ≠ 执行授权；
- MODIFY / REJECT 后必须重新验证模型状态与方案版本；
- DEFER 时保留问题，不擅自继续高风险操作。

## 4. 决策与执行最小链路

```
接收回答 → 校验 interaction 有效性 → 关联实验/阶段/任务
→ 检查重复或过期 → 复述并结构化 → 形成 Decision
→ 检查权限与风险 → 查询当前 PFC 状态 → 必要时单独确认
→ 通过 itasca-mcp 执行 → 再次查询验证 → 向用户反馈 → 关闭 interaction
```

## 5. 防错清单

- 一个问题只走一个通道，禁止 Chat 与 AUQ 重复投递；
- 已回答/关闭的问题不接受迟到回答进入执行；
- 旧实验/旧方案版本的回答不得作用于新状态；
- 文件变化 ≠ 模型已加载；命令输入 ≠ 执行成功；执行返回 ≠ 物理状态达到。
