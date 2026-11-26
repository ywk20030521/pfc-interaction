"""4.0 question-panel quality acceptance (Nature design + PFC manual basis).

Run: python -m unittest tests.test_v40_question_quality -v
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from core import (  # noqa: E402
    ArtifactStore, Question, Option, V41CoreDispatcher, CoreDispatcher,
    AUTHOR_INPUT_NEEDED, to_decision_questions, meta_for, apply_answers,
)
from modules import nature_experiment_design as ned  # noqa: E402


class TestQuestionSchema(unittest.TestCase):
    def test_panel_prompt_is_concise(self):
        """Spec 6.2: panel shows title + one-sentence description only.
        Operator feedback: no group tags / '为什么问' / '依据' labels."""
        q = Question(id="conf", prompt="围压范围", title="围压取哪些水平?",
                     description="围压是唯一自变量，其余条件固定。",
                     group="变量与对照组", why="自变量决定矩阵", unit="MPa",
                     options=[Option("1,5,10", [1, 5, 10], unit="MPa",
                                     source="user_provided", basis="M1 假设")],
                     allow_free_text=True, progress_idx=2, progress_total=4)
        d = q.to_decision_question()
        self.assertEqual(d["question"],
                         "围压取哪些水平?\n围压是唯一自变量，其余条件固定。")
        for bad in ("[2/4]", "变量与对照组", "为什么问", "依据"):
            self.assertNotIn(bad, d["question"])
        # Stage tag is in the header, not the prompt.
        self.assertIn(d["header"], ("实验设计·关键决策", "实验设计·参数决策"))
        # Metadata stays in question_meta for audit.
        meta = meta_for([q])[0]
        self.assertEqual(meta["progress_idx"], 2)
        self.assertIn("自变量决定矩阵", meta["why"])
        self.assertIn("M1 假设", meta["options"][0]["basis"])
        self.assertTrue(d["allow_free_text"])
        self.assertTrue(any(o.get("free_text") for o in d["options"]))

    def test_author_input_needed_not_invented(self):
        q = Question(id="n", prompt="独立重复 n", author_input_needed=True,
                     options=[Option(AUTHOR_INPUT_NEEDED, AUTHOR_INPUT_NEEDED)])
        d = q.to_decision_question()
        self.assertNotIn(AUTHOR_INPUT_NEEDED, d["question"])
        self.assertTrue(d["author_input_needed"])
        self.assertEqual(apply_answers([q], {"n": AUTHOR_INPUT_NEEDED})["n"],
                         AUTHOR_INPUT_NEEDED)


class TestNatureDesign(unittest.TestCase):
    def test_four_design_questions(self):
        qs = ned.nature_questions("三轴压缩")
        self.assertEqual([q.id for q in qs],
                         ["control_group", "independent_unit",
                          "randomization", "stat_plan"])
        self.assertTrue(any(q.author_input_needed for q in qs))

    def test_design_review_flags_missing_controls(self):
        r = ned.design_review({})
        self.assertEqual(r["counts"]["P0"], 2)   # control + independent unit
        self.assertEqual(r["counts"]["P1"], 1)   # stat plan
        self.assertFalse(r["imports_posthoc_analysis"])

    def test_design_review_clean_when_answered(self):
        r = ned.design_review({
            "control_group": "baseline_first", "independent_unit": "pfc_seed_3",
            "randomization": "not_applicable", "stat_plan": "mean_sd_effect"})
        self.assertEqual(sum(r["counts"].values()), 0)

    def test_pfc_manual_basis_distinguishes_overlap(self):
        q = ned.sample_preparation_question()
        labels = {o.label: o.basis for o in q.options}
        self.assertIn("non-overlapping", labels["ball generate（无重叠）"])
        self.assertIn("without regard for overlap", labels["ball distribute（目标孔隙率）"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
