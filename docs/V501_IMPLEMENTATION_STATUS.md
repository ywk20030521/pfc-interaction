# PFC Interaction 5.0.1 实现状态矩阵

**规则：** 五份 5.0.1 文件是目标规范，不代表能力已实现。本表只记录当前代码与测试证据。

| 规范条款 | 状态 | 实现/证据 |
|---|---|---|
| PFCI-ARCH-5.0.1 §4 Research Issue 对象模型 | 已实现 | `core/v501_issues.py`：16 类议题、11 种状态、P0–P3、依赖、重开/失效 |
| PFCI-ARCH-5.0.1 §7 迭代与回退 | 已实现 | `IssueTree.reopen()` / `ChangeManager.analyze()`；重开保留版本与历史 |
| PFCI-ARCH-5.0.1 §8 科研档案 | 已实现（生成层） | `core/v501_archive.py` 生成 15 类文件 + archive_index；内容真实性依赖上游数据 |
| PFCI-HUMAN-5.0.1 §3 D0–D3 深度 | 已实现 | `core/v501_deep_discussion.py`；D2/D3 必须完成实质阶段，首轮不得定案 |
| PFCI-HUMAN-5.0.1 §5 讨论模式 | 已实现（协议层） | 8 种模式枚举与 cycle 记录；模式自动选择策略未实现 |
| PFCI-HUMAN-5.0.1 §7 用户专业知识 | 部分 | `EvidenceClass.USER_EXPERIENCE` 登记且不升格为事实；主动提问策略由 Agent 对话执行 |
| PFCI-HUMAN-5.0.1 §9 长期记忆 | 部分 | 结构化档案可生成；跨会话自动恢复未实现，需宿主上下文/文件重读 |
| PFCI-HUMAN-5.0.1 §11 科研成熟度 | 已实现 | `Maturity` 八状态 + `HypothesisManager`；CONFIRMED ≠ VALIDATED |
| PFCI-CARD-5.0.1 §3 五类卡片 | 已实现 | `modules/v501_cards.py`；参数单位/来源、授权版本绑定、检查点证据校验 |
| PFCI-CARD-5.0.1 §7 提交回写 | 已实现（接口层） | `submit()` 返回 `requires_issue_writeback` / `requires_archive_writeback`，实际写入由 Core 调用档案管理器 |
| PFCI-MOD-5.0.1 §3 模块深度模式 | 部分 | 深度讨论引擎提供流程骨架；M1–M6 未逐一包装为 v501 深度模块 |
| 真实 PFC 工具证据 | 工具层在线通过 | 5.0/5.0.1 验收共 21 个真实 tool_task_id（PFC3D） |
| 科学有效性 | 未通过 | 复杂课题中围压未建立，假设 UNRESOLVED |

## 未实现或限制

- 讨论模式自动路由、跨会话恢复、宿主 UI 渲染、M1–M6 的 v501 深度模块包装。
- 不新增 Web/数据库服务；档案为 Markdown/JSON/CSV。
- 本版本不重新宣称物理标定通过。
