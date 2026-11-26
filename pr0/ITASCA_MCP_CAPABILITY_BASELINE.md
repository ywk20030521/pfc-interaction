# itasca-mcp 能力基线（PR0）

**版本：** 0.1  
**日期：** 2026-11-25  
**状态：** 静态核查已完成，动态能力待实测  
**依据：** 本机 MCP 配置、已暴露工具的真实 schema、bridge 包源码、工作区 ARCHITECTURE.md

---

## 1. 锁定的版本与环境

| 项目 | 锁定值 | 证据来源 |
|---|---|---|
| itasca-mcp | `0.8.1`（uvx 拉取） | `~/.workbuddy/mcp.json` |
| itasca-mcp-bridge | `0.6.11` | `bridge.exe --version` + `pip show`（Roaming/Python310/site-packages） |
| PFC 引擎 | PFC900（2D/3D console + gui 齐全） | `D:\Itasca\PFC900\exe64\`：pfc2d9_console.exe / pfc2d9_gui.exe / pfc3d9_console.exe / pfc3d9_gui.exe |
| Bridge 可执行文件 | `D:\Itasca\PFC900\exe64\python310\Scripts\itasca-mcp-bridge.exe` | 文件存在，help 可运行 |
| Bridge 默认地址 | `http://localhost:9001` | ARCHITECTURE.md §5 + 工具错误信息 |
| MCP 文档服务 | `http://127.0.0.1:8000/mcp` | ARCHITECTURE.md §5 |
| 嵌入式 Python | 3.10 | bridge 包路径 Python310 + 工具说明（Itasca 9+ → 3.10） |

> 注意：本机默认 shell 的 `python` 没有 itasca 模块，也没有 itasca-mcp / bridge 包；这些只存在于 PFC 自带 Python 与 MCP 的 uvx 环境。因此任何"直接 import itasca"的验证都必须在 PFC 引擎进程内进行。

### 1.1 仓库核查与版本差异（2026-11-25，来源 `https://github.com/yusong652/itasca-mcp` main 分支）

**这是 PR0 最重要的发现：公开 main 分支与本机锁定的 0.8.1 在工具命名和文档版本默认值上已经不同。** 任何 Skill 文档都必须以"锁定版本 + 能力探测"为准，不得写死上游工具名。

| 项目 | 本机 0.8.1（本次会话实测 schema） | 公开 main 分支（2026-11-25 核查） |
|---|---|---|
| 文档工具 | 4 个：`itasca_browse_commands`、`itasca_query_command`、`itasca_browse_reference`、`itasca_query_python_api` | README 称 2 个：`itasca_browse_doc`、`itasca_query_doc`；server.py 实际注册 `browse_doc` + `query_doc`（一个工具覆盖 4 棵文档树，用 `source` 参数选 commands/python_api/fish/reference） |
| 执行工具 | 5 个：`execute_code`、`execute_task`、`check_task_status`、`interrupt_task`、`list_tasks` | 同 5 个，名称与职责一致 |
| 工具总数 | 9 个（4 文档 + 5 执行） | README 标称 7 个（2 文档 + 5 执行） |
| 文档版本默认值 | 7.0 | server.py instructions 明确写 "Version defaults to 9.0; pass 6.0/7.0 for older PFC, FLAC or 3DEC installs" |
| `_context` 说明 | schema 未详述 | server.py 给出完整指令，见 §4.1 |

**对 Skill 的影响（已写入 PR1）**：

- 文档查询工具**必须通过能力探测确认实际暴露的工具名**，Skill 不得假定是 `browse_commands` 还是 `browse_doc`；
- 文档版本参数**必须显式传入**，不得依赖默认值（不同版本默认值不同）；
- 5 个执行工具在两版本中稳定，可作为 Skill 的稳定依赖面。

仓库 README 补充确认的 bridge 启动方式（与本机 ARCHITECTURE.md 一致）：

