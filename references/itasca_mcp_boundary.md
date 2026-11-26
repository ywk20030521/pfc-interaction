# itasca-mcp 使用边界与能力探测

## 1. 稳定依赖面与变化面

**稳定面（本机 0.8.1 与公开 main 均存在，可依赖）**：

| 工具 | 用途 | 关键参数 |
|---|---|---|
| `itasca_execute_code` | 同步 REPL，查询状态/实时调参 | code、timeout(1–600, 默认10) |
| `itasca_execute_task` | 提交长任务脚本 | entry_script(绝对路径)、description(≤200) |
| `itasca_check_task_status` | 任务状态与分页输出 | task_id、limit(默认64)、filter、wait_seconds(默认1) |
| `itasca_interrupt_task` | 请求中断任务 | task_id（中断≠暂停恢复） |
| `itasca_list_tasks` | 任务历史 | skip_newest、limit(默认32) |

**变化面（必须能力探测，不得写死）**：文档检索工具。本机 0.8.1 暴露 4 个（browse_commands / query_command / browse_reference / query_python_api）；公开 main 只注册 2 个（browse_doc / query_doc，用 `source` 参数选择 commands/python_api/fish/reference）。文档版本默认值也不同（0.8.1 为 7.0，main 为 9.0）。

**探测做法**：先查看宿主实际暴露的工具清单；调用时显式传 `version`，不依赖默认值；若工具名不符，按实际工具调整，不虚构调用。

## 2. 使用原则

- 只在 PFC 引擎进程内执行代码；不试图从外部 Python 直接 import itasca；
- `itasca.command` 用原名调用，不重绑定（重绑定绕过 bridge 归一化，产生警告）；
- FISH 定义块整块传入一个 `itasca.command` 字符串；
- 长任务用 `execute_task`（可轮询/可中断），短查询用 `execute_code`；
- 运行中可用 `execute_code` 在 cycle 间隙检查/调参，但修改是否安全必须结合具体模型验证；
- **GUI 用户操作感知走独立的 `console_history` 端点**（0.6.17 实测，见 `examples/GUI_DYNAMIC_ACCEPTANCE.md`）：`POST /console_history {"limit":20}` → `data.entries[]`（`source=python` 用户输入 / `source=view` 视图与对话框）+ `cursor`/`has_more` + `state.unsaved`。**执行工具响应不再附加 `_context`**；旧版文档"响应附加 `_context`"的表述已过时。覆盖任何数据文件前必须拉取 `console_history` 并确认目标不在 `state.unsaved`。

**Console 模式下用户直接输入感知 = unsupported（源码级定论 0.6.11 + 实测 0.6.17）**：bridge 的 console 捕获器（`install_console_capture` / `install_view_tracking`）只在有 Qt 事件循环的 GUI 模式下安装；console 模式走阻塞泵，不安装任何捕获器。因此：

- Console 运行时，用户直接在 PFC console 键入的命令不会被 Agent 观察到；`console_history` 返回 `status=error, code=console_history_unavailable`（0.6.17 实测）；
- 用户介入必须走 Native Chat 明确指令或文件提交通道，不得假定"用户敲了命令 Agent 就知道"；
- GUI 模式下用户输入/视图/对话框/unsaved 全部可从 `console_history` 拉取，有磁盘持久化（用户暂离期间输入不丢失）与投递游标（不重放）；但仍是**主动拉取**，bridge 广播只是 doorbell，不构成 Agent 自主消息。

## 3. PFC 领域常识（来自本机工作区验证，必须遵守）

1. **Console 无头模式下 plot 命令静默空操作**：`plot create` / `plot item create` / `plot export bitmap` 返回成功但不产文件。出图走离线 matplotlib 脚本或 GUI 导出。
2. **自建 `model new` 后必须显式 `model large-strain on|off`**，在首次 `cycle`/`solve` 前设置；`model restore` 续跑继承存档设置。
3. 阶段脚本命名：`<前缀>_<两位序号>_<动作>.py`；共享参数：`<前缀>_geom.py`；无头入口：`*_console.py`。
4. 参数集中在 `data/`，GUI 与 console 共用；脚本写死参数会造成数值漂移。
4a. **维度判定不要依赖 `itasca.dimension()`**：本机 GUI 内 `itasca` 为 built-in 模块，实测无 `dimension()` / `vec2` 构造器；可靠方式是建球看 `ball.pos()` 返回 `vec2`（2D）或 `vec3`（3D）。详见 `examples/GUI_DYNAMIC_ACCEPTANCE.md` §5。
5. 存档放 `work/`（`.sav` / `.p2sav` / `.p3sav`），成果放 `outputs/<模式>/`。
6. Bridge 用进程 CWD 冻结根路径，启动脚本必须把工作目录固定到工作区根目录。

