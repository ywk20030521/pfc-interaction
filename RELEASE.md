# PFC Interaction Skill — 发布与兼容说明

**版本：** 4.0.1（首个集成版 4.0.0 的缺陷修订；0.1.0 为历史基线）  
**日期：** 2026-11-26  
**状态：** **可受控试用**  
**整体验收（2026-11-26）：** 未通过，详见 `FINAL_ACCEPTANCE_2026_11_26.md`。本轮关闭 A6 接口/协议层验证（5 条用例对接真实 AUQ server）；A8 宿主层、GUI 动态、完整应力-应变曲线仍需外部动作。全量 43 条用例通过。  
**项目状态定位：** 一个 Skill（唯一目录 `pfc-interaction/`）：现有核心交互能力 + 六个专业科研模块 M1–M6 + 复用 itasca-mcp / Visualization Skill。4.0 升级已完成合并迁移，M1–M6 均已实现；32 条接口用例 + 6 条 v4.0.1 回归用例通过（含真实 bridge 的 FISH 块执行），六模块流水线经真实 PFC2D bridge 端到端跑通。架构定义源为 V3.2 + 4.0 技术报告；接口契约见 `references/module_contract.md`；独立审查见 `V4_INDEPENDENT_REVIEW.md`。**A6、A8 宿主层、GUI 动态验证、完整应力-应变曲线仍未关闭**；不宣称 4.0 全部验收通过。

**4.0.1 修订内容**：依据独立审查与上游 issue #250 的维护者回复，修复三项缺陷：①适配器 `.dat` 执行改为使用 bridge 原生 `preprocess_source` 拆分（不再自行逐行拆分导致 FISH 块卡死)；②无效 PFC 证据标 `INVALID_EVIDENCE` 并阻断结论；③ `REJECTED` 决策保留拒绝语义并维持同 context 去重。**上游定性澄清**：该卡死是 GIL 设计约束下的客户端误用，**非上游 bug**；issue 已回复请关闭。

> 状态用语约定：**实测通过**（有真实运行证据）/ **设计通过**（规范一致但未运行时验证）/ **阻塞已确认**（原因查清、步骤备好，但功能未验收）。三者不得混用。

---

## 1. 文档体系与版本定位（统一版本管理）

审阅意见指出：不应让 V3.1 报告继续承担"最终架构定义"。本发布明确各文档职责：

| 文档 | 职责 | 是否定义最终架构 |
|---|---|---|
| `PFC_人机交互技术报告_V3.1.md` | **原始架构方案历史记录**（含当时的待验证项与已知错误，如"AUQ 是 Python 包"） | 否（历史文档） |
| `PFC_Interaction_架构决策与最终方案.md`（V3.2） | **最终架构决策**：三方两通道一中心、ADR-001~005、从 V0.x 保留的安全原则 | **是** |
| `pfc-interaction/PR_STATUS.md` | **实施状态**：各 PR 完成情况、实证与剩余限制 | 否（状态文档） |
| `pfc-interaction/RELEASE.md`（本文件） | **发布说明**：版本、兼容矩阵、安装、已知限制 | 否（发布文档） |
| `pfc-interaction/SKILL.md` + references/ | **可安装 Skill 本体**：Agent 行为规范 | 是（0.1.0 运行时规范） |
| `docs/PFC_Interaction_4.0_技术报告.md` | **4.0 目标架构定义源**：六模块职责、批次与验收标准 | 是（仅 4.0 阶段） |
| `docs/IF0_接口冻结规范.md` | **4.0 接口契约**：Core ↔ M1–M6 的字段、状态、证据链 | 否（接口契约，非架构目标） |

**原则**：0.1.0 的实现与验收以 `SKILL.md` 和本 RELEASE 为准；V3.1 仅用于追溯设计演进。

**4.0 演进记录（2026-11-25 → 11-26）**：4.0 目标架构已基线化、IF0 接口已冻结、六模块已实现并有真实 bridge 证据；设计档案（技术报告 / IF0 规范 / 升级规划 / 基线登记 / 第一批验收）统一迁入 `pfc-interaction/docs/`，独立目录已清理。**4.0 整体仍未验收通过**。以本 RELEASE 与 `SKILL.md` 为运行时依据，设计档案仅作追溯。

---

## 2. 兼容矩阵（已验证版本绑定）

