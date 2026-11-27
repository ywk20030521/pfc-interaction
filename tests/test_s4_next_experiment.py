"""PR-S4-3: next-best-experiment engine acceptance tests."""

from __future__ import annotations

import os
import sys
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from core.s4_contracts import CalibrationProject, ModelCondition  # noqa: E402
from core.s4_next_experiment import ACTIONS, NextExperimentEngine  # noqa: E402


def setup():
    project = CalibrationProject("p", "nbe", ModelCondition(
        contact_model="LINEAR_PARALLEL_BOND", pfc_version="9.0"))
    return project, NextExperimentEngine(project)


def candidates():
    return [
        {"action": "single_perturbation", "information_gain": 0.2, "cost": 3,
         "parameter_uncertainty": 0.3, "scientific_value": 0.1,
         "rationale": "继续调刚度"},
        {"action": "new_observation", "information_gain": 1.0, "cost": 2,
         "parameter_uncertainty": 0.8, "scientific_value": 0.9,
         "rationale": "增加泊松比观测以区分两种刚度"},
    ]


class TestS4NextExperiment(unittest.TestCase):
    def test_invalid_action_and_cost(self):
        project, engine = setup()
        with self.assertRaises(ValueError):
            engine.evaluate([])
        with self.assertRaises(ValueError):
            engine.evaluate([{"action": "magic", "cost": 1}])
        with self.assertRaises(ValueError):
            engine.evaluate([{"action": "single_perturbation", "cost": 0}])

    def test_scores_by_information_gain_and_cost(self):
        project, engine = setup()
        result = engine.evaluate(candidates())
        self.assertEqual(result["chosen"]["action"], "new_observation")
        self.assertTrue(result["pause_parameter_search"])
        self.assertTrue(result["requires_user_authorization"])
        self.assertEqual(len(result["rejected"]), 1)
        self.assertGreater(result["chosen"]["score"], result["rejected"][0]["score"])

    def test_compensation_forbids_blind_search(self):
        project, engine = setup()
        result = engine.evaluate(candidates(), compensation_detected=True)
        self.assertEqual(result["chosen"]["action"], "new_observation")
        self.assertTrue(result["forced_by_compensation"])
        single = next(r for r in result["rejected"] if r["action"] == "single_perturbation")
        self.assertIn("补偿", single["reason"])

    def test_equivalent_solutions_trigger_new_condition(self):
        project, engine = setup()
        result = engine.evaluate(candidates(), equivalent_solutions=True)
        self.assertNotIn(result["chosen"]["action"], ("single_perturbation", "joint_perturbation"))
        self.assertTrue(result["pause_parameter_search"])

    def test_history_recorded(self):
        project, engine = setup()
        engine.evaluate(candidates())
        self.assertIsNotNone(engine.last())
        self.assertIn("next_experiment", [h["event"] for h in project.history])

    def test_all_actions_defined(self):
        self.assertEqual(len(ACTIONS), 6)


if __name__ == "__main__":
    unittest.main()
