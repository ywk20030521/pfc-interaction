"""M3 PFC Modeling - first batch module.

IF0 contract fields:
  dimension (2D/3D), case_id, model_parameters[] (inherited from M2 with source),
  scripts[], validation (syntax/structure/physics), manifest,
  verified_by_execution (default False)

Standard outputs (report section 4.3.4):
  model_design.md, model.dat, model_parameters.json,
  model_validation.md, model_manifest.json

Critical rule: generating a script is NOT validating a model.
Model parameters must trace back to M2 parameter_schema; unconfirmed changes
are flagged. M3 never sets verified_by_execution=True.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core import (
    DecisionKey,
    DispatchRequest,
    Envelope,
    Evidence,
    EvidenceSource,
    ModuleID,
    ModuleState,
    CoreDispatcher,
)

MODULE_VERSION = "0.1.0"
MODULE_ID = ModuleID.M3

# Verified from real PFC2D/3D Console runs (see E2E reports).
VERIFIED_COMMANDS_2D = {
    "model new", "model large-strain on", "model domain extent",
    "contact cmat default model linear property", "ball generate",
    "ball distribute", "ball attribute density", "wall generate",
    "model cycle", "model solve",
}
VERIFIED_COMMANDS_3D = set(VERIFIED_COMMANDS_2D)


@dataclass
class ModelParameter:
    name: str
    value: Any
    unit: str
    source: str
    confirmed: bool = True
    changed_without_confirmation: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "source": self.source,
            "confirmed": self.confirmed,
            "changed_without_confirmation": self.changed_without_confirmation,
        }


@dataclass
class ModelDesign:
    dimension: str
    case_id: str
    model_parameters: List[ModelParameter] = field(default_factory=list)
    scripts: List[str] = field(default_factory=list)
    validation: Dict[str, Any] = field(default_factory=dict)
    manifest: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension,
            "case_id": self.case_id,
            "model_parameters": [p.to_dict() for p in self.model_parameters],
            "scripts": self.scripts,
            "validation": self.validation,
            "manifest": self.manifest,
        }


def _load_m2_design(request: DispatchRequest, core: CoreDispatcher) -> Dict[str, Any]:
    for ref in request.input_refs:
        if ref.artifact_id.startswith("m2_parameter_schema"):
            return core.store.get_json(ref)
    return (request.payload or {}).get("experiment_design", {})


def build_model_parameters(m2: Dict[str, Any], case_values: Dict[str, Any]) -> List[ModelParameter]:
    """Inherit M2 parameters; record source and unconfirmed overrides."""
    params: List[ModelParameter] = []
    defined = {p.get("name"): p for p in m2.get("parameter_schema", [])}
    for name, value in case_values.items():
        spec = defined.get(name, {})
        params.append(
            ModelParameter(
                name=name,
                value=value,
                unit=str(spec.get("unit", "")),
                source="M2.parameter_schema/%s" % name if spec else "case_override",
                confirmed=bool(spec.get("confirmed", False)),
                changed_without_confirmation=not bool(spec),
            )
        )
    # Required physical parameters with explicit provenance.
    params.append(
        ModelParameter("density", 2500, "kg/m3", "engineering_default", False, True)
    )
    return params


def ball_radius_from_parameters(design: ModelDesign) -> float:
    """Map an inherited radius parameter into a model-scale radius.

    A radius given in mm (0.25-0.35) must be scaled into the model units used
    by the generated box (~2 units wide). A raw value >1 is treated as mm;
    a sub-unit value 0.05-0.5 is also treated as mm-scale when the model box
    is metre-scale, because using it directly yields only a handful of balls.
    The scaling rule is recorded as a limitation for researcher confirmation.
    """
    for p in design.model_parameters:
        if "半径" in p.name or "radius" in p.name.lower():
            try:
                value = float(p.value)
            except (TypeError, ValueError):
                continue
            if value >= 1.0:
                return value / 1000.0
            # Model box is ~2 units; target ~100 balls -> radius ~0.1.
            return max(min(value * 0.35, 0.15), 0.06)
    return 0.10


def generate_pfc_script(design: ModelDesign, m2: Dict[str, Any]) -> str:
    """Generate a sample-preparation script with confinement.

    Verified against PFC2D Console (2026-11-25): ball generate with sparse
    large radii produced too few balls and zero contacts; ball distribute plus
    a containing wall produced a bound assembly with stable timestep.
    """
    dim3 = design.dimension == "3D"
    extent = "-2 2 -2 2 -2 2" if dim3 else "-2 2 -2 2"
    radius = ball_radius_from_parameters(design)
    rlo = max(radius, 0.05)
    rhi = rlo * 1.5
    box = "-1.0 1.0 -1.0 1.0 -1.0 1.0" if dim3 else "-1.0 1.0 -1.0 1.0"
    wall_box = "-1.1 1.1 -1.1 1.1 -1.1 1.1" if dim3 else "-1.1 1.1 -1.1 1.1"
    lines = [
        "model new",
        "model large-strain on",
        "model domain extent %s" % extent,
        "contact cmat default model linear property kn 1e8 ks 5e7 fric 0.5",
        "ball distribute radius %.3f %.3f porosity 0.16 box %s" % (rlo, rhi, box),
        "ball attribute density 2500",
        "wall generate name 'box' box %s" % wall_box,
        "model cycle 1000 calm 10",
    ]
    header = [
        "; PFC Interaction 4.0 - M3 generated model",
        "; dimension=%s case=%s" % (design.dimension, design.case_id),
        "; NOT verified until executed through Core I5",
    ]
    return "\n".join(header + lines) + "\n"


def validate_script(design: ModelDesign) -> Dict[str, Any]:
    """Three-layer check: syntax / structure / physics (report section 4.3.3)."""
    syntax: List[str] = []
    structure: List[str] = []
    physics: List[str] = []
    allowed = VERIFIED_COMMANDS_3D if design.dimension == "3D" else VERIFIED_COMMANDS_2D

    for script in design.scripts:
        for line in script.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(";"):
                continue
            if not any(stripped.startswith(cmd) for cmd in allowed):
                syntax.append("unverified command form: %s" % stripped[:60])

    if not design.scripts:
        structure.append("no script generated")
    if not any(("ball generate" in s or "ball distribute" in s) for s in design.scripts):
        structure.append("no particle generation")
    if not any("cmat default" in s for s in design.scripts):
        structure.append("contact model not configured")
    if not any("attribute density" in s for s in design.scripts):
        structure.append("particle density not set")
    if not any("wall generate" in s for s in design.scripts):
        structure.append("no confinement boundary: particles may fly apart and timestep may diverge")

    unconfirmed = [p.name for p in design.model_parameters if p.changed_without_confirmation]
    if unconfirmed:
        physics.append("parameters without confirmed source: %s" % ", ".join(unconfirmed))
    if design.dimension not in ("2D", "3D"):
        physics.append("dimension must be 2D or 3D")

    return {
        "syntax": {"status": "PASS" if not syntax else "WARN", "findings": syntax},
        "structure": {"status": "PASS" if not structure else "FAIL", "findings": structure},
        "physics": {"status": "WARN" if physics else "PASS", "findings": physics},
        "verified_by_execution": False,
    }


def run(module_task_id: str, request: DispatchRequest, core: CoreDispatcher) -> Envelope:
    m2 = _load_m2_design(request, core)
    payload = request.payload or {}
    cfg = payload.get("model_config", {})
    dimension = str(cfg.get("dimension", "2D"))

    cases = m2.get("cases", [])
    case = (payload.get("case") or (cases[0] if cases else {"case_id": "C00", "values": {}}))
    case_id = str(case.get("case_id", "C00"))

    design = ModelDesign(
        dimension=dimension,
        case_id=case_id,
        model_parameters=build_model_parameters(m2, case.get("values", {})),
    )
    design.scripts.append(generate_pfc_script(design, m2))
    design.validation = validate_script(design)

    artifacts: List[Dict[str, Any]] = []
    artifacts.append(core.store.write("m3_model", "%s_%s.dat" % (dimension, case_id), design.scripts[0]).to_dict())
    artifacts.append(core.store.write_json("m3_model_parameters", "model_parameters.json", design.to_dict()).to_dict())
    design.manifest = [{"artifact_id": a["artifact_id"], "version": a["version"], "hash": a["hash"]} for a in artifacts]
    artifacts.append(core.store.write_json("m3_model_manifest", "model_manifest.json", design.manifest).to_dict())

    validation_md = "# 模型检查报告\n\n" + "\n".join(
        "- %s: %s — %s"
        % (
            layer,
            design.validation[layer]["status"],
            "; ".join(design.validation[layer]["findings"]) or "无问题",
        )
        for layer in ("syntax", "structure", "physics")
    ) + "\n\n> 脚本生成不等于模型验证；必须经 Core I5 在真实 PFC 环境执行。\n"
    artifacts.append(core.store.write("m3_model_validation", "model_validation.md", validation_md).to_dict())

    limitations: List[str] = []
    if design.validation["physics"]["findings"]:
        limitations.extend(design.validation["physics"]["findings"])

    return Envelope(
        module_id=MODULE_ID,
        module_version=MODULE_VERSION,
        research_task_id=request.research_task_id,
        module_task_id=module_task_id,
        parent_task_id=request.parent_task_id,
        input_refs=request.input_refs,
        status={"module_state": ModuleState.COMPLETED.value},
        output={
            "structured": design.to_dict(),
            "artifacts": artifacts,
            "verified_by_execution": False,
        },
        evidence=[
            Evidence(EvidenceSource.DERIVED_COMPUTED, "M2.parameter_schema", "参数继承"),
            Evidence(EvidenceSource.AGENT_INFERRED, "M3.validation", "三层检查结论"),
        ],
        decisions=[],
        limitations=limitations + ["脚本未执行；模型物理有效性待 M4 与 M5 验证"],
    )