## 3.1 PoC 实测补充的 PFC2D 操作要点（2026-11-25，一手证据）

1. **Domain 命令**：建立计算域用 `model domain extent -2 2 -2 2`（不是 `domain create`）；不确定时用 `itasca_query_command(query="domain create", software="pfc", version="9.0")` 查证，不猜命令。
2. **2D/3D 坐标维度不同**：PFC2D 的 `ball create position=(x,y)` 是二维；PFC3D 才是三维。脚本跨维度复用时需注意。
3. **球必须有质量才能 cycle**：创建球后需 `ball attribute density 2500 range id 1 2`，否则 `model cycle` 报 `zero inertial mass`。
4. **ball 列表 API**：`itasca.ball.list()` 返回单个 Ball 对象（不可 `len()`），统计用 `len(list(itasca.ball.list()))`。
5. `itasca` 模块无 `dimension()` 属性，不要假定 API 存在。
6. 第一次任务失败时 `check_task_status` 返回 `task_status=failed` 与完整 `error`，不得把失败当作成功继续。

## 3.2 E2E 验收补充的建模要点（2026-11-25，一手证据）

1. **接触模型命令是 `contact cmat default`**（不是 `cmodel`）：`contact cmat default model linear property kn 1e8 ks 5e7 fric 0.5 dp_nratio 0.7`。不设置会导致球间无接触、timestep 爆炸到 9.78E+09、加载无效。
2. **墙生成**：`wall generate name 'top' box ... one-wall`——不加 `one-wall` 时 box 会拆成 4 面独立墙并自动分配 ID，后续指定 ID 会冲突。
3. **ball generate 受区域限制**：可能提示 "Fewer balls were generated than specified"，属正常现象，需按实际生成数继续。
4. **vec2 分量是方法**：`b.pos().y()` 返回坐标，不是 `b.pos().y`；`b.pos()` 需在 ball 对象上调用（不是 `itasca.ball.pos(b)`）。
5. **任务 completed ≠ 物理有效**：必须检查物理指标（contacts 数、timestep、试样尺寸变化）。timestep 异常增长是"无有效接触"的强信号。Agent 应主动识别并汇报，不得仅凭 task_status=completed 宣称成功。
6. **胶结成键（2026-11-26 完整物理 E2E 实证）**：把线性接触切换为 `linearpbond` 后，**已有接触不会自动成键**——实测 `bonded=0`、试样加载即散架。正确流程（brazil-pfc br_03）四步缺一不可：
   - 接触模型用 `method deform emod ... kratio ... pb_deformability emod ... kratio ...`（不是 `method deformability`；`property emod` 在 PFC9 是只读会报错）；
   - 改 cmat 后执行 `contact cmat apply` + `model clean`；
   - `contact method bond gap <gap>` 前后各做一次 `model cycle <n> calm 20` 平衡；
   - 成键数必须实测确认：`contact.prop(ct,'pb_state') = 3` 才是真粘结，本流程实测 `bonded=5268`。**不要假定接触模型设为 linearpbond 就等于成键。**
7. **撤围压后的应力释放**：圆墙成样试样含预压应力，撤墙换压板后应力会先释放再重新建立；加载初期的应力下降可能是释放而非材料破坏，判断峰值须跳过该瞬态。这条属**待复核的物理诊断**，不是已证实的根因。

## 4. Bridge 状态与启动

- Bridge 默认 `http://localhost:9001`；MCP 文档服务 `http://127.0.0.1:8000/mcp`；
- GUI 启动：引擎 IPython 控制台 `import itasca_mcp_bridge; itasca_mcp_bridge.start()`；
- Console 无头：agent 可通过引擎 `console.exe` 启动 bridge；本机为 `pfc2d9_console.exe` / `pfc3d9_console.exe`；
- `start()` 默认自升级；PR0 锁定 0.6.11 后，所有验证必须设 `ITASCA_MCP_BRIDGE_AUTO_UPGRADE=0` 或 `auto_upgrade=False`，防止版本漂移；
- 连接失败错误形态：`error.code = bridge_unavailable`，action 提示在引擎内启动 bridge。遇到此错误时明确告知用户 bridge 未运行，不假装工具执行成功。

## 5. 明确不做

- 不实现新的 MCP Server 包装 itasca-mcp；
- 不复制 execute / status / interrupt / history 工具；
- 不自建任务注册表、状态机、事件库、检查点管理器（阶段检查点由实验脚本自己维护）；
- 不把 GUI 绘图能力假定在 Console 可用。
