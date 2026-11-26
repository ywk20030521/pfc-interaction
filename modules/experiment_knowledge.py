"""PFC experiment type knowledge base (technical report section 4.2.3).

Covers the 8 experiment types named in the 4.0 technical report. Each entry
provides the parameter groups, required measurements, stage sequence and
physics checks that M2 (design) and M3 (modeling) share. This is domain
knowledge as *suggestions*: nothing here is auto-confirmed by the user, and
M2 still records every field's source and confirmation state explicitly.
"""

from __future__ import annotations

from typing import Any, Dict, List

# 8 experiment types from technical report 4.2.3.
EXPERIMENT_TYPES: Dict[str, Dict[str, Any]] = {
    "单轴压缩": {
        "zh": "单轴压缩", "en": "unconfined_compression",
        "typical_parameters": [
            "试样几何", "粒径及级配", "颗粒密度", "接触模型", "细观力学参数",
            "加载方式", "加载速率", "伺服控制方式", "应力应变计算口径", "破坏判据", "输出指标",
        ],
        "required_measurements": ["轴向应力", "轴向应变", "峰值强度", "弹性模量"],
        "stages": [
            "sample_preparation", "initial_equilibrium", "compaction_servo",
            "bonding", "re_equilibrium", "axial_loading", "data_acquisition",
        ],
        "analysis_metrics": ["峰值强度", "峰值应变", "E50", "泊松比", "裂纹数", "破坏模式"],
    },
    "三轴压缩": {
        "zh": "三轴压缩", "en": "triaxial_compression",
        "typical_parameters": [
            "试样形状尺寸高径比", "粒径级配孔隙率", "颗粒密度阻尼", "成样方式",
            "胶结状态与阶段", "接触模型", "胶结刚度强度摩擦角", "墙体接触模型",
            "围压目标伺服增益限速稳定判据", "轴向加载速率目标应变停止条件",
            "应力应变测量口径", "峰值峰后重复性判据",
        ],
        "required_measurements": ["轴向应力", "轴向应变", "围压", "峰值强度"],
        "stages": [
            "sample_preparation", "initial_equilibrium", "compaction_servo",
            "bonding", "re_equilibrium", "confinement_stabilization",
            "axial_loading", "data_acquisition",
        ],
        "analysis_metrics": ["峰值强度", "峰值应变", "E50", "残余强度", "围压效应"],
    },
    "巴西劈裂": {
        "zh": "巴西劈裂", "en": "brazilian_splitting",
        "typical_parameters": [
            "圆盘几何", "粒径及级配", "颗粒密度", "接触模型", "胶结参数",
            "压条宽度与接触", "加载速率", "伺服控制", "抗拉强度计算口径",
        ],
        "required_measurements": ["劈裂载荷", "抗拉强度", "裂纹演化"],
        "stages": [
            "sample_preparation", "bonding", "initial_equilibrium",
            "contact_seating", "axial_loading", "data_acquisition",
        ],
        "analysis_metrics": ["抗拉强度", "峰值载荷", "裂纹数", "破坏模式"],
    },
    "直剪试验": {
        "zh": "直剪试验", "en": "direct_shear",
        "typical_parameters": [
            "试样几何", "粒径级配", "接触模型", "法向应力", "法向伺服",
            "剪切速率", "剪切位移", "结构面参数", "强度判据",
        ],
        "required_measurements": ["剪切应力", "剪切位移", "法向应力"],
        "stages": [
            "sample_preparation", "bonding", "initial_equilibrium",
            "normal_consolidation", "shear_loading", "data_acquisition",
        ],
        "analysis_metrics": ["峰值剪切强度", "残余强度", "内摩擦角", "黏聚力"],
    },
    "岩体结构面剪切": {
        "zh": "岩体结构面剪切", "en": "joint_shear",
        "typical_parameters": [
            "结构面几何形貌", "起伏度", "粒径级配", "接触模型", "法向应力",
            "剪切速率", "结构面强度参数", "边界条件",
        ],
        "required_measurements": ["剪切应力", "法向应力", "剪切位移", "剪胀"],
        "stages": [
            "joint_sample_preparation", "initial_equilibrium",
            "normal_loading", "shear_loading", "data_acquisition",
        ],
        "analysis_metrics": ["峰值剪切强度", "残余强度", "剪胀角", "JRC估计"],
    },
    "颗粒流动": {
        "zh": "颗粒流动", "en": "particle_flow",
        "typical_parameters": [
            "颗粒粒径分布", "颗粒密度", "摩擦系数", "恢复系数", "料仓几何",
            "出口尺寸", "重力", "边界条件",
        ],
        "required_measurements": ["质量流量", "速度场", "停留时间"],
        "stages": [
            "geometry_setup", "particle_generation", "initial_equilibrium",
            "flow_loading", "data_acquisition",
        ],
        "analysis_metrics": ["质量流量", "平均速度", "停留时间分布", "堵塞判据"],
    },
    "边坡稳定性模拟": {
        "zh": "边坡稳定性模拟", "en": "slope_stability",
        "typical_parameters": [
            "边坡几何", "坡角坡高", "粒径级配", "颗粒密度", "接触模型",
            "胶结强度参数", "强度折减策略", "重力加载", "边界条件",
        ],
        "required_measurements": ["位移场", "安全系数", "破坏面位置"],
        "stages": [
            "slope_geometry", "particle_generation", "initial_equilibrium",
            "gravity_loading", "strength_reduction", "data_acquisition",
        ],
        "analysis_metrics": ["安全系数", "临界破坏面", "最大位移", "破坏模式"],
    },
    "颗粒破碎与裂纹演化": {
        "zh": "颗粒破碎与裂纹演化", "en": "particle_breakage",
        "typical_parameters": [
            "颗粒粒径级配", "颗粒强度分布", "接触模型", "胶结参数",
            "破碎判据", "加载方式", "加载速率", "裂纹统计口径",
        ],
        "required_measurements": ["破碎率", "裂纹数量", "裂纹类型", "级配演化"],
        "stages": [
            "sample_preparation", "bonding", "initial_equilibrium",
            "loading", "crack_tracking", "data_acquisition",
        ],
        "analysis_metrics": ["破碎率", "裂纹数", "裂纹类型分布", "级配演化"],
    },
}


