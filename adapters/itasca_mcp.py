"""Real itasca-mcp adapter for PFC Interaction 4.0 Core.

This adapter maps Core I5 ExecutionRequest to the real itasca-mcp bridge
HTTP API. It replaces RecordingExecutor as the production execution channel.

Bridge protocol (verified against bridge 0.6.11, 2026-11-25):
  POST http://localhost:9001/execute_code
  body: {"request_id": "...", "code": "..."}
  response: {"type":"execute_code_result","status":"success",
             "data":{"output":"...","result":null}, ...}

  POST http://localhost:9001/execute_task
  body: {"request_id": "...", "entry_script": "...", "description": "..."}
  response: {"task_id": "...", ...}

  POST http://localhost:9001/check_task_status
  body: {"request_id": "...", "task_id": "...", "wait_seconds": N}

Design constraints (from references/itasca_mcp_boundary.md):
  - task_state must come from real tool results, never inferred
  - tool_task_id is mandatory for a valid ExecutionResult
  - no local reimplementation of PFC execution
"""

from __future__ import annotations

import json
import os
import tempfile
import urllib.error
import urllib.request
import uuid
from typing import Any, Dict, Optional

from core.state_machine import ExecutionResult, TaskState

DEFAULT_BRIDGE_URL = "http://localhost:9001"


class BridgeUnavailable(RuntimeError):
    pass