- GUI：在引擎 IPython 控制台 `import itasca_mcp_bridge; itasca_mcp_bridge.start()`；
- Console 无头：agent 可通过引擎 `console.exe` 自行启动 bridge（本机为 `pfc2d9_console.exe` / `pfc3d9_console.exe`）；
- `start()` 默认检查 PyPI 并自升级；如需锁定版本，传 `auto_upgrade=False` 或设环境变量 `ITASCA_MCP_BRIDGE_AUTO_UPGRADE=0`——**PR0 锁定 0.6.11 后，后续所有 PoC 必须禁用自升级，否则版本会漂移**；
- MIT 许可。

---

## 2. 已实测：工具清单与真实 schema

以下 6 个工具在本次会话中真实加载了 schema，与 V3.1 报告的源码描述一致。

### 2.1 `itasca_execute_code`

- 同步在引擎进程执行 Python，`stdout` + `result` 立即返回。
- 与长任务共享 `__main__` 命名空间，cycle 间隙插入检查/调参（live REPL）。
- 参数：`code`（必填）、`timeout`（默认 10s，范围 1–600s）。
- 边界：同步阻塞、不进入 `list_tasks`、不可中途中断。
- 约束：`itasca.command` 必须用原名调用（重绑定会绕过归一化并产生 bridge warning）；FISH 定义块必须整块传入；`program call` 按命令逐条执行以保持可达与可中断。

### 2.2 `itasca_execute_task`

- 提交 Python 脚本文件异步执行，立即返回 `task_id`。
- 参数：`entry_script`（引擎工作区内的绝对路径）、`description`（≤200 字）。
- 生命周期配套：`check_task_status` / `interrupt_task` / `list_tasks`。
- 运行中可被 `execute_code` 实时检查与调参（sentinel、回调替换）。

### 2.3 `itasca_check_task_status`

- 参数：`task_id`（必填）、`skip_newest`、`limit`（默认 64，1–200）、`filter`、`wait_seconds`（默认 1，1–3600）。
- 输出：Python print 与 `itasca.command` 控制台输出按执行顺序交错，可分页/过滤。
- `wait_seconds > 0` 时在查询前等待，配合 SSE 任务事件唤醒（V3.1 §4.3C）——这是任务状态等待，**不是**任意 PFC 状态推送。

### 2.4 `itasca_interrupt_task`

- 参数：`task_id`。请求优雅中断。
- 边界：中断 ≠ 任意位置暂停/恢复；本 Skill 不使用它实现"暂停后原调用栈续跑"。

### 2.5 `itasca_list_tasks`

- 参数：`skip_newest`、`limit`（默认 32，1–100）。分页浏览任务历史。

### 2.6 `itasca_browse_commands`

- 参数：`software`（必填，枚举 pfc/flac/3dec/mpoint/massflow）、`command`、`version`（6.0/7.0/9.0，默认 7.0）。
- 另有 `itasca_query_command`、`itasca_browse_reference`、`itasca_browse_python_api`、`itasca_query_python_api` 组成文档检索通道。

---

## 3. 已实测：连接状态

| 检查项 | 结果 | 结论 |
|---|---|---|
| `itasca_execute_code` 最小调用 | `ok:false`，`error.code=bridge_unavailable`，`reason=All connection attempts failed` | **Bridge 未运行**，符合预期 |
| Bridge 进程 | 未启动 | 动态 PoC 的前置条件未满足 |
| 工具 schema 可见性 | 6/6 正常返回完整描述 | MCP Server 本身健康，问题只在 bridge |

**当前状态判断（已更新）：2026-11-25 19:18 已成功无头启动 bridge，通信层与执行层全部连通，PoC-1 动态验证已完成（见 §3.1）。**

---

## 4. 从源码/config 确认的能力边界

### 4.0 Bridge 0.6.11 源码结构变化（重要）

本机 bridge 0.6.11 的模块结构与 V3.1 报告核查的公开版本**完全不同**：

| V3.1 报告引用的路径 | 本机 0.6.11 实际路径 |
|---|---|
| `bridge/context.py` | `handlers/context.py`（`ServerContext` 依赖注入容器）+ `handlers/console.py`（`console_history` handler） |
| 上下文注入 | `console/history.py`（`ConsoleHistory`）+ `console/capture.py` + `console/views.py` |
| 无对应 | `runtime.py`（模式检测、Qt/阻塞泵）、`server.py`（handler 注册） |

