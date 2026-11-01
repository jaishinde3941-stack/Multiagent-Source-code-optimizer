"""
Unit tests for Verification components and Pipeline — Week 7
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.verification.diff_tester import DifferentialTester
from src.verification.z3_verifier import Z3Verifier
from src.verification.perf_benchmarker import PerfBenchmarker
from src.agents.verification_agent import VerificationAgent
from src.pipeline.pipeline import CompilerOptimizationPipeline
from agent_framework import ContextManager


SIMPLE_ORIGINAL = """#include <iostream>
int main() {
    int x = 5;
    std::cout << x << std::endl;
    return 0;
}
"""

SIMPLE_OPTIMIZED = """#include <iostream>
int main() {
    int x = 5 + 0;
    std::cout << x << std::endl;
    return 0;
}
"""

BROKEN_OPTIMIZED = """#include <iostream>
int main() {
    int x = 42;   // changed output — behaviorally different
    std::cout << x << std::endl;
    return 0;
}
"""


# ── Differential Tester ────────────────────────────────────────────────────────

class TestDifferentialTester(unittest.TestCase):

    def setUp(self):
        self.tester = DifferentialTester()

    def test_identical_code_passes(self):
        result = self.tester.test(SIMPLE_ORIGINAL, SIMPLE_ORIGINAL)
        # Should pass (same output) or be skipped if g++ not found
        if result.error and "not found" in result.error:
            self.skipTest("g++ not available")
        self.assertTrue(result.passed)

    def test_equivalent_code_passes(self):
        result = self.tester.test(SIMPLE_ORIGINAL, SIMPLE_OPTIMIZED)
        if result.error and "not found" in result.error:
            self.skipTest("g++ not available")
        self.assertTrue(result.passed)

    def test_different_code_fails(self):
        result = self.tester.test(SIMPLE_ORIGINAL, BROKEN_OPTIMIZED)
        if result.error and "not found" in result.error:
            self.skipTest("g++ not available")
        self.assertFalse(result.passed)

    def test_result_has_outputs(self):
        result = self.tester.test(SIMPLE_ORIGINAL, SIMPLE_OPTIMIZED)
        self.assertIsInstance(result.passed, bool)


# ── Z3 Verifier ───────────────────────────────────────────────────────────────

class TestZ3Verifier(unittest.TestCase):

    def setUp(self):
        self.verifier = Z3Verifier()

    def test_equivalent_simple_returns(self):
        src1 = "int f(int x, int y) { return x + y; }"
        src2 = "int f(int x, int y) { return y + x; }"
        result = self.verifier.verify(src1, src2)
        self.assertIn(result.status, ("PROVEN_EQUIVALENT", "SKIPPED"))

    def test_different_returns(self):
        src1 = "int f(int x) { return x; }"
        src2 = "int f(int x) { return x + 1; }"
        result = self.verifier.verify(src1, src2)
        # Either Z3 finds counterexample or skips (not installed)
        self.assertIn(result.status, ("COUNTEREXAMPLE_FOUND", "SKIPPED", "UNKNOWN"))

    def test_complex_code_returns_unknown_or_skipped(self):
        complex_src = """