class ItascaMcpAdapter:
    """Production executor backed by the real itasca-mcp bridge."""

    def __init__(self, bridge_url: str = DEFAULT_BRIDGE_URL, timeout: int = 120):
        self.bridge_url = bridge_url.rstrip("/")
        self.timeout = timeout
        self.last_response: Optional[Dict[str, Any]] = None

    def _post(self, command: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        body = dict(payload)
        body.setdefault("request_id", "pfc-" + uuid.uuid4().hex[:8])
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            "%s/%s" % (self.bridge_url, command),
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                out = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, OSError) as exc:
            raise BridgeUnavailable(
                "bridge unreachable at %s: %s" % (self.bridge_url, exc)
            ) from exc
        self.last_response = out
        return out

    def health(self) -> Dict[str, Any]:
        req = urllib.request.Request("%s/health" % self.bridge_url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, OSError) as exc:
            raise BridgeUnavailable(str(exc)) from exc

    def execute_code(self, code: str) -> ExecutionResult:
        """Synchronous execution; returns real output and a real request id."""
        resp = self._post("execute_code", {"code": code})
        request_id = str(resp.get("request_id") or "")
        if resp.get("status") != "success":
            return ExecutionResult(
                tool_task_id=request_id or "unknown",
                task_state=TaskState.FAILED,
                error=str(resp.get("error") or resp.get("message") or "execution failed"),
            )
        data = resp.get("data") or {}
        return ExecutionResult(
            tool_task_id=request_id,
            task_state=TaskState.COMPLETED,
            output_artifacts=[
                {
                    "artifact_id": "bridge_output",
                    "output": str(data.get("output", "")),
                }
            ],
            evidence_refs=[request_id],
        )

    def execute_dat_script(self, script: str) -> ExecutionResult:
        """Execute a PFC .dat script via the bridge's own command splitter.

        IMPORTANT (root cause of the 2026-11-25 bridge wedge):
        Do NOT iterate lines and call itasca.command() one by one. A line
        ``fish define NAME`` puts PFC into its interactive FISH prompt; the
        C call holds the GIL while waiting for the body, freezing every
        Python thread in the process (including /health and timeout handling).
        Upstream confirmed this is by design (issue #250).

        Correct approach (verified against bridge 0.6.11):
        pass the WHOLE script as ONE ``itasca.command(<triple-quoted string>)``.
        bridge.utils.command_splitter.preprocess_source() runs before every
        execute_code and splits multi-line command calls into individual
        commands while keeping FISH definition blocks whole. Use the import
        name ``itasca`` (not an alias) so the splitter recognises the call.
        """
        wrapper = (
            "import itasca\n"
            "itasca.command(" + repr(script) + ")\n"
            "print('DAT_SCRIPT_EXECUTED')\n"
        )
        return self.execute_code(wrapper)

    def execute_task(self, entry_script: str, description: str = "") -> ExecutionResult:
        """Asynchronous task; task_state comes from the returned task_id.

        BUG-T04 (bridge 0.6.17): the parameter is `script_path`, not
        `entry_script`. Older bridge (0.6.11) accepted `entry_script`. Send
        both so the adapter works across versions. The response `data` may
        also be None on error, so guard the nested `.get`.
        """
        # BUG-T04 (bridge 0.6.17): parameter is `script_path` (not
        # `entry_script`) AND the caller must supply `task_id` (the server no
        # longer generates it). Send both legacy and new field names.
        task_id = "task-" + uuid.uuid4().hex[:8]
        resp = self._post(
            "execute_task",
            {"script_path": entry_script, "entry_script": entry_script,
             "task_id": task_id, "description": description},
        )
        data = resp.get("data") or {}
        task_id = str(resp.get("task_id") or data.get("task_id") or task_id)
        if not task_id:
            return ExecutionResult(
                tool_task_id=str(resp.get("request_id") or "unknown"),
                task_state=TaskState.FAILED,
                error="execute_task returned no task_id",
            )
        # task_state READY is what the tool reports at submission time.
        result = ExecutionResult(
            tool_task_id=task_id,
            task_state=TaskState.READY,
            evidence_refs=[task_id],
        )
        result.task_state = TaskState.READY
        return result

    def check_status(self, task_id: str, wait_seconds: int = 0) -> Dict[str, Any]:
        return self._post(
            "check_task_status",
            {"task_id": task_id, "wait_seconds": wait_seconds},
        )

    def execute(self, request: Dict[str, Any]) -> ExecutionResult:
        """Core I5 entry point."""
        operation = request.get("operation", "")
        if operation in ("execute_dat", "run_dat_script"):
            return self.execute_dat_script(str(request.get("code", "")))
        if operation in ("execute_code", "run_script_text"):
            return self.execute_code(str(request.get("code", "")))
        if operation in ("execute_task", "run_script_file"):
            script = str(request.get("model_ref") or request.get("entry_script") or "")
            return self.execute_task(script, str(request.get("expected_effect", "")))
        if operation == "check_task_status":
            resp = self.check_status(str(request.get("tool_task_id", "")))
            state = self._map_task_state(resp)
            return ExecutionResult(
                tool_task_id=str(request.get("tool_task_id", "")),
                task_state=state,
                error=None if state != TaskState.FAILED else "task failed",
            )
        return ExecutionResult(
            tool_task_id="unknown",
            task_state=TaskState.FAILED,
            error="unsupported operation: %s" % operation,
        )

    def _map_task_state(self, resp: Dict[str, Any]) -> TaskState:
        """Map bridge status string to IF0 TaskState, from tool data only."""
        raw = str(
            resp.get("task_status")
            or resp.get("status")
            or (resp.get("data") or {}).get("task_status")
            or ""
        ).lower()
        mapping = {
            "completed": TaskState.COMPLETED,
            "running": TaskState.RUNNING,
            "created": TaskState.CREATED,
            "ready": TaskState.READY,
            "paused": TaskState.PAUSED,
            "failed": TaskState.FAILED,
            "cancelled": TaskState.CANCELLED,
            "canceled": TaskState.CANCELLED,
            "recovering": TaskState.RECOVERING,
            "interrupted": TaskState.CANCELLED,
        }
        return mapping.get(raw, TaskState.RUNNING)

    def write_temp_script(self, content: str, suffix: str = ".py") -> str:
        """Helper: persist generated script to a temp file for execute_task."""
        fd, path = tempfile.mkstemp(suffix=suffix)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        return path