**这再次证明：任何 Skill 文档都不得引用具体源码路径作为能力依据，只能引用能力与实测结果。**

### 4.0.1 Console 用户操作感知 —— 已由源码定论（关键待验证项关闭）

V0.x 与 V3.x 都把"Console 下能否观察用户直接键入的命令"列为待验证。**本机 0.6.11 源码给出明确答案：Console 模式下不支持。**

证据（`runtime.py` 第 595–633 行）：

- `install_console_capture(console_history)` 和 `install_view_tracking(...)` **只在 `qt_running` 为真时安装**（注释原文："Only a GUI has those widgets, and the prompt hook needs the event loop for its timers"）；
- `mode="console"` 且无 Qt 事件循环时走 `use_blocking` 分支，只 `set_runtime_mode("console")`，**不安装任何 console 捕获器**；
- `mode="gui"` 在无 Qt 循环时直接抛错。

**结论**：Console-only 运行时，用户直接键入的任意命令**不会被采集**。Skill 必须：

- 在 Console 场景把"用户直接输入感知"声明为 unsupported；
- 用户介入只能走 Native Chat 明确指令或文件提交通道；
- 不得把 GUI 的 `_context.user_console` 能力外推到 Console。

同时，0.6.11 新增了比 V3.1 报告描述更强的能力：`ConsoleHistory` 用 `console_history.jsonl` + `console_cursor.json` 做磁盘持久化和投递游标，客户端重连不会丢条目或重放整个会话；bridge 还暴露了独立 `console_history` handler 与 SSE 广播。但这些**仅在 GUI 模式生效**。

### 4.1 上下文回传（`_context`）—— 本次已由 server.py 源码逐字核实

`server.py` 的 `instructions` 明确说明（已核实，非推断）：

- 执行工具响应**可能**携带 `_context` = "what happened in the engine GUI since the previous call"；它不属于工具结果本身，需单独读取以跟进用户正在做什么；
- `_context.user_console`：列出用户键入的内容。`'python'` = IPython 面板，`'command'` = 命令提示符；`'queued'` = 引擎忙尚未执行，其输出随后以 `'ran'` 出现；
- `_context.gui`：用户或 Agent 自己代码打开/切换的 Plot 与 Data 文件（`'active'` = 当前在前台）以及 plot items 的增删改动；`'executed'` = 用户从编辑器运行了该数据文件（`'master'` = 项目主文件），`'saved'` = 用户已保存，`'diff'` = 自上次看到后的改动，查看方式是用工具读文件或导出 Plot 为图片；`'unsaved'` = 用户正在编辑、尚未落盘的数据文件，**写入前必须先告知用户**；`kind 'dialog'` = GUI 出现模态对话框（`open`）或消失（`closed`），对话框打开期间引擎可能在等用户响应；
- **关键限制**：best-effort，在 Agent 的**下一次 MCP 工具调用边界**获取，不是独立实时推送通道。虽然 README 有"The agent follows what you do in the engine GUI"的表述，但实现机制是"下次调用时附加"，Skill 不得据此宣称具备实时事件推送。

### 4.2 工作区既有领域知识（来自 ARCHITECTURE.md，可写入 Skill）

这些是本项目已验证的 PFC2D 事实，Skill 必须遵守：

1. **Console 无头模式下所有 `plot` 命令都是静默空操作**（`plot create` / `plot item create` / `plot export bitmap` 返回成功但不产文件）。出图必须走离线 matplotlib 脚本或 GUI 手动导出。
2. **自建 `model new` 必须在首次 `cycle` / `solve` 前显式设置 `model large-strain on|off`**；`model restore` 续跑继承存档设置。
3. 阶段脚本命名：`<前缀>_<两位序号>_<动作>.py`；共享参数/工具：`<前缀>_geom.py`；无头入口：`*_console.py`。
4. 参数集中在 `data/`（GUI 与 console 共用），脚本不写死参数；存档放 `work/`，成果放 `outputs/<模式>/`。
5. Bridge 用进程 CWD 冻结根路径，启动脚本必须把工作目录固定到工作区根目录。