def get_experiment(name: str) -> Dict[str, Any]:
    """Return knowledge for a supported experiment type."""
    if name not in EXPERIMENT_TYPES:
        raise KeyError("unsupported experiment type: %s" % name)
    return EXPERIMENT_TYPES[name]


def supported_types() -> List[str]:
    return list(EXPERIMENT_TYPES.keys())


def required_measurements(name: str) -> List[str]:
    return list(get_experiment(name)["required_measurements"])


def stages_for(name: str) -> List[str]:
    return list(get_experiment(name)["stages"])


def build_experiment_detail_fields(name: str, overrides: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Build M2 field definitions from knowledge, with per-field source/confirmed.

    Knowledge supplies *suggested* fields; confirmed=False until the operator
    answers in M2 negotiation. ``overrides`` lets a caller (e.g. triaxial 13
    field schema) refine units/questions without changing provenance rules.
    """
    knowledge = get_experiment(name)
    fields: List[Dict[str, Any]] = []
    for idx, param in enumerate(knowledge["typical_parameters"], start=1):
        fields.append({
            "key": "field_%02d" % idx,
            "name": param,
            "unit": "-",
            "question": "请确认 %s 的取值与单位" % param,
            "options": ["用户给定", "Agent 建议后确认", "沿用默认值"],
            "source": "EXPERIMENT_KNOWLEDGE/%s" % name,
            "confirmed": False,
            "default": None,
            "missing_risk": "未确认：不得进入 M3",
        })
    if overrides:
        for ov in overrides:
            for f in fields:
                if ov.get("name") == f["name"] or ov.get("key") == f["key"]:
                    f.update(ov)
    return fields


__all__ = [
    "EXPERIMENT_TYPES", "get_experiment", "supported_types",
    "required_measurements", "stages_for", "build_experiment_detail_fields",
]