| 组件 | 已验证版本 | 验证状态 | 发布要求 |
|---|---|---|---|
| itasca-mcp | **0.8.1** | 工具 schema 实测、T1–T8 通过 | 固定 0.8.1 或显式验证其他版本的工具名差异 |
| itasca-mcp-bridge | **0.6.11 / 0.6.16 均实测通过** | 2D/3D Console 实测；0.6.16 上 FISH 整块执行复验通过 | 两者兼容；启动时建议禁用自升级以锁定版本 |
| PFC2D | PFC900（9.x）Console | **完整 PoC + 2 次 E2E** | 已验证，可试用 |
| PFC3D | PFC900（9.x）Console | **PoC T1–T8 通过** | 已验证，可试用 |
| PFC2D/PFC3D GUI | PFC900 GUI（PFC3D GUI 实测） | **G1–G6 全部实测通过（bridge 0.6.17）** | 已验收；见 `examples/GUI_DYNAMIC_ACCEPTANCE.md` |
| AUQ | **auq-mcp-server 3.4.0**（npm，非 Python） | CLI 异步往返 A1–A5 实测 | 用 npm/npx 安装；MCP 工具需会话重启生效 |
| Agent 宿主 | WorkBuddy | 结构化提问可用；宿主主动推送能力待补验 | 标注实际支持能力，见 `pr0/HOST_INTERACTION_CAPABILITY.md` |

**版本漂移警告（实测）**：

- 本机 itasca-mcp 0.8.1 有 4 个文档工具（`browse_commands` / `query_command` / `browse_reference` / `query_python_api`），公开 main 分支只有 2 个（`browse_doc` / `query_doc`）；文档版本默认值 7.0 vs 9.0。Skill 规定：**文档工具必须能力探测、版本参数显式传入**。
- bridge `start()` 默认检查 PyPI 自升级，会破坏版本锁定。所有启动脚本已设 `auto_upgrade=False`。**2026-11-26 复验发现本机 bridge 已为 0.6.16**（上游当前版本 0.6.16），在此版本上重跑 v4.0.1 的 FISH 整块执行用例仍通过——执行适配跨 0.6.11/0.6.16 均成立。
- AUQ 是 npm 包 `auq-mcp-server`，四份技术报告中"Python 包"描述错误，以本矩阵为准。

---

## 3. 安装说明（最小可用配置）

### 3.1 基础安装（必需）

```text
1. 安装 PFC Interaction Skill
   → 将 pfc-interaction/ 目录放入 Agent 的 skills 目录
2. 配置并验证 itasca-mcp（已验证 0.8.1）
   → uvx itasca-mcp@0.8.1
3. 在 PFC 引擎内启动 bridge（已验证 0.6.11）
   → 见 pfc-interaction/pr0/poc/README.md
4. 在 Agent 中启动实验协作
```

基础功能（Native Chat 协作）不依赖 AUQ、不依赖 Web、不依赖数据库、不需要独立后端。

### 3.2 可选：AUQ 异步通道

```json
{
  "mcpServers": {
    "ask-user-questions": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "auq-mcp-server@3.4.0", "server"]
    }
  }
}
```

安装后需重启 Agent 会话/信任新 server，工具 `ask_user_questions` 与 `get_answered_questions` 才会在宿主可见。**工具层已通过 MCP stdio 协议实测（异步往返成立）；宿主可见性仍未通过（A8）**。异步调用时把 `nonBlocking` 设为 `true`（默认 false = 阻塞）。

### 3.3 显式不做

不安装 PostgreSQL / Redis / 消息队列；不部署 Web；不 fork AUQ；不复制 itasca-mcp 工具。

---

## 4. 功能与能力边界

| 能力 | 状态 |
|---|---|
| Agent 读取 PFC 状态、提交/中断任务、运行中 REPL | 已验证（2D/3D Console） |
| 阶段汇报、异常识别、参数协商、决策结构化 | Skill 规范完成；E2E 场景验证 |
| 用户反馈改变后续执行并有 PFC 状态证据 | 已验证（E2E） |
| 双通道：Native Chat + AUQ | Native 已用；AUQ CLI 异步往返已验证，MCP 工具宿主集成待补 |
| GUI 上下文感知（`console_history`） | **G1–G6 实测通过**：用户输入/视图/unsaved/对话框均可拉取；Console 返回 unavailable |
| Agent 退出后台主动通知 | 不支持（宿主能力边界） |
| 任意位置暂停/恢复 | 不支持；仅阶段级检查点 |

---

## 5. 已知限制（随版本发布）

**未关闭项（均未通过，不得以"已处理"代替"已验收"）**：

