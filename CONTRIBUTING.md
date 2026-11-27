# 参与贡献

欢迎参与 PFC Interaction Skill 的建设。本仓库是科研协作的**唯一用户入口与总协调者**，请让改动留在该边界内。

## 职责边界

本 Skill 负责：科研讨论与议题树、研究计划与实验设计组织、决策与授权记录、跨会话上下文恢复、对其他 Skill 的调度、结果解释与用户审查。

本 Skill **不负责**：连接或控制 PFC Console；维护底层 Run 状态机；原始数据；派生量、统计、图表与 Viewer；正式 Hypothesis / Validation / Evidence / Finding 的登记。相关能力分别属于 Execution、Visualization 与规划中的 Research Evidence Skill。

## 开始前

- Python 3.10+；单元测试不需要真实 PFC。
- 先阅读 `SKILL.md`、`README.md`、`RELEASE.md` 与 `docs/OPEN_SOURCE_READINESS.md`。
- 注意：`main` 上的版本基线与工作区中尚未提交的 5.2.0 S4 代码并不一致，提交前确认你基于哪条基线。

## 开发与测试

```bash
python -m unittest discover -s tests -p "test_*.py"
```

bridge 在线时的结果才可标记为工具层通过；离线跳过的用例必须如实记录，不得写成“全部通过”。修改 Core / 模块契约时同步更新 `references/` 与 `docs/`。

## 科研诚信规则

1. 能力状态使用统一词条：`IMPLEMENTED` / `TESTED` / `REAL_ENV_VERIFIED` / `NOT_VERIFIED` / `NOT_IMPLEMENTED` / `DEPRECATED`；`TESTED` 不等于 `REAL_ENV_VERIFIED`。
2. 用户的回答不等于确认，确认不等于授权；执行授权必须来自明确的执行确认卡并绑定版本与上下文。
3. 关键参数缺失或仅为 Agent 假设时必须停机等待，不得“合理假设后继续”。
4. `NOT_RUN` / `UNKNOWN` / `WARNING` 不得转 `PASS`；`CONFIRMED` 是决策状态，不是科学验证。
5. S4 参数标定是对话与协商协议层，不得产出正式 Validation / Finding / Evidence，也不得宣称定量标定成功。
6. 宿主是否提供结构化提问通道必须每次会话探测；不得把某个宿主的能力外推到其他宿主，不得声称未投递的问题“已投递”。

## Pull Request

- 从 `main` 建短分支（`fix/...`、`docs/...`、`feat/...`），向 `main` 提 PR。
- 完整填写 `.github/PULL_REQUEST_TEMPLATE.md`。
- 行为改动必须附带测试；文档、验收记录与 `CHANGELOG.md` 同 PR 更新。
- 写明验证命令与结果；真实 PFC / 宿主证据单独列出，无证据则标 `NOT_VERIFIED`。
- 不要把安全闸门改动与无关文档整理混在一个 PR。

## Issue

使用 bug / feature 模板，提供精确命令、Python 版本、bridge 与宿主信息、可观察证据。不要上传含专有参数或真实岩样数据的文件。

## 安全

可利用缺陷请按 `SECURITY.md` 私下报告，不要公开 Issue。

## 行为准则

参与即表示遵守 `CODE_OF_CONDUCT.md`。

## 许可

贡献内容按 `LICENSE`（MIT）授权。