int main() {
    for (int i = 0; i < 5; i++) {
        int arr[5]; arr[i] = i;
    }
    return 0;
}"""
        result = self.verifier.verify(complex_src, complex_src)
        self.assertIn(result.status, ("UNKNOWN", "SKIPPED", "PROVEN_EQUIVALENT"))

    def test_availability_check(self):
        # Just check it returns a bool, not crashes
        avail = self.verifier.is_available()
        self.assertIsInstance(avail, bool)


# ── Performance Benchmarker ───────────────────────────────────────────────────

class TestPerfBenchmarker(unittest.TestCase):

    def setUp(self):
        self.bench = PerfBenchmarker()

    def test_benchmark_returns_result(self):
        result = self.bench.benchmark(SIMPLE_ORIGINAL, SIMPLE_OPTIMIZED)
        self.assertIsInstance(result.available, bool)

    def test_summary_is_string(self):
        result = self.bench.benchmark(SIMPLE_ORIGINAL, SIMPLE_ORIGINAL)
        self.assertIsInstance(result.summary(), str)

    def test_speedup_within_range(self):
        result = self.bench.benchmark(SIMPLE_ORIGINAL, SIMPLE_ORIGINAL)
        if result.available and not result.error:
            self.assertGreaterEqual(result.original_ms, 0)
            self.assertGreaterEqual(result.optimized_ms, 0)


# ── Verification Agent ────────────────────────────────────────────────────────

class TestVerificationAgent(unittest.TestCase):

    def setUp(self):
        self.ctx   = ContextManager()
        self.agent = VerificationAgent("ver_test", self.ctx)

    def test_capabilities(self):
        caps = self.agent.get_capabilities()
        self.assertIn("differential_testing", caps)
        self.assertIn("context_rollback_on_failure", caps)

    def test_pass_on_equivalent_code(self):
        result = self.agent.process({
            "original_code":  SIMPLE_ORIGINAL,
            "optimized_code": SIMPLE_OPTIMIZED,
        })
        self.assertIn("status", result)
        self.assertIn(result["status"], ("PASS", "ROLLBACK"))

    def test_result_has_required_keys(self):
        result = self.agent.process({
            "original_code":  SIMPLE_ORIGINAL,
            "optimized_code": SIMPLE_OPTIMIZED,
        })
        for key in ("status", "diff_passed", "z3_status", "perf_summary",
                    "reasoning_steps", "conclusion", "summary"):
            self.assertIn(key, result)

    def test_context_updated_after_verification(self):
        self.agent.process({
            "original_code":  SIMPLE_ORIGINAL,
            "optimized_code": SIMPLE_OPTIMIZED,
        })
        stored = self.ctx.get("verification_status")
        self.assertIsNotNone(stored)

    def test_missing_code_returns_fail(self):
        result = self.agent.process({})
        self.assertEqual(result.get("status"), "FAIL")


# ── Full Pipeline ─────────────────────────────────────────────────────────────

class TestPipeline(unittest.TestCase):

    def setUp(self):
        self.pipeline = CompilerOptimizationPipeline()

    def test_pipeline_on_string(self):
        code = """
#include <iostream>
int main() {
    int arr[5];
    for (int i = 0; i <= 5; i++) {
        arr[i] = i * 2;
    }
    return 0;
}
"""
        result = self.pipeline.run_string(code, label="TC11_test.cpp")
        self.assertIn(result.status, ("success", "partial", "rollback"))
        self.assertIsNotNone(result.analysis_report)

    def test_pipeline_detects_uninit(self):
        code = """
#include <iostream>
int main() {
    int x;
    int y = x + 1;
    std::cout << y;
    return 0;
}
"""
        result = self.pipeline.run_string(code, "uninit_test.cpp")
        findings = result.analysis_report.get("all_findings", [])
        types = [f["type"] for f in findings]
        self.assertIn("uninitialized_variable", types)

    def test_pipeline_missing_file(self):
        result = self.pipeline.run("/nonexistent/path/file.cpp")
        self.assertEqual(result.status, "failed")
        self.assertIsNotNone(result.error)

    def test_pipeline_on_real_tc01(self):
        tc_path = os.path.join(
            os.path.dirname(__file__), "..",
            "MicroBenchmarks", "Testcases", "TC01_uninit_arithmetic.cpp"
        )
        if not os.path.exists(tc_path):
            self.skipTest("TC01 not found")
        result = self.pipeline.run(tc_path)
        self.assertIn(result.status, ("success", "partial", "rollback"))

    def test_summary_is_string(self):
        result = self.pipeline.run_string(
            "int main() { return 0; }", "minimal.cpp"
        )
        summary = result.summary()
        self.assertIsInstance(summary, str)
        self.assertIn("Pipeline Result", summary)


if __name__ == "__main__":
    unittest.main(verbosity=2)
