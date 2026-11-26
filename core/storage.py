"""IF0 section 4: versioned artifacts with integrity hashes; raw data is read-only."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .contract import ArtifactRef


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def hash_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


@dataclass
class StoredArtifact:
    ref: ArtifactRef
    absolute_path: str


class ArtifactStore:
    """Filesystem-backed artifact registry.

    Each write creates a new version; existing versions are never overwritten.
    Artifacts registered as raw are immutable.
    """

    def __init__(self, root: str) -> None:
        self.root = os.path.abspath(root)
        os.makedirs(self.root, exist_ok=True)
        self._index_path = os.path.join(self.root, "artifact_index.json")
        self._index: Dict[str, List[Dict[str, Any]]] = self._load_index()

    def _load_index(self) -> Dict[str, List[Dict[str, Any]]]:
        if not os.path.exists(self._index_path):
            return {}
        with open(self._index_path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def _save_index(self) -> None:
        with open(self._index_path, "w", encoding="utf-8") as fh:
            json.dump(self._index, fh, ensure_ascii=False, indent=2)

    def write(
        self,
        artifact_id: str,
        relative_path: str,
        content: str,
        raw: bool = False,
    ) -> ArtifactRef:
        versions = self._index.get(artifact_id, [])
        version = "v%d" % (len(versions) + 1)
        rel = "%s/%s" % (version, relative_path.lstrip("/"))
        absolute = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(absolute), exist_ok=True)
        data = content.encode("utf-8")
        with open(absolute, "wb") as fh:
            fh.write(data)
        ref = ArtifactRef(
            artifact_id=artifact_id,
            path=rel.replace("\\", "/"),
            version=version,
            hash=hash_bytes(data),
        )
        record = ref.to_dict()
        record["absolute_path"] = absolute
        record["raw"] = raw
        versions.append(record)
        self._index[artifact_id] = versions
        self._save_index()
        return ref

    def write_json(self, artifact_id: str, relative_path: str, obj: Any) -> ArtifactRef:
        return self.write(
            artifact_id,
            relative_path,
            json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True),
        )

    def get(self, ref: ArtifactRef) -> str:
        candidates = self._index.get(ref.artifact_id, [])
        match = None
        for entry in candidates:
            if entry["version"] == ref.version:
                match = entry
                break
        if match is None:
            raise KeyError("artifact version not found: %s/%s" % (ref.artifact_id, ref.version))
        path = match["absolute_path"]
        with open(path, "r", encoding="utf-8") as fh:
            content = fh.read()
        if hash_bytes(content.encode("utf-8")) != ref.hash:
            raise ValueError("artifact hash mismatch: %s" % ref.artifact_id)
        return content

    def get_json(self, ref: ArtifactRef) -> Any:
        return json.loads(self.get(ref))

    def verify(self, ref: ArtifactRef) -> bool:
        try:
            self.get(ref)
            return True
        except (KeyError, ValueError, OSError):
            return False

    def raw_ids(self) -> List[str]:
        return [
            aid
            for aid, versions in self._index.items()
            if versions and versions[-1].get("raw")
        ]
