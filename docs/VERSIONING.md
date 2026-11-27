# 版本与发布流程

## 版本方案

采用 [Semantic Versioning](https://semver.org/)：`MAJOR.MINOR.PATCH`，tag 前缀 `v`。

- `MAJOR`：六阶段、Core 契约或 IF0 接口破坏性变化。
- `MINOR`：新增模块/能力且向后兼容（如 5.1 → 5.2 的 S4 子系统）。
- `PATCH`：缺陷修复与文档修订，不改变协议。

预发布使用 `v5.2.0-rc.1`，并在 GitHub 上标记为 pre-release。

## 当前状态

- `main`：`5.2.0`（`SKILL.md` frontmatter；S4 子系统已合并）。
- 运行时闸门 PR（#1）与 R02 物理闸门整改：尚未合并。
- 首个建议 tag：`v5.2.0`，**未创建且被阻断**；见 `docs/RELEASE_NOTES_DRAFT.md`。

## 发布清单

1. 关闭 `docs/OPEN_SOURCE_READINESS.md` 中所有 P0 项并合并到 `main`。
2. 运行 `python -m unittest discover -s tests -p "test_*.py"`，记录通过数、跳过数与真实工具证据。
3. 在 `CHANGELOG.md` 把 `[未发布]` 条目移入版本段落并写明日期。
4. 定稿 `docs/RELEASE_NOTES_DRAFT.md`，同步 `RELEASE.md` 的兼容矩阵与已知限制。
5. 确认安装目录（WorkBuddy / Codex）已同步同一提交。
6. 从已验证提交创建 tag，再创建 GitHub Release。

## 禁止

- 不得从含有授权旁路的提交打 tag。
- 不得把协议层通过写成宿主端到端通过。
- 不得在 Release notes 中宣称只存在于未合并分支的能力。
