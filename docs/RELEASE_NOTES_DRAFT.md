# 发布说明草稿（未发布）

**仓库：** `ywk20030521/pfc-interaction`
**建议 tag：** `v5.2.0` — **尚未创建**
**状态：** `DRAFT / BLOCKED`
**日期：** 2026-11-27

## 1. 状态说明

本文件是首个公开 tag 的发布说明草稿。**当前 `main` 已为 5.2.0**
（`SKILL.md` 中 `version: 5.2.0`；S4 子系统已合并），但运行时闸门与物理闸门
整改仍未合并。因此本草稿不得作为已发布说明引用。

## 2. 发布阻断项

| 阻断项 | 依据 | 需要的动作 |
|---|---|---|
| 物理闸门越权整改未合并 | REM-001 R02：`core/v510_physics.py` 尚无 `claim_authority` / `scientific_validation` 标记 | 合并整改，修正旧回放脚本文本 |
| 运行时闸门 PR 未合并 | `fix/interaction-runtime-gate` (#1)：宿主探测、停机协议、授权闸门 | 合并后重跑 178+ 测试 |
| 与 Headless 授权接收端联调未完成 | REM-001 R01：交互侧字段已生成，Headless 安装版无接收端 | 两侧同批发布并做端到端演练 |
| 宿主 UI 端到端交互未通过 | `docs/INTERACTION_RUNTIME_GATE.md`：卡片渲染与回写仍为参考实现 | 在目标宿主完成验收后再宣称 |
| 跨 Skill 调用信封缺失 | REM-001 R11：`request_id` / `idempotency_key` 未与 Execution/Viz 统一 | 定义 `pfc.skill-invocation@1.0.0` |

## 3. `main` 上可确认的能力（5.2.0 基线）

- 六阶段工作流与 Core 五能力；M1–M6 模块化协作。
- 科研议题树、D0–D3 深度讨论、反方审查、证据与假设成熟度。
- 决策与授权状态模型、跨会话恢复、讨论模式路由、五类卡片参考实现。
- 5.2.0 S4 参数识别与标定协议子系统（`core/s4_*.py`、`modules/s4_calibration.py`）：
  协商与协议闭环，**不宣称材料参数定量标定成功**。
- 三工况真实 PFC3D 机制比较（`docs/V510_ACCEPTANCE.md`，69 个真实 tool_task_id）。

## 4. 明确的非范围

- 材料参数定量标定不在已发布基线内。
- 正式模型验证、Evidence 与 Finding 属于 Research Evidence Skill。
- 宿主自动渲染卡片并回写答案未端到端通过；不得写作“已投递/已询问”。

## 5. 发布前验证

```bash
python -m unittest discover -s tests -p "test_*.py"
```

记录：实际通过条数、离线跳过项、真实宿主通道探测结果、真实 PFC 证据（如有）。
没有真实证据的能力标 `NOT_VERIFIED`，不得以协议测试替代。

## 6. 版本沿革

完整沿革见 `RELEASE.md` 与 `CHANGELOG.md`。本草稿只覆盖拟议的 5.2.0。
