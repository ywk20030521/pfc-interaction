# PFC Interaction Skill 5.1.0

面向 Itasca PFC2D/PFC3D 数值模拟的持续科研协作 Skill。一个 Skill、一个协作主体：Agent 主持科研讨论，用户保留科学决策权，专业模块 M1–M6 按需调用，底层复用 itasca-mcp / Bridge 与 Scientific Visualization Skill。

5.1 将 Skill 从「会按流程协作」升级为「可持续深度科研协作系统」：以科研议题为核心，支持 D0–D3 实质讨论、证据/假设/决策成熟度、跨会话恢复、讨论模式自动路由、M1–M6 深度包装、五类结构化卡片和可复用科学层闸门。用户可见的是 S1–S6 六阶段，而不是六个独立模块。

## 核心特性

- **六阶段工作流**：S1 研究对象与目标 → S2 实验设计 → S3 建模路线 → S4 参数标定 → S5 仿真执行与异常干预 → S6 结果分析；支持有证据的回退与影响分析。
- **Core 五能力**：统一科研上下文、持续讨论管理、证据化方案建议、决策与授权管理、工作流编排；阶段/模块/讨论/决策/执行状态彼此分离。
- **持续科研讨论**：无固定问题数；D0–D3 深度等级按议题复杂度要求实质阶段，D2/D3 不得首轮定案；反方审查、用户修正、方案修订和验证计划都可追溯。
- **科研议题与档案**：议题树、优先级队列、依赖、重开/失效；证据八分类、假设成熟度、决策与科研成熟度分离；课题级档案自动生成。
- **五类结构化卡片**：讨论收敛、参数登记、方案确认、执行授权、检查点决策；卡片绑定议题并通过深度门槛，不绕过 Core。
- **决策与授权**：讨论 → 确认 → 授权 → 执行 → 验证严格分离；授权绑定操作、对象、模型/参数/工况版本与上下文版本，变更即失效。
- **参数标定闭环**：M2 目标与矩阵、M3 参数版本、M4 真实工具证据、M5 数据可信度、M6 误差与敏感性、用户确认；拒绝伪造执行与未验证标定。
- **双通道与卡片**：Native Chat 默认，AUQ 可选且有事项级去重；三类提问卡片遵循 PFCI-CARD-5.0，卡片不绕过 Core 触发执行。
- **向后兼容**：4.0 六模块契约、v41 阶段门与提问卡片 V2 保持可用。

## 强制规范

四份规范位于 `docs/`，构成 5.0 强制约束：`PFCI-ARCH-5.0.md`、`PFCI-MOD-5.0.md`、`PFCI-HUMAN-5.0.md`、`PFCI-CARD-5.0.md`；总索引见 `docs/README_四规范总索引.md`。目标架构见 `docs/PFC_Interaction_5.0_技术报告.md`。规范描述的目标能力不自动等于已实现能力，状态见 `docs/V50_IMPLEMENTATION_STATUS.md`。

## 安装

需要 Python 3.10+、itasca-mcp 与可用的 PFC 引擎（PFC2D 或 PFC3D）。

```bash
git clone https://github.com/ywk20030521/pfc-interaction.git
```

将 `pfc-interaction/` 目录放入 WorkBuddy 的用户级或项目级 skills 目录。运行时只需 `SKILL.md` 与 `references/`；`docs/` 按需读取。

## 快速开始

在 WorkBuddy 中直接描述 PFC 科研任务，例如：

> 用三轴压缩实验研究围压对胶结颗粒集合体峰值强度的影响，围压 1/5/10 MPa。

Skill 会先讨论研究目标与实验设计，再按需调用建模/执行/诊断/分析能力；每次需要用户决策或授权时会明确说明背景、证据、建议与影响。

演练脚本：

```bash
python examples/v501/complex_case_replay.py --out ./replay_report.json        # 5.0.1 复杂课题回放
python examples/v50/full_stage_walkthrough.py --out ./walkthrough_report.json  # 5.0 六阶段离线回放
python examples/v50/real_bridge_execution.py --out ./real_bridge_report.json   # 5.0 真实 bridge 协议验收
python examples/v41/triaxial_longitudinal_slice.py                             # 三轴纵向闭环回放
python examples/v40/full_research_loop.py                                      # 4.0 完整科研案例
```

## 目录结构

```
pfc-interaction/
├── SKILL.md                  # 5.0 Skill 入口与运行时规则
├── core/                     # 4.0 IF0 + 5.0 五能力 + 5.0.1 议题/讨论/证据/档案（v50_*/v501_*）
├── adapters/itasca_mcp.py    # 真实执行适配器（Core I5 → bridge HTTP）
├── modules/                  # M1–M6 + 5.0 标定/交互/执行 + 5.0.1 五类卡片（v50_*/v501_*）
├── references/               # 运行时按需读取的语义规范
├── templates/                # 状态汇报、参数协商、异常报告模板
├── tests/                    # 4.0/5.0/5.1 回归与协议验收
├── examples/                 # 端到端演示与验收脚本（v50/、v501/、v510/）
├── assets/                   # 五类卡片 UI 渲染参考
├── docs/                     # 五份规范、技术报告、PR 台账与验收记录
└── pr0/                      # 上游能力基线与 PoC
```

## 测试

```bash
python -m unittest discover -s tests -p "test_*.py"
```

bridge 在线时 **170 条全部通过（0 跳过）**：98 条既有 4.0/4.1 回归 + 42 条 5.0 协议/执行载体验收 + 14 条 5.0.1 议题/深度讨论/证据/卡片协议 + 7 条讨论深度门槛测试 + 9 条 5.1 发布测试。科学层另有三工况真实 PFC3D 验收（69 个 tool_task_id）。离线时 4 条工具用例自动跳过。启动 bridge：用 `pr0/poc/start_bridge_p2d.dat` 或 `start_bridge_p3d.dat` 启动对应 Console。

## 已知边界

- **科学层机制比较通过**：围压控制已修复，三工况数据有效；材料参数定量标定不在 5.1 范围，pb_ten 仍为经验初值。
- **工具层在线通过**：bridge 0.6.17 / PFC2D 与 PFC3D Console 真实往返通过；无真实 ID 一律 BLOCKED。
- **宿主 UI**：Skill 提供完整五类卡片渲染参考，最终视觉仍由宿主面板决定。

状态用语分层：`已实现` / `接口层通过` / `协议层通过` / `工具层在线通过` / `科学层机制比较通过` / `定量标定不在范围`。

## 许可

MIT — 详见 [LICENSE](LICENSE)。
