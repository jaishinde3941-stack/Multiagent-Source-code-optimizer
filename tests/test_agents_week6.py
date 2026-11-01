"""
Unit tests for CoT Validator, Analysis Agent, and Optimization Agent — Week 6
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.reasoning.cot_validator import CoTValidator, CoTResult
from src.agents.analysis_agent import AnalysisAgent
from src.agents.optimization_agent import OptimizationAgent
from agent_framework import ContextManager


# ── CoT Validator ────────────────────────────────────────────────────────────

class TestCoTValidator(unittest.TestCase):

    def setUp(self):
        self.validator = CoTValidator()

    def test_valid_json_direct(self):
        cot_json = json.dumps({
            "reasoning_steps": ["Step 1", "Step 2"],
            "findings": [{"type": "bug", "description": "error", "line": 1, "severity": "high"}],
            "conclusion": "Bug found.",
            "confidence": 0.9,
        })
        result = self.validator.validate(cot_json)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.confidence, 0.9)
        self.assertEqual(len(result.reasoning_steps), 2)

    def test_valid_json_in_markdown_fence(self):
        resp = (
            "Here is my analysis:\n"
            "```json\n"
            '{"reasoning_steps": ["a"], "findings": [], "conclusion": "ok", "confidence": 0.8}\n'
            "```"
        )
        result = self.validator.validate(resp)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.conclusion, "ok")

    def test_missing_required_key(self):
        bad = json.dumps({"reasoning_steps": ["a"], "conclusion": "ok"})
        result = self.validator.validate(bad)
        self.assertFalse(result.is_valid)
        self.assertIn("confidence", result.error)

    def test_empty_reasoning_steps(self):
        bad = json.dumps({
            "reasoning_steps": [],
            "findings": [],
            "conclusion": "x",
            "confidence": 0.5,
        })
        result = self.validator.validate(bad)
        self.assertFalse(result.is_valid)

    def test_no_json_at_all(self):
        result = self.validator.validate("This is plain text, no JSON here.")
        self.assertFalse(result.is_valid)
        self.assertIsNotNone(result.error)

    def test_confidence_clamping(self):
        cot_json = json.dumps({
            "reasoning_steps": ["step"],
            "findings": [],
            "conclusion": "ok",
            "confidence": 1.5,  # out of range
        })
        result = self.validator.validate(cot_json)
        self.assertTrue(result.is_valid)
        self.assertLessEqual(result.confidence, 1.0)

    def test_optimized_code_extracted(self):
        cot_json = json.dumps({
            "reasoning_steps": ["fixed it"],
            "findings": [],
            "conclusion": "done",
            "confidence": 0.9,
            "optimized_code": "int main() { return 0; }",
        })
        result = self.validator.validate(cot_json)
        self.assertTrue(result.is_valid)
        self.assertIsNotNone(result.optimized_code)


# ── Analysis Agent ────────────────────────────────────────────────────────────

UNINIT_CODE = """
#include <iostream>
int main() {
    int x;
    int y = x + 1;
    std::cout << y << std::endl;
    return 0;
}
"""

OFF_BY_ONE_CODE = """
#include <iostream>
int main() {
    int arr[5];
    for (int i = 0; i <= 5; i++) {
        arr[i] = i * 2;
    }
    return 0;
}
"""

NESTED_LOOP_CODE = """
int bubble_sort(int* arr, int n) {
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n-i-1; j++) {
            if (arr[j] > arr[j+1]) {
                int t = arr[j]; arr[j] = arr[j+1]; arr[j+1] = t;
            }
        }
    }
    return 0;
}
"""


class TestAnalysisAgent(unittest.TestCase):

    def setUp(self):
        self.ctx   = ContextManager()
        self.agent = AnalysisAgent("analysis_test", self.ctx)

    def test_capabilities(self):
        caps = self.agent.get_capabilities()
        self.assertIsInstance(caps, list)
        self.assertGreater(len(caps), 0)

    def test_detects_uninitialized_variable(self):
        result = self.agent.process({"source_code": UNINIT_CODE, "file_path": "test.cpp"})
        types = [f["type"] for f in result["all_findings"]]
        self.assertIn("uninitialized_variable", types)

    def test_detects_off_by_one(self):
        result = self.agent.process({"source_code": OFF_BY_ONE_CODE, "file_path": "obo.cpp"})
        types = [f["type"] for f in result["all_findings"]]
        self.assertIn("off_by_one_error", types)

    def test_detects_nested_loops(self):
        result = self.agent.process({"source_code": NESTED_LOOP_CODE, "file_path": "sort.cpp"})
        types = [f["type"] for f in result["all_findings"]]
        self.assertIn("algorithmic_inefficiency", types)

    def test_result_has_required_keys(self):
        result = self.agent.process({"source_code": "int main() { return 0; }", "file_path": "ok.cpp"})
        for key in ("all_findings", "reasoning_steps", "conclusion", "confidence", "summary"):
            self.assertIn(key, result)

    def test_context_updated(self):
        self.agent.process({"source_code": UNINIT_CODE, "file_path": "t.cpp"})
        stored = self.ctx.get("analysis_results")
        self.assertIsNotNone(stored)
        self.assertIn("all_findings", stored)

    def test_empty_code_graceful(self):
        result = self.agent.process({"source_code": ""})
        self.assertIn("error", result)

    def test_on_real_testcase(self):
        tc_path = os.path.join(
            os.path.dirname(__file__), "..",
            "MicroBenchmarks", "Testcases", "TC11_buffer_overflow_loop.cpp"
        )
        if os.path.exists(tc_path):
            with open(tc_path) as f:
                code = f.read()
            result = self.agent.process({"source_code": code, "file_path": tc_path})
            self.assertGreater(len(result["all_findings"]), 0)


# ── Optimization Agent ────────────────────────────────────────────────────────

class TestOptimizationAgent(unittest.TestCase):

    def setUp(self):
        self.ctx   = ContextManager()
        self.tmpdir = tempfile.mkdtemp()
        self.agent = OptimizationAgent(
            "opt_test", self.ctx, output_dir=self.tmpdir
        )

    def test_capabilities(self):
        caps = self.agent.get_capabilities()
        self.assertIn("off_by_one_fix", caps)

    def test_fixes_off_by_one(self):
        analysis = {
            "all_findings": [{
                "type": "off_by_one_error",
                "description": "Loop uses <=",
                "line": 4, "severity": "high",
            }]
        }
        result = self.agent.process({
            "source_code": OFF_BY_ONE_CODE,
            "file_path": "test.cpp",
            "analysis_report": analysis,
        })
        opt_code = result["optimized_code"]
        # The '<=' should be replaced with '<'
        self.assertNotIn("i <= 5", opt_code)

    def test_fixes_uninit_variable(self):
        analysis = {
            "all_findings": [{
                "type": "uninitialized_variable",
                "description": "Variable 'x' declared at line 3 may be used before initialization.",
                "line": 3, "severity": "high",
            }]
        }
        result = self.agent.process({
            "source_code": UNINIT_CODE,
            "file_path": "test.cpp",
            "analysis_report": analysis,
        })
        opt_code = result["optimized_code"]
        self.assertIn("x = 0", opt_code)

    def test_diff_generated(self):
        result = self.agent.process({
            "source_code": OFF_BY_ONE_CODE,
            "file_path": "test.cpp",
            "analysis_report": {"all_findings": [{"type": "off_by_one_error",
                "description": "x", "line": 4, "severity": "high"}]},
        })
        self.assertIsInstance(result["unified_diff"], str)

    def test_output_file_saved(self):
        result = self.agent.process({
            "source_code": "int main() { return 0; }",
            "file_path": "simple.cpp",
        })
        out = result.get("output_file", "")
        self.assertTrue(os.path.exists(out))

    def test_result_has_required_keys(self):
        result = self.agent.process({
            "source_code": "int main() { return 0; }",
            "file_path": "ok.cpp",
        })
        for key in ("original_code", "optimized_code", "unified_diff",
                    "transformations", "summary", "output_file"):
            self.assertIn(key, result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