### 4.3 明确不假定

- 不假定 Console 下能观察用户直接键入的任意命令；
- 不假定存在通用 `pause_task` / `resume_task`；
- 不假定运行中 REPL 的任意修改都安全；
- 不把 GUI 事件能力外推到 Console。

---

## 3.1 PoC-1 实测结果（2026-11-25 19:18–19:21，PFC2D Console）

**启动方式**：`pfc2d9_console.exe <pr0/poc/start_bridge_p2d.dat>`，后台常驻，PID 25236。`auto_upgrade=False` 锁定 bridge 0.6.11。`/health` 返回 `{"status":"success","version":"0.6.11","runtime_mode":"console"}`。

| 编号 | 验证项 | 实测结果 | 结论 |
|---|---|---|---|
| T1 | `/health` | status=success, version=0.6.11, runtime_mode=console | 通过 |
| T2 | 同步执行 | `PY 3.10.5` / `EXE ...\pfc2d9_console.exe` / `ITASCA_OK`（execute_code 返回 ok:true） | 通过 |
| T3 | 状态查询 | `BALL_COUNT 2` / `BALL1_RADIUS 0.5`，与模型一致 | 通过 |
| T4 | 长任务提交 | task_id `752362` / `b99b1e` / `25e359`，真实上游 ID | 通过 |
| T5 | 任务状态与输出 | `b99b1e` completed，500 cycles，46 行分页输出，含 elapsed_time | 通过 |
| T6 | 运行中 REPL | 任务 cycling 期间 execute_code 返回 `CURRENT_CYCLE 500` / `BALL_COUNT 2`，任务未受影响 | 通过 |
| T7 | 中断 | `interrupt_requested:true` → 状态 `interrupted`，elapsed 3.26s | 通过 |
| T8 | 历史任务 | list_tasks 返回 3 条，含 completed/interrupted/failed 三种真实状态 | 通过 |
| T9 | 上下文回传 | console 模式下 execute_code 响应**未携带 `_context`**；与源码定论一致 | 通过（符合预期：unsupported） |
| T10 | Console 用户输入感知 | 源码定论 unsupported；本轮 console 会话无 GUI 捕获器 | 关闭：unsupported |
| T11 | PFC3D | 已实测（19:30，详见 §3.2） | 通过 |
| T12 | GUI 模式 | 源码级已确认；动态需人工在 GUI IPython 启动（见 `poc/GUI_MODE_VERIFICATION.md`） | 源码通过 / 动态待人工 |

**过程中获得的真实 PFC 知识（已写入 Skill）**：

1. 工具名/参数以本机 schema 为准：`itasca_query_command` 用 `query` 参数（不是 main 分支的 `browse_doc`），`version` 显式传 `9.0`；
2. `domain` 正确命令是 `model domain extent -2 2 -2 2`（查询文档工具后确认，不靠猜）；
3. PFC2D 的 `ball create position` 是二维 `(x,y)`，不是三维；
4. 球参与 `model cycle` 前必须有质量：`ball attribute density 2500 range id 1 2`，否则报 `zero inertial mass`；
5. `itasca.ball.list()` 返回单个 Ball 对象而非可 len 的列表，用 `list(itasca.ball.list())`；
6. 失败的第一次任务 `752362` 状态为 `failed`，错误信息完整保留——验证了"执行失败不假报成功"。

**PoC-1 结论**：PFC2D Console 运行组合的核心执行能力（T1–T8）全部通过。T9/T10 确认 Console 模式无上下文回传（unsupported，非缺陷）。T11/T12 待切换引擎/模式后验证，不阻塞 PFC2D Console 场景的 Skill 使用。

## 3.2 PoC-1 补充实测：PFC3D Console（2026-11-25 19:30）

启动方式：`pfc3d9_console.exe <pr0/poc/start_bridge_p3d.dat>`，后台常驻（PID 27708）。`/health` = success / 0.6.11 / console 模式。

