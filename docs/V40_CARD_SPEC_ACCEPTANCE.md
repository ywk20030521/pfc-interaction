# 提问卡片强制设计规范 V2 — 验收报告

**依据：** `C:/Users/L/Downloads/PFC_Interaction_提问卡片强制设计规范_V2.md`（第 6、12 章为 MUST）  
**日期：** 2026-11-26  
**实现：** `core/question.py`、`modules/question_cards.py`、`modules/nature_experiment_design.py`

---

## 0. 内容—逻辑—形式融合（2026-11-26 追加）

用户明确三项修正，已并入本实现：

1. **形式是模板，不是数量**：A/B/C 是三种卡片形式模板；同一类型可出现 N 张直到实验完成，不存在"一类只一张"。
2. **形式严格照录图片**：`modules/card_templates.py` 固化图片原文——
   - A 科研讨论：研究目标与实验假设 / 用于开放性问题，优先采用简短文字和自然语言输入。/ 适用：研究机制、实验假设、方案比较。
   - B 参数决策：实验参数与条件选择 / 用于单选、多选、数值和单位输入。/ 适用：2D/3D、接触模型、围压、加载速率。
   - C 执行确认：实验方案审核与授权 / 简洁展示变更内容、风险和影响，要求明确确认。/ 适用：模型初始化、参数修改、运行、覆盖和终止。
3. **卡片顺序 = 模型顺序**：`modules/card_sequence.py` 是顺序单一真相源，M1→M2→M3→M4→M5→M6，阶段内 A→B→C。共 28 张卡：M1 9、M2 14、M3 1、M4 2、M5 1、M6 1；`validate_sequence()` 返回空（无倒退、无跨阶段错位）。

`v41_interview.py`（实际入口）的 M1 两轮、M2 四轮问组已改为引用模板的 `_a_card/_b_card/_c_card`，保留全部答案 id 与 topic，逻辑与阶段门不变。验证：98 条测试全过（4 skip 桥离线）、v41 纵向切片与 v40 两遍走查通过。

---

## 1. 结论

**规范的语义层（P0）全部实现并验收通过；视觉层（P1）中宿主可控制的部分通过，宿主决定的部分（如窄屏、折叠区）由宿主能力边界说明。**

- 强制最小测试集 8 项：全部通过（`tests/test_v40_card_spec.py` 16 条）
- 三类卡片实测面板：全部按规范渲染
- 状态机严格区分：answered ≠ confirmed ≠ authorized ≠ executed ≠ verified
- 无高风险隐式授权：执行确认卡无静默延后、无默认勾选

---

## 2. 强制项逐条对照

| 规范条 | 要求 | 实现 | 验收 |
|---|---|---|---|
| 6.1 | 单卡单决策 | Question 单 question_id，card_from_question_set 保序 | ✅ |
| 6.1 | 推荐不默认选中 | Option.recommended 仅加"（建议）"标签，无 is_default/checked | ✅ |
| 6.1 | 允许不确定 | 非执行卡自动带 DEFER_LABEL | ✅ |
| 6.1 | 答案可追溯 | Decision 对象 + question_id + created_at | ✅ |
| 6.2 | 阶段标识/标题/说明/控件/建议/延后/依据/提交 | Question 全字段，panel_prompt=标题+一句话说明 | ✅ |
| 6.3 | 标题≤20、说明≤50、选项2-5、选项标题≤18 | validate_card() 强制自检 | ✅ |
| 6.4 | 三种卡片类型 | discussion_card / parameter_card / execution_card | ✅ |
| 6.5 | 颜色只表状态、克制视觉 | 由宿主面板控制；Skill 不输出装饰 | ⚠️ 宿主边界 |
| 6.6 | 卡片默认模板 | to_decision_question() 输出完整语义 | ✅ |
| 6.7 | 12 态状态机严格区分 | CardStatus + Decision.confirm/authorize/execute/verify | ✅ |
| 6.8 | 生成前强制自检 12 项 | validate_card()，工厂强制调用 | ✅ |
| 6.9/6.10 | 上下文区/已确认区/当前问题/依据/输入/延后/摘要/导航 | known_context + question_meta + decision_summary；完整面板由宿主渲染 | ⚠️ 宿主边界 |
| 7.1/7.2 | Question/Decision 数据结构 | 按规范字段实现 | ✅ |
| 8 | 去重键 | dedup_key(experiment,stage,topic) | ✅ |
| 12.4 | 最低测试集 8 项 | 16 条测试覆盖 | ✅ |

