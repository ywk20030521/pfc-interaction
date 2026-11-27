# PFC Interaction 5.1 收口 PR 拆分

**基线：** 5.0.1（议题树/D0–D3/证据档案/五类卡片，161 条测试通过）  
**目标：** 关闭 5.0.1 验收列出的全部未实现项，发布通用 **5.1.0**  
**原则：** 三轴案例只是验收材料；所有新增能力必须可复用于任意 PFC 科研课题。

## PR-E 跨会话恢复与模式自动路由 ✅

- `core/v501_archive.py` 写入结构化 `archive_state.json`；`core/v510_continuity.py` 提供 `SessionRestore`。
- `core/v510_routing.py` 按议题类型/状态/阶段自动推荐 8 种讨论模式。
- 验收：4 条发布测试；档案可重建议题树、证据索引与开放待办。

## PR-F M1–M6 深度模块包装 ✅

- `modules/v510_deep_modules.py`：统一 `module_result`，执行前检查 D0–D3 门槛与模块专属输入；失败返回 blocked 并列出未决项。
- 验收：2 条测试；未过门槛不得运行，过门槛后返回 candidates/evidence/confidence/unresolved。

## PR-G 宿主 UI 渲染参考 ✅

- `assets/v510_cards.html`：五类卡片、浅色克制样式、高级依据折叠、窄屏纵向排列、文字状态标签、暂缓/返回讨论按钮。
- 验收：文件随包发布；宿主实际渲染仍由平台决定，Skill 提供完整参考实现与元数据。

## PR-H 可复用科学层闸门与围压闭环 ✅

- 根因：旧 `wall servo force(...)` 向量写法与响应参数不足；改用 `force-x/force-y` + `velocity-max 1.0` + `gain-update 10`。
- `core/v510_physics.py` 区分数据有效性与峰值强度声明；`outputs/v510_acceptance/scripts/pfc_case_runner.py` 为可复用三轴配方。
- 验收：3 工况、69 个真实 tool_task_id、围压比 0.975–1.000、加载中漂移 ≤10%；`SCIENTIFIC_REPORT.md` 标记科学层机制比较通过。

## PR-I 版本、文档与发布 ✅

- SKILL/README/CHANGELOG/RELEASE 升 5.1.0；新增 V510 验收/状态文档；全量 170 条测试通过；打包并同步安装目录。