| 编号 | 验证项 | 实测结果 | 结论 |
|---|---|---|---|
| T1 | health | success / 0.6.11 / console | 通过 |
| T2 | 同步执行 | `PY 3.10.5` / `EXE ...\pfc3d9_console.exe` / `ITASCA_OK` | 通过 |
| T3 | 3D 状态查询 | `BALLS3D 40` / `POS3D vec3(...)`，三维坐标正确 | 通过 |
| T4 | 长任务提交 | task_id `d25bc6` | 通过 |
| T5 | 任务状态与输出 | completed，300 cycles，contacts/timestep 输出正常 | 通过 |
| T6 | 运行中 REPL | cycling 期间返回 `CYCLE 300` / `BALLS 40`，任务未受影响 | 通过 |
| T7 | 中断 | `interrupted`，elapsed 3.58s | 通过 |
| T8 | 历史任务 | list_tasks 累积 12 条，跨 2D/3D 会话持久化 | 通过 |

**跨维度隔离验证（重要）**：把 2D 脚本 `poc_long_task.py`（`position=(0,0)`）提交到 3D 引擎，返回 `failed` + 明确错误 "3D vector of floating point values expected"（task `3b95d4`）。证明：
- 2D/3D 脚本不通用，Skill 必须按 engine 选择正确脚本；
- 错误被如实标记为 failed，不伪装成功；
- 跨维度失败不影响后续 3D 任务（紧跟的 `f08ca8` 正常 completed）。

**PFC3D 建模要点**：domain 是六参数 `model domain extent -3 3 -3 3 -3 3`；球用 `ball generate ... box -2 2 -2 2 -2 2`；坐标是 `vec3`；接触模型命令与 2D 相同（`contact cmat default model linear ...`）。

**PoC-1 结论（更新）**：T1–T8 在 PFC2D Console 与 PFC3D Console **两种组合全部通过**。T9/T10 确认 Console 模式无 `_context`（unsupported）。T12 GUI 动态验证需人工执行。

## 5. 待实测清单（PoC-1 门禁）

启动 bridge 后逐项执行并记录证据：

| 编号 | 验证项 | 方法 | 通过标准 |
|---|---|---|---|
| T1 | `/health` 返回 | `Invoke-RestMethod http://localhost:9001/health` | `status=success`，记录 version / runtime_mode |
| T2 | 同步执行 | `execute_code` 打印 `sys.version_info` / `sys.executable` | 返回真实引擎版本 |
| T3 | 状态查询 | `execute_code` 查询 ball/contact 数量 | 返回与模型一致的真实数值 |
| T4 | 长任务提交 | `execute_task` 提交一个最小脚本 | 立即返回 task_id，关联真实 ID |
| T5 | 任务状态与输出 | `check_task_status` 轮询至完成 | 有输出、最终状态、耗时 |
| T6 | 运行中 REPL | 任务 cycle 期间 `execute_code` 检查状态 | 可 interleaving 查询，不影响任务 |
| T7 | 中断 | `interrupt_task` 中断运行中任务 | 状态转为 interrupted，无残留 |
| T8 | 历史任务 | `list_tasks` | 可见 T4 的任务 |
| T9 | 上下文回传 | 调用任一工具后检查 `_context` | 记录 user_console / gui 是否出现及触发条件 |
| T10 | Console 用户输入感知 | 在 console 直接输入命令后调用工具 | **源码已定论 unsupported**（`runtime.py` 仅在 GUI 安装 capture）；实测用于最终确认 |
| T11 | PFC3D | 换 pfc3d9_console.exe 重复 T1–T8 | 3D 同样通过 |
| T12 | GUI 模式 | GUI IPython 中 `start()` 后重复 T1–T9 | GUI 能力与限制有记录 |

**验收门槛：** T1–T8、T11 全部通过，T9/T10/T12 有明确结论（通过或 unsupported），才算 PR0 通信基线关闭。未通过项必须转为受限功能或重新设计，不得在后续 PR 中伪装为已具备。

---

## 6. 结论

PR0 静态部分已完成：版本锁定、工具 schema 核对、连接状态确认、领域知识提取。**动态能力尚未验证**，因为 bridge 未运行。按 V3.1 的门禁要求，PoC-1 通过前不得宣称端到端闭环成立；但 PR1–PR4 的行为规范编写不依赖 bridge 运行，可以并行推进。
