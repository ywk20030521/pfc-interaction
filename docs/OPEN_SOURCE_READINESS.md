# 开源就绪度与三大 Skill 标准对接

**仓库：** `ywk20030521/pfc-interaction`
**日期：** 2026-11-27
**标准来源：** PFC-SRA-ARCH-001 / ARCH-002 / REM-001 与总体规划 §3.3
**状态键：** `PASS` 已在 `main`；`ADDED IN THIS PR`；`PARTIAL` 部分具备；`GAP` 缺失。

## 1. GitHub 仓库配置

| # | 要求 | 标准来源 | 当前符合情况 | 需补齐项 | 优先级 |
|---|---|---|---|---|---|
| 1 | MIT LICENSE | GitHub 开源基线 | `PASS` | 无 | — |
| 2 | README（定位、边界、测试） | ARCH-002 §1.1 | `PASS` | 增加贡献/准则/发布入口链接 | P2 |
| 3 | CONTRIBUTING | GitHub 开源基线 | `ADDED IN THIS PR` | 含科研诚信规则 | — |
| 4 | 行为准则 | GitHub 开源基线 | `ADDED IN THIS PR` | 无 | — |
| 5 | 安全策略 | GitHub 开源基线 | `ADDED IN THIS PR` | 无 | — |
| 6 | Issue 模板 | GitHub 开源基线 | `ADDED IN THIS PR` | 无 | — |
| 7 | PR 模板 | GitHub 开源基线 | `ADDED IN THIS PR` | 无 | — |
| 8 | CHANGELOG | GitHub 开源基线 | `PASS` | 本次补 `[未发布]` 条目 | P1 |
| 9 | 发布说明配置 + 草稿 | GitHub 开源基线 | `ADDED IN THIS PR` | 阻断项关闭前不得发布 | P0 |
| 10 | tag 与公开 Release | GitHub 开源基线 | `GAP` — 无 tag / Release | 建议 `v5.2.0`，须先关闭阻断项；本 PR 不创建 | P0 |
| 11 | 版本策略 | SemVer / Keep a Changelog | `ADDED IN THIS PR` | 无 | — |

## 2. 三大 Skill 标准逐项对接

| 标准项 | 要求 | 当前符合情况 | 需补齐项 | 优先级 |
|---|---|---|---|---|
| ARCH-002 §3 唯一入口 | 用户交互、决策、跨 Skill 调用必须经 Interaction | `PASS` — 架构层如此声明 | 持续评审，防止新增旁路 | — |
| ARCH-002 §3 规则 5 执行闸门 | 正式 Run 携带绑定授权，版本变化即失效；无授权只能 `--pilot` | `GAP` 在 `main`；PR #1 已实现交互侧 | 合并 PR #1，与 Headless 闸门同批发布 | **P0** |
| ARCH-002 §3 规则 6 状态诚实 | 六个状态彼此分离；未知保留 `UNKNOWN` | `PARTIAL` — README 有分层用语 | 在 `SKILL.md` 与验收报告中统一六词条 | P1 |
| ARCH-002 §3 规则 7 验证诚实 | `NOT_RUN/UNKNOWN/WARNING` 不转 `PASS` | `PASS`（协议层） | 保持测试覆盖 | — |
| ARCH-002 §3 规则 8 建议与决策分离 | 回答不确认、确认不授权 | `PASS` — 20 条协议测试与 8 条闸门测试 | 合并闸门 PR 后复验 | P0 |
| ARCH-002 §3 规则 9 幂等 | 每次调用带 `request_id` + `idempotency_key` | `GAP` — 仅内部去重，无共享信封 | 定义 `pfc.skill-invocation@1.0.0`（REM-001 R11） | P1 |
| ARCH-002 §3 规则 12 能力状态 | 六态标注，TESTED ≠ REAL_ENV_VERIFIED | `PARTIAL` — 文档用中文分层表述 | 增加六态映射表 | P1 |
| REM-001 R02 物理闸门越权 | 峰值强度许可降级为技术信号 | `GAP` 在 `main`；整改工作树已修复并验证 179 条 | 合并整改，修正旧回放脚本文本 | **P0** |
| REM-001 R08 S4 侵入 RE | S4 不得产出 Validation / Evidence / Finding | `GAP` — 5.2.0 工作树未合并 | 在 `docs/S4_SPEC.md` 明示协议层定位；RE 建成后改适配层 | P1 |
| REM-001 R09 自建执行载体 | 改为调用 Execution 标准请求 | `GAP` — `v50_execution.py` 仍直接执行 | 改为薄适配器；同步修改直连桥示例 | P1 |
| REM-001 R01 授权握手单侧 | 两侧字段对齐并同步安装 | `GAP` — 两个 PR 未合并、安装目录无闸门 | 同批合并、同步安装包、端到端演练 | **P0** |

## 3. 发布结论

`main` 已包含 5.2.0 S4 子系统，但仍缺少运行时闸门 PR（#1）与 R02 物理闸门整改，
且宿主 UI 端到端交互未通过。**不得从当前 `main` 打 `v5.2.0` tag 或发布 Release。**
本 PR 只添加仓库配置与发布物料，不改变运行时行为。

## 4. 本 PR 验证

```text
python -m unittest discover -s tests -p "test_*.py"
# Ran 219 tests in 34.782s ... OK（bridge 在线，rebase 到 5.2.0 后）
```

未修改运行时代码、测试或契约。运行时闸门 PR（#1）保持独立且未合并。
