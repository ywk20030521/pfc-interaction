# AUQ 集成（薄适配）

## 1. 定位

AUQ（ask-user-questions-mcp）是**正式的可选第二交互通道**，采用可选依赖、薄适配方式集成。它不是"备用提问工具"，也不是 PFC Interaction 的核心服务。基础功能不依赖它。

**安装事实（实测修正）**：AUQ 是 **npm 包 `auq-mcp-server`**（非 Python/PyPI 包），当前版本 3.4.0，FastMCP 实现。安装用 `npm install -g auq-mcp-server` 或 MCP 配置 `npx -y auq-mcp-server@3.4.0 server`。四份技术报告中"Python 包"的描述是错误的。详见 `pr0/AUQ_CAPABILITY_BASELINE.md`。

**真实 MCP 工具（仅 2 个）**：

- `ask_user_questions`：创建问题，参数 `questions`（1–5 题）、`nonBlocking`（默认 **false** = 阻塞等待；需要异步时显式设 `true`，返回 session_id）；
- `get_answered_questions`：取回答，参数 `session_id`（完整 UUID 或前 8 位短 ID）、`blocking`（默认 **false** 非阻塞，返回 pending 或答案）。

> 注意：CLI `auq answer <sessionId>` **只接受完整 UUID**（短 ID 报 Session not found），而 MCP 的 `get_answered_questions` 接受短 ID。异步流程中保存完整 UUID 更稳妥。MCP 工具级异步往返已实测通过（见 `pr0/AUQ_CAPABILITY_BASELINE.md` §5.1）。

CLI headless 等价命令：`auq ask '<json>'`（默认阻塞）、`auq answer <sessionId> --answers '...'`、`auq fetch-answers --unread`。实测已确认异步往返成立。

## 2. 复用与自持边界

**复用 AUQ 的能力**：
- 问题创建与排队；
- 单选、多选、自定义文本等结构化回答；
- 用户暂离时保留待回答问题；
- 通过 AUQ 自带 TUI/CLI 入口查看与回答；
- 获取回答、拒绝或补充说明（以目标版本实际支持为准）。

**PFC Interaction 自己负责**：
- 判断是否应向操作者提问；
- 决定问题走 Native Chat 还是 AUQ；
- 将实验上下文、问题目的和必要证据组织成清晰内容；
- 将 AUQ 回答重新放回 Agent 实验上下文；
- 校验回答是否完整、是否过期、是否与当前实验版本匹配；
- 将回答转化为实验决策，并在执行前完成澄清和授权检查。

**明确不做**：
- 不 fork 或重写 AUQ 的队列、Session、TUI；
- 不在 Skill 中另建一套平行问题数据库；
- 不把 AUQ Session 当实验工作流状态机；
- 不允许 AUQ 回答直接绕过 Agent 触发 PFC 执行；
- 不要求所有用户安装 AUQ；
- 不把 AUQ 的独立 TUI 扩展成自建 Web Dashboard。

## 3. 集成流程

1. **可用性检测**：检查 AUQ 是否安装、工具是否在宿主注册；不可用则走 Native Chat 并声明；
2. **工具核实**：以 PR0 锁定的目标版本实际工具 schema 为准，不假设 CLI 命令等于 MCP 工具；
3. **问题关联**：把 AUQ 问题与实验阶段、当前状态摘要、决策目的关联，记录最小元数据（`experiment_id`、`agent_run_id`、`itasca_task_id`、`interaction_kind`、`created_at`、版本/过期信息）；
4. **异步收集**：优先"创建问题后返回 / 稍后查询回答"的非阻塞模式，避免长时间阻塞等待；
5. **回答回填**：取回回答后放回 Agent 上下文，校验关联、完整性与时效性；
6. **异常处理**：超时、拒绝、过期回答、重复回答、Agent 重连、问题撤销分别处理；超时不自动转 REJECT；
7. **防重复投递**：同一待决事项只保留一个有效交互实例；Chat 已答不投 AUQ。

## 4. 回答的处理原则

AUQ 回答只是**用户输入证据**，不是执行指令。Agent 必须：

- 复述并结构化回答；
- 结合当前 PFC 状态重新解释与验证；
- 按 `decision_workflow.md` 完成授权检查后，才能通过 itasca-mcp 执行。

## 5. 安装体验

基础安装 = PFC Interaction Skill + 已配置的 itasca-mcp。AUQ 作为推荐的可选组件单独安装；安装后启用异步结构化交互。用户无需为使用基础功能启动独立 Web 服务。