1. **A6 双通道运行时去重 — 未通过**：仅完成 7 份文档规则一致 + 可执行判定流程（设计通过），真实任务中不重复投递尚未实测。
2. **A8 AUQ 宿主集成 — 未通过**：MCP 配置已注册，但当前 WorkBuddy 会话工具不可见（阻塞已确认）；重启后需重新检查工具可见性与异步回答取回。
3. ~~**GUI 动态验证 — 未通过**~~ → ✅ **已通过（2026-11-26 晚）**：PFC3D GUI + bridge 0.6.17 实测 G1–G6 全部通过（`examples/GUI_DYNAMIC_ACCEPTANCE.md`）。注意 0.6.17 上下文机制改为独立 `console_history` 端点拉取，执行响应不再附加 `_context`；Console 模式仍返回 `console_history_unavailable`。
4. **完整物理曲线独立验证 — 未通过**：已获得异常识别证据（回归案例 `E2E_DATA_QUALITY_AND_DECISION_RECOVERY`），但有效应力-应变曲线未得到；±2.0 扩散的几何诊断为**待复核技术诊断**，非已证明根因。若需验收完整曲线，应单独进行几何/边界/测量标定，不混入 Skill 功能开发。

**其他限制**：

5. **跨实验类型证据有限**：E2E 证据来自简化的单轴压缩场景；三轴、颗粒流动等实验类型未验证。
6. **版本差异**：见 §2；上游工具名/默认值随版本变化，以能力探测为准。
7. **Console 用户直接输入不可观察**：架构边界，介入通过 Chat 或文件提交。

---

## 6. 发布门槛与试用建议

**当前状态**：核心 PR（PR0/PR1/PR2/PR3/PR4/PR6）完成主体，可试用；PR5 条件性未触发。

**建议试用范围**：PFC2D/PFC3D Console + Native Chat 协作 + 阶段级检查点决策。

**暂不建议**：AUQ 异步通道的生产使用（A8 宿主层未通过）、跨实验类型的通用性结论。GUI 模式已完成 G1–G6 动态验证可试用；`console_history` 需走 bridge HTTP（MCP 工具层未暴露）。

---

## 7. 变更日志

| 版本 | 日期 | 变更 |
|---|---|---|
| 0.1.0 | 2026-11-25 | 首次试用版：V3.1 方案落地；PR0–PR4/PR6 主体完成；PFC2D/3D Console 真实验证；AUQ npm 包修正；完整物理 E2E 与数据可信度规范补充 |
| 0.1.0-rev1 | 2026-11-25 | 复审修正（功能不变）：状态分层（实测/设计/阻塞）、未关闭项明确标未通过、数据质量回归案例定名、几何诊断改为待复核、去重协议加 context_version 与 SUPERSEDED、V3.2 与 SKILL 对齐 |
| 0.1.0-rev2 | 2026-11-25 | 架构图实践检测（功能不变）：6 要素实证全部通过；A8 分层为工具层通过/宿主层未通过；AUQ schema 细节修正；物理曲线标定起点归档 |
| 0.1.0-rev3 | 2026-11-25 | 复杂实验指导（功能不变）：新增 `references/complex_experiment.md`（阶段化拆解 + 检查点 + 数据把关 + 维度差异）；修正 GUI 文档过时 PID |
| 4.0.0 | 2026-11-25 | 架构升级（一个 Skill，非新建）：合并迁移 4.0 core/modules/tests；新增 `adapters/itasca_mcp.py` 真实桥适配器；M1–M6 六模块全部实现；`references/module_contract.md` 统一接口；32 条接口用例通过；六模块流水线经真实 PFC2D bridge 端到端跑通；SKILL 升 v4.0.0 |
| 4.0.1 | 2026-11-26 | 缺陷修订：`.dat` 执行改用 bridge 原生 splitter（FISH 块整块执行，不再卡死 bridge）；新增 `INVALID_EVIDENCE` 并阻断缺 tool_task_id 的 PFC 证据结论；`REJECTED` 映射 CANCELLED 且保留拒绝语义；新增 6 条回归用例；上游 issue #250 定性为客户端误用并请关闭 |
| 4.0.1-rev1 | 2026-11-26 晚 | GUI 动态验证关闭（文档修订，功能不变）：用户启动 PFC3D GUI + bridge 0.6.17，G1–G6 全部实测通过；实测发现 0.6.17 上下文机制改为独立 `console_history` 端点拉取（执行响应不再附加 `_context`），同步修正 5 份 Skill 文档与验收/发布状态 |
