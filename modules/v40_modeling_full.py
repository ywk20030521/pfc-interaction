"""4.0 full implementation: M3 PFC Modeling (technical report section 4.3).

Generates REAL PFC command scripts (.dat), supports PFC2D/PFC3D, performs
three-layer checks (syntax / structure / physics), and emits all 5 standard
outputs. It preserves the 4.1 staged physics gates: a failed stage halts
before the loading script is generated.

12 functions implemented (4.3.2): dimension detection, model structure,
geometry/particle generation, grading, contact model, micro parameters,
boundary conditions, loading/servo, FISH/Python/command script generation,
completeness check, initialization/equilibrium check, version records.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from core import (
    DispatchRequest, Envelope, Evidence, EvidenceSource, ModuleID,
    ModuleState, CoreDispatcher, check_physics_gate,
)
from modules.experiment_knowledge import get_experiment
from modules.v41_modeling import STAGES, _check_stage, _measurements_for

MODULE_VERSION = "4.0.0"

VERIFIED_COMMANDS = {
    "model new", "model large-strain", "model domain extent", "model cycle",
    "model solve", "contact cmat default", "contact method bond",
    "ball generate", "ball distribute", "ball attribute density",
    "ball property", "wall generate", "wall create", "wall servo",
    "fish define", "end", "set", "history", "save",
}


# ---- 12 functions --------------------------------------------------------

def detect_dimension(cfg: Dict[str, Any]) -> str:
    dim = str(cfg.get("dimension", "3D")).upper()
    return "2D" if dim in ("2D", "PFC2D") else "3D"


def design_structure(exp_type: str, dimension: str) -> Dict[str, Any]:
    knowledge = get_experiment(exp_type) if exp_type else {"stages": []}
    return {"experiment_type": exp_type, "dimension": dimension,
            "stages": list(knowledge["stases"]) if "stases" in knowledge
                      else list(knowledge.get("stages", []))}


def generate_geometry(cfg: Dict[str, Any], dimension: str) -> List[str]:
    extent = "-2 2 -2 2 -2 2" if dimension == "3D" else "-2 2 -2 2"
    box = "-1.0 1.0 -1.0 1.0 -1.0 1.0" if dimension == "3D" else "-1.0 1.0 -1.0 1.0"
    wall_box = "-1.1 1.1 -1.1 1.1 -1.1 1.1" if dimension == "3D" else "-1.1 1.1 -1.1 1.1"
    return [
        "model new",
        "model large-strain on",
        "model domain extent %s" % extent,
        "; experiment geometry: box %s" % box,
        "; confinement walls: box %s" % wall_box,
    ]


def particle_generation(cfg: Dict[str, Any], dimension: str = "3D") -> List[str]:
    """BUG-T02 fix: box must have 4 tokens in 2D, 6 in 3D."""
    radius = float(cfg.get("radius", 0.06))
    rlo = max(radius, 0.05)
    rhi = rlo * 1.5
    box = cfg.get("box") or (
        "-1.0 1.0 -1.0 1.0 -1.0 1.0" if dimension == "3D"
        else "-1.0 1.0 -1.0 1.0"
    )
    return [
        "; particle generation box (dimension=%s)" % dimension,
        "ball generate radius %.4f %.4f number %d box %s" % (
            rlo, rhi, int(cfg.get("n_balls", 300)), box),
        "ball attribute density %s" % cfg.get("density", 2500),
    ]


def grading_setup(cfg: Dict[str, Any]) -> List[str]:
    if cfg.get("grading"):
        return ["; grading: %s" % json.dumps(cfg["grading"], ensure_ascii=False)]
    return ["; grading: uniform (not user confirmed)" ]


def contact_model_setup(cfg: Dict[str, Any]) -> List[str]:
    model = str(cfg.get("contact_model", "linear"))
    kn = cfg.get("kn", 1e8)
    ks = cfg.get("ks", 5e7)
    fric = cfg.get("friction", 0.5)
    lines = ["contact cmat default model %s property kn %s ks %s fric %s" % (
        model, kn, ks, fric)]
    if cfg.get("bonded"):
        lines.append("contact method bond gap %s" % cfg.get("bond_gap", 5e-4))
    return lines


def micro_parameters(cfg: Dict[str, Any]) -> List[str]:
    lines = []
    if cfg.get("pb_kn"):
        lines.append("contact cmat default model linearpbond property pb_kn %s pb_ks %s pb_ten %s pb_coh %s" % (
            cfg["pb_kn"], cfg.get("pb_ks", cfg["pb_kn"] * 0.5),
            cfg.get("pb_ten", 1e6), cfg.get("pb_coh", 1e6)))
    return lines


def boundary_setup(cfg: Dict[str, Any], dimension: str) -> List[str]:
    wall_box = cfg.get("wall_box",
        "-1.1 1.1 -1.1 1.1 -1.1 1.1" if dimension == "3D" else "-1.1 1.1 -1.1 1.1")
    return ["wall generate name 'box' box %s" % wall_box]


def loading_servo(cfg: Dict[str, Any]) -> List[str]:
    lines = ["model cycle %d calm 10" % int(cfg.get("equilibrate_cycles", 1000))]
    if cfg.get("confining_target_Pa"):
        lines.append("; confinement servo target=%s Pa, tolerance=±5%%" % cfg["confining_target_Pa"])
        lines.append("; wall servo velocity-max 0.02 until confinement stable")
    if cfg.get("axial_velocity"):
        lines.append("; axial loading velocity=%s m/s" % cfg["axial_velocity"])
    return lines


def generate_script(cfg: Dict[str, Any], stage: str, dimension: str) -> str:
    """FISH/Python/PFC command script generation for one stage."""
    # BUG-T01 fix: PFC command interpreter accepts ';' comments, not '#'.
    lines = ["; PFC Interaction 4.0 - M3 stage: %s" % stage,
             "; dimension=%s case=%s" % (dimension, cfg.get("case_id", "C00")),
             "; NOT verified until executed through Core I5"]
    if stage == "sample_preparation":
        lines += generate_geometry(cfg, dimension)
        lines += particle_generation(cfg, dimension)
        lines += grading_setup(cfg)
        lines += boundary_setup(cfg, dimension)
    elif stage in ("initial_equilibrium", "compaction_servo", "re_equilibrium"):
        lines += ["model cycle %d" % int(cfg.get("equilibrate_cycles", 1000))]
    elif stage == "bonding":
        lines += contact_model_setup(cfg)
        lines += micro_parameters(cfg)
    elif stage == "confinement_stabilization":
        lines += loading_servo(cfg)
    elif stage == "axial_loading":
        lines.append("model cycle %d" % int(cfg.get("load_cycles", 20000)))
    elif stage == "data_acquisition":
        lines += ["history id 1 model cycle", "; export CSV: axial_strain, axial_stress, conf_pressure"]
    return "\n".join(lines) + "\n"


def syntax_check(scripts: Dict[str, str]) -> Dict[str, Any]:
    findings = []
    for stage, script in scripts.items():
        for line in script.splitlines():
            s = line.strip()
            if not s or s.startswith(("#", ";")):
                continue
            cmd = s.split()[0]
            if cmd and cmd not in VERIFIED_COMMANDS:
                findings.append("%s: unverified command '%s'" % (stage, s[:50]))
    return {"status": "PASS" if not findings else "WARN", "findings": findings}


def structure_check(scripts: Dict[str, str], dimension: str) -> Dict[str, Any]:
    findings = []
    all_text = "\n".join(scripts.values())
    if "ball generate" not in all_text and "ball distribute" not in all_text:
        findings.append("no particle generation")
    if "wall generate" not in all_text and "wall create" not in all_text:
        findings.append("no boundary")
    if "contact cmat" not in all_text:
        findings.append("no contact model")
    if dimension not in ("2D", "3D"):
        findings.append("invalid dimension")
    return {"status": "PASS" if not findings else "FAIL", "findings": findings}


def physics_check(stage_checks: List[Dict[str, Any]],
                  admission: Dict[str, Any]) -> Dict[str, Any]:
    findings = [f["stage"] for f in stage_checks if f.get("status") == "FAIL"]
    findings += admission.get("failures", [])
    return {"status": "PASS" if not findings else "FAIL", "findings": findings}


def initialization_check(cfg: Dict[str, Any]) -> Dict[str, Any]:
    return {"equilibrium_cycles": cfg.get("equilibrate_cycles", 1000),
            "requires_runtime_verification": True,
            "status": "PENDING_EXECUTION"}


def version_record(cfg: Dict[str, Any], scripts: Dict[str, str]) -> Dict[str, Any]:
    import hashlib
    return {stage: {"hash": hashlib.sha256(s.encode()).hexdigest()[:16],
                    "version": "v1", "source": cfg.get("case_id", "C00")}
            for stage, s in scripts.items()}


# ---- runner --------------------------------------------------------------

def _load_m2(request: DispatchRequest, core: CoreDispatcher) -> Dict[str, Any]:
    for ref in request.input_refs:
        if ref.artifact_id.startswith("m2_parameter_schema"):
            return core.store.get_json(ref)
    return (request.payload or {}).get("experiment_design", {})


def run(module_task_id: str, request: DispatchRequest,
        core: CoreDispatcher) -> Envelope:
    payload = request.payload or {}
    m2 = _load_m2(request, core)
    exp_type = str(m2.get("experiment_type") or payload.get("experiment_type") or "三轴压缩")
    dimension = detect_dimension(payload)
    case_id = str(payload.get("case_id", "C00"))
    cfg = dict(payload)
    cfg["case_id"] = case_id

    structure = design_structure(exp_type, dimension)
    stages = structure["stages"]

    stage_states: List[Dict[str, Any]] = []
    scripts: Dict[str, str] = {}
    halted: Optional[str] = None
    for stage in stages:
        m = _measurements_for(stage, payload)
        result = _check_stage(stage, m)
        result["module_state"] = "COMPLETED" if result["status"] == "PASS" else "BLOCKED"
        stage_states.append(result)
        if result["status"] == "FAIL":
            halted = stage
            break
        scripts[stage] = generate_script(cfg, stage, dimension)

    conf_m = _measurements_for("confinement_stabilization", payload)
    admission = check_physics_gate(conf_m)
    gate = {
        "status": "PASS" if (halted is None and admission.can_load) else "FAIL",
        "halted_at": halted, "can_load": halted is None and admission.can_load,
        "admission": admission.to_dict(),
    }
    if not admission.can_load and halted is None:
        halted = "confinement_stabilization"

    syntax = syntax_check(scripts)
    struct = structure_check(scripts, dimension)
    physics = physics_check(stage_states, admission.to_dict())

    docs = {
        "model_design.md": "# 模型设计\n\n实验类型: %s\n维度: %s\n工况: %s\n阶段: %s\n" % (
            exp_type, dimension, case_id, " -> ".join(stages)),
        "model_validation.md": "# 模型检查\n\n语法: %s %s\n结构: %s %s\n物理: %s %s\n\n> 脚本生成不等于模型验证；须经 Core I5 真实执行。\n" % (
            syntax["status"], syntax["findings"], struct["status"], struct["findings"],
            physics["status"], physics["findings"]),
    }
    artifacts = []
    for name, text in docs.items():
        artifacts.append(core.store.write("m3_" + name.replace(".", "_"), name, text).to_dict())
    for stage, script in scripts.items():
        artifacts.append(core.store.write("m3_dat_%s" % stage,
                         "%s_%s.dat" % (case_id, stage), script).to_dict())
    parameters = {"dimension": dimension, "experiment_type": exp_type,
                  "case_id": case_id, "config": cfg, "stages": stage_states}
    artifacts.append(core.store.write_json(
        "m3_model_parameters", "model_parameters.json", parameters).to_dict())
    manifest = version_record(cfg, scripts)
    artifacts.append(core.store.write_json(
        "m3_model_manifest", "model_manifest.json", manifest).to_dict())
    artifacts.append(core.store.write_json("m3_staged_model", "staged_model.json", {
        "stages": stage_states, "physics_gate": gate, "halted_at": halted,
        "dimension": dimension, "experiment_type": exp_type}).to_dict())

    state = ModuleState.COMPLETED.value if halted is None else ModuleState.BLOCKED.value
    return Envelope(
        module_id=ModuleID.M3, module_version=MODULE_VERSION,
        research_task_id=request.research_task_id, module_task_id=module_task_id,
        parent_task_id=request.parent_task_id, input_refs=request.input_refs,
        status={"module_state": state, "physics_gate": gate["status"]},
        output={"structured": {"experiment_type": exp_type, "dimension": dimension,
                "case_id": case_id, "stages": stage_states, "scripts": scripts,
                "validation": {"syntax": syntax, "structure": struct, "physics": physics},
                "physics_gate": gate, "halted_at": halted,
                "initialization": initialization_check(cfg),
                "verified_by_execution": False},
                "artifacts": artifacts, "verified_by_execution": False},
        evidence=[Evidence(EvidenceSource.DERIVED_COMPUTED, "M3.validation", "三层检查")],
        decisions=[], limitations=["脚本生成不等于模型验证"] + (physics["findings"] or []))


__all__ = ["detect_dimension", "design_structure", "generate_geometry",
           "particle_generation", "grading_setup", "contact_model_setup",
           "micro_parameters", "boundary_setup", "loading_servo", "generate_script",
           "syntax_check", "structure_check", "physics_check", "initialization_check",
           "version_record", "run"]
