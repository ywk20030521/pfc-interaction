# AUQ（ask-user-questions-mcp）能力基线（PR0/PR4）

**版本：** 0.2（实测更新）  
**日期：** 2026-11-25  
**状态：** 已安装并实测核心异步能力；MCP 工具已注册待会话重启生效  
**仓库：** https://github.com/paulp-o/ask-user-questions-mcp

---

## 1. 重大修正：AUQ 是 npm 包，不是 Python 包

**这是四份技术报告的根本性错误。** V0.x / V3.x 都把 AUQ 当作 Python MCP 讨论（暗示 pip/uvx 安装），实际：

| 项目 | 报告假设 | 实测事实 |
|---|---|---|
| 生态系统 | Python / PyPI | **npm** |
| 包名 | `ask-user-questions-mcp` | **`auq-mcp-server`** |
| 安装 | pip / uvx | `npm install -g auq-mcp-server` 或 `npx -y auq-mcp-server` |
| 本机 pip 查询 | 未安装 | 本就不存在此 PyPI 包（`uvx` 解析失败已证实） |
| 实现框架 | 未说明 | FastMCP（TypeScript） |
| 版本 | 未锁定 | **3.4.0**（MCP server 内部自称 0.1.17） |

**修正动作**：已把 `~/.workbuddy/mcp.json` 注册为 `npx -y auq-mcp-server@3.4.0 server`（stdio），保留其他 server 不变。新 server 需重启/信任后才在当前会话生效。

## 2. 真实 MCP 工具清单（源码级核实，A2）

`dist/src/server.js` 只注册 **2 个工具**（不是 README 暗示的多工具）：

| 工具名 | 作用 | 关键参数 |
|---|---|---|
| `ask_user_questions` | 创建问题 | `questions`、`nonBlocking`（关键！） |
| `get_answered_questions` | 取回答 | `session_id`、`blocking` |

**核心结论：V3.1 §4.2 "非阻塞回答获取待验证" 已关闭——`nonBlocking` 参数真实存在。** `get_answered_questions` 的 `blocking` 可选，默认非阻塞。

## 3. 实测结果（A1–A5 通过）

| 编号 | 验证项 | 实测证据 | 结论 |
|---|---|---|---|
| A1 | 锁定版本 | `auq --version` → v3.4.0；npx 缓存路径已记录 | 通过 |
| A2 | 工具清单 | server.js 源码：2 个工具 + nonBlocking/blocking 参数 | 通过 |
| A3 | 非阻塞创建 + 稍后取回答 | `ask` 创建 session `e2034739`（pending）→ 稍后 `answer` → `fetch-answers` 返回 "→ linear" | 通过 |
| A4 | 回答关联原 question | fetch 返回完整问题"选择接触模型"与答案 `linear`，session_id 正确 | 通过 |
| A5 | 拒绝 + 理由 | `answer --reject --reason "需要更多模型证据"` → status=rejected；fetch 正确显示理由 | 通过 |
| A5b | unread 队列语义 | 回答后 `fetch-answers --unread` 返回 "No unread sessions" | 通过 |

**关键实测细节**：

- `auq ask '<raw JSON>'` 默认**阻塞**启动 TUI（本次自动转后台）；MCP 的 `ask_user_questions` 需用 `nonBlocking:true` 才不阻塞；
- CLI headless 回答：`auq answer <sessionId> --answers '{"0":{"selectedOption":"linear"}}'`；
- 支持 multiSelect：`{"0":{"selectedOptions":["A","B"]}}`、自定义文本 `{"0":{"customText":"..."}}`；
- `auq fetch-answers --unread` / `<sessionId>` / `--blocking` 三种取法；
- 会话持久化在全局目录，跨进程可见（sessions list 显示 2 个 pending 会话）；
- 会话状态：pending / completed / rejected。

## 4. 对 Skill 设计的影响（已同步）

1. **AUQ 的异步能力成立**：V3.1 的"创建问题—持久化—稍后取回"模式可用，无需自建队列；
2. **薄适配边界不变**：Skill 仍负责是否提问、选 Chat 还是 AUQ、组织问题内容、把回答放回 Agent 上下文、校验过期与版本、转化为决策；AUQ 只管传递与保存；
3. **MCP 工具名明确**：`ask_user_questions` + `get_answered_questions`，Skill 文档不应再写模糊的"AUQ MCP 能力"；
4. **nonBlocking 必用**：调用 `ask_user_questions` 必须设 `nonBlocking:true`，否则阻塞等待用户，违背异步设计；
5. **标识关联**：AUQ 的 session_id（UUID）与 experiment_id / agent_run_id / itasca_task_id 的映射由 Skill 维护。

## 5. 剩余待验证

| 编号 | 验证项 | 状态 |
|---|---|---|
| A6 | Chat 与 AUQ 协同：同一事项不重复投递 | 需 MCP 会话重启后在真实 Agent 流程验证 |
| A7 | Agent 重连后问题恢复 | 会话持久化已确认（sessions list 跨进程可见），重连取回答已通过 A3 |
| A8 | MCP 工具在 WorkBuddy 会话中实际可用 | **分层判定**：①工具层**实测通过**（MCP stdio 协议 `tools/list` 返回 2 个工具真实 schema；nonBlocking 创建→待答→回答→取回完整往返跑通）；②宿主会话可见性**未通过**（ToolSearch 查 `ask_user_questions` 无结果，需重启/信任）。工具本身可用 ≠ 宿主已加载。 |

### 5.1 MCP 协议级实测补充（2026-11-25 20:10）

直接以 stdio 协议启动 `auq-mcp-server@3.4.0` 并调用：

- `initialize` → serverInfo `AskUserQuestions` / `0.1.17`，capabilities 含 tools/logging/completions；
- `tools/list` → 2 个工具，真实 schema 如下；
- `ask_user_questions(nonBlocking:true)` → 返回 `[Session: 68cfd0e6 | Status: pending]`；
- `get_answered_questions(session_id:"68cfd0e6", blocking:false)` → 回答前返回 "No answers yet"（**不阻塞**）；
- CLI `auq answer <完整UUID> --answers '{"0":{"selectedOption":"linear"}}'` → status=completed；
- 再次 `get_answered_questions` → 返回 "选择接触模型 → linear — 线性接触"。

**schema 修正（相对此前文档）**：

| 项 | 此前文档 | 实测 schema |
|---|---|---|
| `nonBlocking` 默认值 | 写成"必设 true" | 默认 **false**（阻塞）；异步时才设 true |
| session_id 格式 | 未说明 | `get_answered_questions` 接受完整 UUID 或前 8 位短 ID；**CLI `answer` 只接受完整 UUID**（短 ID 报 Session not found） |
| 问题数量 | 未说明 | 1–5 题，每题 2–5 选项，title ≤12 字符 |
| session 存储 | 未说明 | `%APPDATA%\auq\sessions\<UUID>` |

**结论**：AUQ 工具实现完整、异步机制成立；A8 剩余阻塞仅在"宿主会话是否加载该 MCP server"，需用户重启/信任。

## 6. 结论

AUQ 3.4.0 已安装核实，**核心异步能力全部通过实测**（A1–A5）。这是 PR4 的关键进展：V3.1 中悬而未决的"AUQ 能否非阻塞异步往返"现有确定答案——可以。同时修正了四份报告"AUQ 是 Python 包"的错误。

剩余 A6/A8 需 MCP 会话重启后在真实 Agent 流程中验证，不影响 Skill 文档定稿。
