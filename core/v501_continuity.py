"""PFC Interaction 5.0.1: deterministic cross-session restore from archive.

The archive is the source of truth. Restore does not re-read raw chat; it
loads only structured summaries, decisions, evidence references and open items.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from .v501_deep_discussion import DiscussionCycle, DeepDiscussionEngine, DepthLevel, DiscussionMode
from .v501_evidence import EvidenceClass, EvidenceEntry, EvidenceManager, HypothesisManager
from .v501_issues import IssuePriority, IssueStatus, IssueTree, IssueType, ResearchIssue


class SessionRestore:
    def __init__(self, archive_root: Path) -> None:
        self.root = Path(archive_root)
        self.state_path = self.root / "archive_state.json"
        self.state: Dict[str, Any] = {}

    def load(self) -> Dict[str, Any]:
        if not self.state_path.exists():
            raise FileNotFoundError("没有可恢复的科研档案: %s" % self.state_path)
        self.state = json.loads(self.state_path.read_text(encoding="utf-8"))
        return self.state

    def restore_issue_tree(self) -> IssueTree:
        if not self.state:
            self.load()
        research_task_id = self.state.get("project", {}).get(
            "research_task_id", self.state.get("issues", {}).get("research_task_id", ""))
        tree = IssueTree(research_task_id)
        for item in self.state.get("issues", {}).get("issues", []):
            issue = ResearchIssue(
                issue_id=item["issue_id"], title=item["title"],
                issue_type=IssueType(item["issue_type"]),
                status=IssueStatus(item["status"]),
                priority=IssuePriority(item["priority"]),
                parent_id=item.get("parent_id"), stage_id=item.get("stage_id", "S1"),
                dependencies=list(item.get("dependencies", [])),
                evidence_needs=list(item.get("evidence_needs", [])),
                owner_module=item.get("owner_module", "Core"),
                next_action=item.get("next_action", ""),
                evidence_refs=list(item.get("evidence_refs", [])),
                version=int(item.get("version", 1)),
                history=list(item.get("history", [])),
                created_at=item.get("created_at", ""),
            )
            tree.issues[issue.issue_id] = issue
        return tree

    def restore_evidence(self) -> EvidenceManager:
        if not self.state:
            self.load()
        manager = EvidenceManager()
        for item in self.state.get("evidence", {}).get("evidence", []):
            entry = EvidenceEntry(
                evidence_id=item["evidence_id"],
                evidence_class=EvidenceClass(item["evidence_class"]),
                ref=item["ref"], description=item.get("description", ""),
                source=item.get("source", ""), tool_task_id=item.get("tool_task_id", ""),
                confidence=item.get("confidence", "medium"),
                created_at=item.get("created_at", ""),
            )
            manager.entries[entry.evidence_id] = entry
        return manager

    def restore_discussion(self, issues: IssueTree) -> DeepDiscussionEngine:
        if not self.state:
            self.load()
        engine = DeepDiscussionEngine(issues)
        for iid, item in self.state.get("discussion", {}).items():
            cycle = DiscussionCycle(
                issue_id=iid, depth=DepthLevel(item["depth"]),
                mode=DiscussionMode(item["mode"]),
                stages=list(item.get("stages", [])),
                revisions=list(item.get("revisions", [])),
                created_at=item.get("created_at", ""),
            )
            engine.cycles[iid] = cycle
        return engine

    def restore_all(self) -> Dict[str, Any]:
        issues = self.restore_issue_tree()
        evidence = self.restore_evidence()
        discussion = self.restore_discussion(issues)
        return {
            "state": self.state,
            "issues": issues,
            "evidence": evidence,
            "hypotheses": HypothesisManager(evidence),
            "discussion": discussion,
            "open_backlog": [i.issue_id for i in issues.backlog(
                include_provisional=True)],
        }

    def summary(self) -> Dict[str, Any]:
        restored = self.restore_all()
        state = restored["state"]
        return {
            "archive": str(self.root),
            "research_task_id": state.get("project", {}).get("research_task_id", ""),
            "issue_count": len(restored["issues"].issues),
            "evidence_count": len(restored["evidence"].entries),
            "discussion_cycles": len(restored["discussion"].cycles),
            "open_backlog": restored["open_backlog"],
            "restored": True,
        }


__all__ = ["SessionRestore"]
