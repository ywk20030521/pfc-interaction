"""PFC Interaction 5.0.1: lightweight project archive generator.

Markdown/JSON/CSV files only; no database or web service. The archive is a
logical asset set, not proof that every section has real content.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def _stage_names(cycle: Dict[str, Any]) -> List[str]:
    stages = cycle.get("stage_sequence") or cycle.get("stages") or []
    return [s.get("stage", str(s)) if isinstance(s, dict) else str(s) for s in stages]


class ResearchArchive:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _write(self, name: str, content: str) -> Path:
        path = self.root / name
        path.write_text(content.strip() + "\n", encoding="utf-8")
        return path

    def write_all(self, project: Dict[str, Any], issues: Any,
                  decisions: Any = None, evidence: Any = None,
                  hypotheses: Any = None, changes: Any = None,
                  discussion: Any = None) -> List[str]:
        issue_data = issues.snapshot() if hasattr(issues, "snapshot") else issues
        decision_data = decisions.snapshot() if decisions is not None else {}
        evidence_data = evidence.snapshot() if evidence is not None else {}
        hypothesis_data = hypotheses.snapshot() if hypotheses is not None else {}
        change_data = changes.snapshot() if changes is not None else {}
        discussion_data = discussion.snapshot() if discussion is not None else {}

        written: List[str] = []
        written.append(str(self._write("PROJECT_CHARTER.md", "\n".join([
            "# PROJECT CHARTER", "",
            f"- 课题ID: {project.get('research_task_id', '')}",
            f"- 标题: {project.get('title', '')}",
            f"- 研究目标: {project.get('objective', '待形成')}",
            f"- 边界: {project.get('boundary', '待确认')}",
            f"- 阶段: {project.get('stage', 'S1')}",
        ]))))
        written.append(str(self._write("ISSUE_TREE.md", "\n".join(
            ["# ISSUE TREE", ""]
            + [f"- {i['issue_id']} [{i['priority']}/{i['status']}] {i['title']}"
               f" (parent={i['parent_id'] or '-'}, stage={i['stage_id']},"
               f" next={i['next_action'] or '未定义'})"
               for i in issue_data.get("issues", [])]
        ))))
        written.append(str(self._write("DISCUSSION_LOG.md", "\n".join(
            ["# DISCUSSION LOG", "", "每轮必须产生新分析/证据/反例/修订；摘要由 DeepDiscussionEngine 生成。", ""]
            + [f"- {iid}: stages={', '.join(_stage_names(c))};"
               f" revisions={len(c.get('revisions', []))}"
               for iid, c in (discussion_data.items() if isinstance(discussion_data, dict) else [])]
        ))))
        written.append(str(self._write("HYPOTHESIS_REGISTER.md", "\n".join(
            ["# HYPOTHESIS REGISTER", ""]
            + [f"- {h['hypothesis_id']} [{h['maturity']}] {h['statement']}"
               f" (competing={h['competing']})"
               for h in hypothesis_data.get("hypotheses", [])]
        ))))
        written.append(str(self._write("DECISION_REGISTER.md", "\n".join(
            ["# DECISION REGISTER", ""]
            + [f"- {d.get('decision_id')} [{d.get('status')}] {d.get('topic')}"
               for d in decision_data.get("decisions", [])]
        ))))
        written.append(str(self._write("ASSUMPTION_REGISTER.md", "\n".join(
            ["# ASSUMPTION REGISTER", ""]
            + [f"- {e['evidence_id']} [{e['evidence_class']}] {e['description']}"
               for e in evidence_data.get("evidence", [])
               if e["evidence_class"] in ("UNVERIFIED_ASSUMPTION", "AGENT_INFERENCE")]
        ))))
        written.append(str(self._write("EVIDENCE_INDEX.md", "\n".join(
            ["# EVIDENCE INDEX", ""]
            + [f"- {e['evidence_id']} [{e['evidence_class']}] {e['ref']}"
               f" tool={e.get('tool_task_id') or '-'}"
               for e in evidence_data.get("evidence", [])]
        ))))
        for name, heading in (("EXPERIMENT_DESIGN.md", "EXPERIMENT DESIGN"),
                              ("MODEL_REGISTER.md", "MODEL REGISTER"),
                              ("SIMULATION_LOG.md", "SIMULATION LOG"),
                              ("ANOMALY_REGISTER.md", "ANOMALY REGISTER"),
                              ("ANALYSIS_REGISTER.md", "ANALYSIS REGISTER")):
            written.append(str(self._write(name, "# %s\n\n%s" % (
                heading, project.get(name.lower(), "待按阶段议题生成；不得用模板内容冒充完成。")))))
        written.append(str(self._write("EXPERIMENT_MATRIX.csv", "\n".join(
            ["case_id,condition,value,status"] + project.get("experiment_matrix_rows", [])
        ))))
        written.append(str(self._write("PARAMETER_REGISTER.csv", "\n".join(
            ["parameter_id,name,value,unit,source_type,status"] +
            project.get("parameter_rows", [])
        ))))
        written.append(str(self._write("CHANGELOG.md", "\n".join(
            ["# CHANGELOG", ""]
            + [f"- {c['change_id']}: {c['reason']} → issues={c['invalidated_issues']},"
               f" decisions={c['invalidated_decisions']}"
               for c in change_data.get("changes", [])]
        ))))
        (self.root / "archive_index.json").write_text(
            json.dumps({"files": [Path(p).name for p in written]},
                       ensure_ascii=False, indent=2), encoding="utf-8")
        # Structured state is what makes cross-session restore deterministic;
        # Markdown files remain human-readable projections of this state.
        state = {
            "project": project, "issues": issue_data, "decisions": decision_data,
            "evidence": evidence_data, "hypotheses": hypothesis_data,
            "changes": change_data, "discussion": discussion_data,
        }
        (self.root / "archive_state.json").write_text(
            json.dumps(state, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return written


__all__ = ["ResearchArchive"]
