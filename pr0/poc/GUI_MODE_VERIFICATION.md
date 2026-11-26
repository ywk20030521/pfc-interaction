# T12：GUI 模式验证步骤（需人工在 GUI IPython 执行）

**状态：** ✅ **G1–G6 全部实测通过（2026-11-26，PFC3D GUI / bridge 0.6.17）**，完整证据见 `examples/GUI_DYNAMIC_ACCEPTANCE.md`。  
**启动方式：** 官方 bootstrap 将 GUI 启动列为 `[USER ACTION REQUIRED]`——bridge 必须在 PFC GUI 的 IPython 控制台内启动，由操作者手动执行（本次由用户启动 PFC3D GUI 并 `start()`）。  
**前置：** 先停止当前占用 9001 的 console bridge（进程名/PID 以 `Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'pfc.*console.*\.exe' }` 实际查询为准），否则端口冲突。  
**版本注意：** 0.6.17 的 GUI 上下文改为独立 `console_history` 端点拉取，执行工具响应不再附加 `_context`；下表方法按实测更新。

---

## 手动执行步骤

### 1. 停止当前 console bridge

```powershell
# 动态查询并结束当前占用 9001 的 console 进程（不要用硬编码 PID）
$procs = Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'pfc.*(console|gui)\.exe' }
$procs | Select-Object Name,ProcessId | Format-Table -AutoSize
$procs | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
# 确认 9001 已释放
Test-NetConnection -ComputerName localhost -Port 9001
```

### 2. 启动 PFC2D GUI

```powershell
Start-Process "D:\Itasca\PFC900\exe64\pfc2d9_gui.exe"
```

### 3. 在 GUI 的 IPython 控制台执行

```python
import itasca_mcp_bridge
itasca_mcp_bridge.start(auto_upgrade=False)
```

预期输出：`Itasca MCP Bridge Server` / `http://localhost:9001` / `Mode: Qt timer`。

### 4. 验证（Agent 侧）

health 应返回 `"runtime_mode":"gui"`（而非 console）。

---

## GUI 模式专属验证项（Console 模式不成立的能力）

| 编号 | 验证项 | 方法 | 通过标准 | 实测结果 |
|---|---|---|---|---|
| G1 | runtime_mode | `/health` | = gui | ✅ gui（0.6.17） |
| G2 | 用户控制台输入捕获 | GUI IPython 输入命令 → Agent `POST /console_history` | `entries[].source=python`，含 input/output | ✅ id=65 `print('GUI_VERIFY_20261126')` |
| G3 | 视图/文件跟踪 | GUI 打开 Plot / Data 文件 → 拉取 `console_history` | `source=view` 含 `kind=plot/data_file` | ✅ id=68 Plot01 / id=71 new |
| G4 | 输入持久化游标 | 先读一次 → 用户输入 → 再读 | cursor 推进，只返回新条目、不重放 | ✅ 64→65 |
| G5 | unsaved 文件提示 | 编辑 Data 文件不保存 → 拉取 | `state.unsaved` 含文件名 | ✅ `state:{"unsaved":["new"]}` |
| G6 | 模态对话框 | 打开模态对话框 → 拉取 | `source=view` 含 `kind=dialog,event=open` | ✅ id=66/69 含 open+closed |

> 拉取命令：`POST http://localhost:9001/console_history  {"limit":20}`。MCP 工具层未暴露该命令，需走 bridge HTTP。

---

## 已由源码确认（无需实测即可写入 Skill）

- GUI 模式才安装 `install_console_capture` / `install_view_tracking`（`runtime.py` L601–624）；
- ConsoleHistory 用磁盘持久化：`console_history.jsonl` + `console_cursor.json`；
- `mode="gui"` 在无 Qt 事件循环时抛错（不能在 console.exe 里用 gui 模式）。

这些结论已写入 `references/itasca_mcp_boundary.md` 与 `pr0/ITASCA_MCP_CAPABILITY_BASELINE.md`。

---

## 结论

T12 / G1–G6 已于 2026-11-26 在 PFC3D GUI + bridge 0.6.17 上全部实测通过，详见 `examples/GUI_DYNAMIC_ACCEPTANCE.md`。GUI 专属的上下文回传（含用户输入、视图跟踪、unsaved、对话框）能力成立；Console 模式仍为 unsupported。`console_history` 为主动拉取端点，非实时推送；MCP 工具层未暴露，需走 bridge HTTP。