---

## 3. 最低测试集 8 项结果

```
test_01_discussion_card        ok
test_02_parameter_card         ok
test_03_numeric_card_with_unit_and_source   ok
test_04_defer_path             ok
test_05_execution_card_requires_explicit_authorization   ok
test_06_context_reuse_no_repeat ok
test_07_decision_change_supersedes ok
test_08_length_caps_and_visual_constraints  ok
+ TestStateMachine 3 条
+ TestSpecMUST 5 条
Ran 16 tests — OK
```

---

## 4. 真实面板实测（AskUserQuestion）

按规范截图样式实测三张卡：

**卡1 科研讨论**
```
header: 实验设计
问题:   本轮实验改变哪个变量？
        确定主变量，保证不同实验组之间具有可比性。
选项:   胶结强度（建议）/ 颗粒摩擦系数 / 粒径级配 / 暂不确定
```
用户选择：**粒径级配**

**卡2 参数决策**
```
header: 参数决策
问题:   围压取哪些水平？
        围压是唯一自变量，其余条件固定。
选项:   1,5,10 MPa（建议，单位 MPa，来源 M1 给定）/ 自定义 / 暂不确定
```
用户选择：**自定义数值+单位**

**卡3 执行确认**
```
header: 执行确认
问题:   确认开始求解？
        将使用已确认参数启动三轴压缩计算。
选项:   确认执行（动作/对象/影响）/ 取消返回检查
        —— 无"暂不确定"，无默认勾选
```
用户选择：**取消 / 返回检查** —— 未授权执行，符合规范 6.4C。

---

## 5. 与规范截图的一致性

- 截图1 的"实验设计·关键决策 / 待确认"标签、问题标题、一句话说明、选项说明、"建议"区——全部体现在实测面板。
- 截图2 的三种卡片类型（A 科研讨论蓝 / B 参数决策绿 / C 执行确认橙）——语义全部实现，颜色由宿主映射。

---

## 6. 未覆盖项与边界

1. **视觉规范 6.5**（字体、间距、圆角、语义色、窄屏）：由宿主 AUQ/Native Chat 面板控制，Skill 只提供语义与文本，不渲染 CSS。
2. **阶段导航区 6.10.8**（进度条）：question_meta 提供 progress{index,total}，宿主可选择展示。
3. **折叠技术依据区 6.2.8**：technical_basis 字段已提供，宿主可折叠展示；未折叠时不污染首屏。
4. **PR6 四类场景对照测试**（规范 10.3）：需要真实用户组对照实验，不在代码验收范围；本轮仅完成代码级与面板级验收。

---

## 7. 第二次对照修正（用户反馈"与标准图仍有差距"）

用户对照规范截图指出差距，逐条修正如下：

| 标准图 | 修正前 | 修正后 |
|---|---|---|
| 独立 💡 建议区 | 推荐塞在选项描述里 | `panel_prompt()` 末尾独立段落 `建议：…` |
| 选项说明为纯物理意义 | 混入"来源: Agent 建议" | 选项说明只留物理意义；来源/单位/理由移入 question_meta |
| 第4项"其他变量 / 由用户补充研究因素" | "暂不确定 / 稍后决定" | 自由输入项改为"其他变量 / 由用户补充研究因素" |
| header `实验设计 · 关键决策` | 只有 `实验设计` | `panel_header()` = 阶段·卡片类型；P1 参数卡显示"关键决策" |
| 右上角"待确认"徽章 | 无 | 宿主面板不提供徽章字段；`question_meta.status=pending` 供支持宿主渲染（宿主能力边界） |

修正后再次真实面板实测两张卡，用户均选择推荐项，确认建议表达清晰。98 条测试全过。

## 8. 验收判定

按规范 12.5：**通过** —— 所有核心语义强制项通过，最低测试集全部通过，无高风险误授权。视觉宿主边界项（状态徽章、按钮文案、窄屏）已如实标注，不影响理解、决策、授权与状态追踪。
