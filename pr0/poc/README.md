# PR0 PoC 执行脚本

用途：在本地启动 PFC console + bridge，关闭 PR0 动态验证项。脚本已锁定版本（禁用 bridge 自升级）。

> **执行状态（2026-11-25）**：PFC2D Console 已成功启动并完成 PoC-1 的 T1–T10 验证（见 `../ITASCA_MCP_CAPABILITY_BASELINE.md` §3.1）。T11（PFC3D）/T12（GUI）待验证。bridge 进程当前以后台任务方式运行。

## 一键启动（PowerShell，需在许可可用的机器上手动执行）

```powershell
# 工作目录固定为工作区根（bridge 用 CWD 冻结根路径）
Set-Location "D:\Python\itasca-mcp"

# PFC2D 无头启动 bridge（start() 不返回，进程常驻；保持此终端开启）
& "D:\Itasca\PFC900\exe64\pfc2d9_console.exe" "D:\Python\itasca-mcp\PFC Interaction Skill\pfc-interaction\pr0\poc\start_bridge_p2d.dat"

# PFC3D（二选一）
& "D:\Itasca\PFC900\exe64\pfc3d9_console.exe" "D:\Python\itasca-mcp\PFC Interaction Skill\pfc-interaction\pr0\poc\start_bridge_p3d.dat"
```

GUI 模式替代：在 PFC GUI 的 IPython 控制台执行：

```python
import itasca_mcp_bridge
itasca_mcp_bridge.start(auto_upgrade=False)
```

## 健康检查

```powershell
Invoke-RestMethod -Uri http://localhost:9001/health
# 预期 status=success, version=0.6.11, runtime_mode=console 或 gui
```

## 版本锁定说明

- `auto_upgrade=False` 阻止 bridge 启动时从 PyPI 自升级（默认行为会升级，导致版本漂移）；
- 等价的环境变量方式：`$env:ITASCA_MCP_BRIDGE_AUTO_UPGRADE="0"`；
- 锁定基线：itasca-mcp 0.8.1 / bridge 0.6.11。

## 启动后由 Agent 执行的验证

bridge 在线后，让 Agent 按 `ITASCA_MCP_CAPABILITY_BASELINE.md` §5 的 T1–T12 逐项验证。最小连通性检查：

```
itasca_execute_code:
  code = "import sys; print(sys.version); print(sys.executable)"
  timeout = 20
```

成功返回 `ok:true` + 引擎 Python 版本，即通信链路打通。

## 已知限制

- Console 模式下用户直接键入不可观察（`runtime.py` 源码定论）；GUI 模式才有 console capture；
- Console 构建不能出图（`plot` 命令静默空操作）；
- `start()` 不返回，console 进程需保持运行；停止用 Ctrl+C 或关闭进程。
