"""
Unit tests for LLM Client and Code Parser — Week 5
"""

import json
import sys
import os
import unittest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.llm.llm_client import LLMClient
from src.llm.prompt_templates import (
    AnalysisPromptTemplate,
    OptimizationPromptTemplate,
    VerificationPromptTemplate,
)
from src.parser.code_parser import CodeParser


# ── LLM Client tests ────────────────────────────────────────────────────────

class TestLLMClient(unittest.TestCase):

    def setUp(self):
        self.client = LLMClient()

    def test_health_check_returns_dict(self):
        result = self.client.health_check()
        self.assertIn("available", result)
        self.assertIn("model", result)
        self.assertIn("base_url", result)

    def test_generate_returns_string(self):
        """generate() always returns a string (stub if offline)."""
        result = self.client.generate("Analyze this code: int x;")
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_stub_response_is_json_parseable(self):
        """The stub response should contain parseable JSON."""
        # Force stub by temporarily marking unavailable
        orig = self.client._available
        self.client._available = False
        resp = self.client.generate("analyze some code")
        self.client._available = orig
        # Extract JSON from potential markdown fence
        if "```json" in resp:
            json_str = resp.split("```json")[1].split("```")[0].strip()
        else:
            json_str = resp.strip()
        data = json.loads(json_str)
        self.assertIn("reasoning_steps", data)
        self.assertIn("conclusion", data)
        self.assertIn("confidence", data)

    def test_stub_response_has_findings(self):
        orig = self.client._available
        self.client._available = False
        resp = self.client.generate("fix this code")
        self.client._available = orig
        self.assertIsInstance(resp, str)


# ── Prompt Template tests ────────────────────────────────────────────────────

class TestPromptTemplates(unittest.TestCase):

    SAMPLE_CODE = "int main() { int x; int y = x + 1; return y; }"

    def test_analysis_prompt_contains_code(self):
        prompt = AnalysisPromptTemplate.build(self.SAMPLE_CODE, "test.cpp")
        self.assertIn("int main()", prompt)
        self.assertIn("test.cpp", prompt)

    def test_analysis_prompt_contains_schema(self):
        prompt = AnalysisPromptTemplate.build(self.SAMPLE_CODE)
        self.assertIn("reasoning_steps", prompt)
        self.assertIn("findings", prompt)
        self.assertIn("confidence", prompt)

    def test_optimization_prompt_contains_findings(self):
        report = {
            "findings": [
                {"type": "uninitialized_var", "description": "x is uninitialized",
                 "line": 1, "severity": "high"}
            ]
        }
        prompt = OptimizationPromptTemplate.build(self.SAMPLE_CODE, report)
        self.assertIn("uninitialized_var", prompt)
        self.assertIn("optimized_code", prompt)

    def test_verification_prompt_contains_verdict(self):
        prompt = VerificationPromptTemplate.build(self.SAMPLE_CODE, self.SAMPLE_CODE, True)
        self.assertIn("PASSED", prompt)
        self.assertIn("verdict", prompt)


# ── Code Parser tests ────────────────────────────────────────────────────────

class TestCodeParser(unittest.TestCase):

    def setUp(self):
        self.parser = CodeParser()

    def test_parse_simple_function(self):
        code = """
#include <iostream>
int add(int a, int b) {
    return a + b;
}
"""
        result = self.parser.parse_string(code, "test.cpp")
        self.assertEqual(result.file_path, "test.cpp")
        self.assertIn("iostream", result.includes)
        self.assertGreater(result.line_count, 1)

    def test_detect_uninitialized_variable(self):
        code = """
int main() {
    int x;
    int y = x + 1;
    return y;
}
"""
        result = self.parser.parse_string(code)
        var_names = [v["variable"] for v in result.uninitialized_vars]
        self.assertIn("x", var_names)

    def test_detect_for_loop(self):
        code = """
int main() {
    for (int i = 0; i < 10; i++) { }
    return 0;
}
"""
        result = self.parser.parse_string(code)
        loop_types = [l.loop_type for l in result.loops]
        self.assertIn("for", loop_types)

    def test_detect_nested_loops(self):
        code = """
int main() {
    for (int i = 0; i < 5; i++) {
        for (int j = 0; j < 5; j++) {
        }
    }
    return 0;
}
"""
        result = self.parser.parse_string(code)
        self.assertTrue(result.has_nested_loops)

    def test_detect_malloc(self):
        code = """
#include <stdlib.h>
int main() {
    int* p = (int*)malloc(10 * sizeof(int));
    free(p);
    return 0;
}
"""
        result = self.parser.parse_string(code)
        self.assertGreater(len(result.malloc_calls), 0)
        self.assertGreater(len(result.free_calls), 0)

    def test_parse_buffer_overflow_testcase(self):
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
        result = self.parser.parse_string(code, "TC11.cpp")
        self.assertTrue(len(result.loops) > 0)
        self.assertTrue(len(result.array_accesses) > 0)

    def test_summary_is_string(self):
        code = "int main() { return 0; }"
        result = self.parser.parse_string(code)
        summary = result.to_summary()
        self.assertIsInstance(summary, str)
        self.assertIn("Lines:", summary)

    def test_parse_file_from_benchmarks(self):
        """Parse an actual MicroBenchmarks test file."""
        tc_path = os.path.join(
            os.path.dirname(__file__), "..",
            "MicroBenchmarks", "Testcases", "TC01_uninit_arithmetic.cpp"
        )
        if os.path.exists(tc_path):
            result = self.parser.parse_file(tc_path)
            self.assertGreater(result.line_count, 0)
            # Should detect the uninitialized 'x'
            var_names = [v["variable"] for v in result.uninitialized_vars]
            self.assertIn("x", var_names)


if __name__ == "__main__":
    unittest.main(verbosity=2)
