"""PFC Interaction 4.0 professional research modules.

First batch: M1/M2/M3. Second batch: M4/M5/M6.
All modules follow the IF0 contract in references/module_contract.md.
"""

from . import m1_planning, m2_design, m3_modeling, m4_simulation, m5_diagnosis, m6_analysis
from . import v41_interview, v41_modeling, v41_runner, v41_analysis

__all__ = [
    "m1_planning",
    "m2_design",
    "m3_modeling",
    "m4_simulation",
    "m5_diagnosis",
    "m6_analysis",
    "v41_interview",
    "v41_modeling",
    "v41_runner",
    "v41_analysis",
]
