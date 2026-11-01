"""
test_security_week8.py — Week 8 Security Agent Tests

Covers:
  - SecurityAgent Layer 1: rule-based detection
  - SecurityAgent Layer 2: heuristic detection
  - SecurityPromptTemplate structure
  - New-vulnerability detection and rollback logic
  - Full 4-stage pipeline integration on real test cases
  - cppcheck integration (skipped if not installed)
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agents.security_agent import SecurityAgent
from src.llm.prompt_templates import SecurityPromptTemplate
from agent_framework import ContextManager

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def ctx():
    return ContextManager()


@pytest.fixture
def mock_llm():
    """LLM that returns a valid stub CoT JSON (no real Ollama needed)."""
    llm = MagicMock()
    llm._available = False
    llm.generate.return_value = (
        '```json\n'
        '{\n'
        '  "reasoning_steps": ["Analyzed code for vulnerabilities."],\n'
        '  "findings": [],\n'
        '  "overall_risk": "none",\n'
        '  "conclusion": "No new vulnerabilities found.",\n'
        '  "confidence": 0.7\n'
        '}\n'
        '```'
    )
    return llm


@pytest.fixture
def agent(ctx, mock_llm):
    return SecurityAgent("sec_test", ctx, llm_client=mock_llm)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run(agent, original, optimized, file_path="test.cpp"):
    return agent.process({
        "original_code":  original,
        "optimized_code": optimized,
        "file_path":      file_path,
    })


# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 1: Rule-based detection
# ═══════════════════════════════════════════════════════════════════════════════

class TestRuleBasedDetection:

    def test_gets_flagged(self, agent):
        code = '#include <stdio.h>\nvoid f() { char buf[64]; gets(buf); }'
        result = _run(agent, code, code)
        types = [v["type"] for v in result["all_vulnerabilities"]]
        assert "unsafe_gets" in types

    def test_gets_severity_high(self, agent):
        code = 'void f() { char buf[64]; gets(buf); }'
        result = _run(agent, code, code)
        gets_finding = next(
            v for v in result["all_vulnerabilities"] if v["type"] == "unsafe_gets"
        )
        assert gets_finding["severity"] == "high"
        assert gets_finding["confidence"] == 0.9
        assert gets_finding["source"] == "rule"

    def test_strcpy_flagged(self, agent):
        code = 'void f(char* s) { char buf[64]; strcpy(buf, s); }'
        result = _run(agent, code, code)
        types = [v["type"] for v in result["all_vulnerabilities"]]
        assert "unsafe_strcpy" in types

    def test_sprintf_flagged(self, agent):
        code = 'void f(char* s) { char buf[64]; sprintf(buf, s); }'
        result = _run(agent, code, code)
        types = [v["type"] for v in result["all_vulnerabilities"]]
        assert "unsafe_sprintf" in types

    def test_format_string_bug_flagged(self, agent):
        code = 'void f(char* msg) { printf(msg); }'
        result = _run(agent, code, code)
        types = [v["type"] for v in result["all_vulnerabilities"]]
        assert "format_string_bug" in types

    def test_format_string_literal_not_flagged(self, agent):
        """printf("Hello %s", name) is safe — the format arg is a literal."""
        code = 'void f(char* name) { printf("Hello %s\\n", name); }'
        result = _run(agent, code, code)
        types = [v["type"] for v in result["all_vulnerabilities"]]
        assert "format_string_bug" not in types

    def test_use_after_free_flagged(self, agent):
        code = (
            '#include <stdlib.h>\n'
            'void f() {\n'
            '  int* p = (int*)malloc(4);\n'
            '  free(p);\n'
            '  *p = 42;\n'
            '}\n'
        )
        result = _run(agent, code, code)
        types = [v["type"] for v in result["all_vulnerabilities"]]
        assert "use_after_free" in types

    def test_safe_code_no_rule_findings(self, agent):
        safe_code = (
            '#include <stdio.h>\n'
            '#include <string.h>\n'
            'void f(const char* src) {\n'
            '    char buf[64];\n'
            '    strncpy(buf, src, sizeof(buf) - 1);\n'
            '    buf[63] = "\\0";\n'
            '    printf("%s\\n", buf);\n'
            '}\n'
        )
        result = _run(agent, safe_code, safe_code)
        rule_findings = [
            v for v in result["all_vulnerabilities"] if v.get("source") == "rule"
        ]
        assert len(rule_findings) == 0, f"Unexpected: {rule_findings}"


# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 2: Heuristic detection
# ═══════════════════════════════════════════════════════════════════════════════

class TestHeuristicDetection:

    def test_taint_flow_detected(self, agent):
        """scanf → strcpy without size check triggers taint flow heuristic."""
        code = (
            '#include <stdio.h>\n'
            '#include <string.h>\n'
            'void f() {\n'
            '    char src[256], dst[64];\n'
            '    scanf("%s", src);\n'
            '    strcpy(dst, src);\n'
            '}\n'
        )
        result = _run(agent, code, code)
        types = [v["type"] for v in result["all_vulnerabilities"]]
        assert "taint_flow_risk" in types

    def test_unchecked_malloc_detected(self, agent):
        code = (
            '#include <stdlib.h>\n'
            'void f() {\n'
            '    int* p = (int*)malloc(100 * sizeof(int));\n'
            '    p[0] = 1;\n'
            '}\n'
        )
        result = _run(agent, code, code)
        types = [v["type"] for v in result["all_vulnerabilities"]]
        assert "unchecked_malloc" in types

    def test_unchecked_malloc_not_flagged_when_checked(self, agent):
        code = (
            '#include <stdlib.h>\n'
            '#include <assert.h>\n'
            'void f() {\n'
            '    int* p = (int*)malloc(100 * sizeof(int));\n'
            '    assert(p);\n'
            '    p[0] = 1;\n'
            '}\n'
        )
        result = _run(agent, code, code)
        h_types = [
            v["type"] for v in result["all_vulnerabilities"]
            if v.get("source") == "heuristic"
        ]
        assert "unchecked_malloc" not in h_types

    def test_int_overflow_malloc_detected(self, agent):
        code = (
            '#include <stdlib.h>\n'
            'void f(int a, int b) {\n'
            '    int* p = (int*)malloc(a * b);\n'
            '}\n'
        )
        result = _run(agent, code, code)
        types = [v["type"] for v in result["all_vulnerabilities"]]
        assert "integer_overflow_malloc" in types

    def test_buffer_loop_write_detected(self, agent):
        code = (
            'void f(int n) {\n'
            '    char buf[64];\n'
            '    for (int i = 0; i < n; i++) {\n'
            '        buf[i] = "A";\n'
            '    }\n'
            '}\n'
        )
        result = _run(agent, code, code)
        types = [v["type"] for v in result["all_vulnerabilities"]]
        assert "unbounded_loop_write" in types


# ═══════════════════════════════════════════════════════════════════════════════
# New vulnerability detection & rollback
# ═══════════════════════════════════════════════════════════════════════════════

class TestNewVulnerabilityDetection:

    def test_new_vuln_detected_when_not_in_original(self, agent):
        original  = 'void f() { char buf[64]; strncpy(buf, "hi", 63); }'
        optimized = 'void f() { char buf[64]; gets(buf); }'
        result = _run(agent, original, optimized)
        new_types = [v["type"] for v in result["new_vulnerabilities"]]
        assert "unsafe_gets" in new_types

    def test_preexisting_vuln_not_in_new_vulns(self, agent):
        """gets() in both original and optimized → not a new vulnerability."""
        code = 'void f() { char buf[64]; gets(buf); }'
        result = _run(agent, code, code)
        new_types = [v["type"] for v in result["new_vulnerabilities"]]
        assert "unsafe_gets" not in new_types

    def test_rollback_triggered_on_new_high_severity(self, ctx, mock_llm):
        """A new HIGH rule-based finding must trigger rollback."""
        agent = SecurityAgent("sec_rb", ctx, llm_client=mock_llm)
        # Put something in context so rollback has state to revert
        ctx.set("original_code", "void f() {}")
        ctx.set("optimized_code", "void f() { gets(buf); }")

        original  = 'void f() {}'
        optimized = 'void f() { char buf[64]; gets(buf); }'
        result = _run(agent, original, optimized)
        assert result["status"] == "ROLLBACK"
        assert len(result["rollback_triggers"]) > 0

    def test_no_rollback_when_no_new_high_severity(self, ctx, mock_llm):
        """Pre-existing gets() should NOT trigger rollback."""
        agent = SecurityAgent("sec_no_rb", ctx, llm_client=mock_llm)
        code = 'void f() { char buf[64]; gets(buf); }'
        result = _run(agent, code, code)
        assert result["status"] == "PASS"
        assert len(result["rollback_triggers"]) == 0

    def test_llm_only_finding_does_not_trigger_rollback(self, ctx):
        """LLM findings alone must not trigger rollback, only rules/heuristics can."""
        llm = MagicMock()
        llm._available = True
        # LLM reports a high-severity finding
        llm.generate.return_value = (
            '```json\n'
            '{\n'
            '  "reasoning_steps": ["Found a SQL injection risk."],\n'
            '  "findings": [{"type": "sql_injection", "severity": "high", '
            '    "line": 5, "description": "SQL risk", "cwe_id": "CWE-89", '
            '    "recommendation": "Use prepared statements"}],\n'
            '  "overall_risk": "high",\n'
            '  "conclusion": "SQL injection risk detected.",\n'
            '  "confidence": 0.9\n'
            '}\n'
            '```'
        )
        agent = SecurityAgent("sec_llm", ctx, llm_client=llm)
        safe_code = 'void f() { int x = 1; }'
        result = _run(agent, safe_code, safe_code)
        # sql_injection is only from LLM → should NOT rollback
        assert result["status"] == "PASS"


# ═══════════════════════════════════════════════════════════════════════════════
# SecurityPromptTemplate
# ═══════════════════════════════════════════════════════════════════════════════

class TestSecurityPromptTemplate:

    def test_build_contains_required_schema_keys(self):
        prompt = SecurityPromptTemplate.build("void f() {}")
        for key in ["reasoning_steps", "findings", "overall_risk",
                    "conclusion", "confidence"]:
            assert key in prompt, f"Missing key: {key}"

    def test_build_includes_code(self):
        code = "void secret_function() { return 42; }"
        prompt = SecurityPromptTemplate.build(code)
        assert "secret_function" in prompt

    def test_build_with_baseline_types_includes_note(self):
        prompt = SecurityPromptTemplate.build(
            optimized_code="void f() {}",
            original_code="void f() { gets(buf); }",
            baseline_types=["unsafe_gets"],
        )
        assert "unsafe_gets" in prompt
        assert "ALREADY present" in prompt

    def test_system_prompt_not_empty(self):
        assert len(SecurityPromptTemplate.SYSTEM) > 10


# ═══════════════════════════════════════════════════════════════════════════════
# cppcheck integration (skip if not available)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(
    not SecurityAgent._check_cppcheck(),
    reason="cppcheck not installed",
)
class TestCppcheckIntegration:

    def test_cppcheck_runs_without_crash(self, agent):
        code = '#include <stdio.h>\nvoid f() { char buf[4]; gets(buf); }'
        findings = agent._cppcheck_scan(code, "test.cpp")
        # Just verify it returned a list (may be empty on some cppcheck versions)
        assert isinstance(findings, list)

    def test_cppcheck_source_label(self, agent):
        code = 'void f() { int* p = 0; *p = 1; }'
        findings = agent._cppcheck_scan(code, "test.cpp")
        for f in findings:
            assert f["source"] == "cppcheck"
            assert "cppcheck_" in f["type"]


# ═══════════════════════════════════════════════════════════════════════════════
# Overall risk computation
# ═══════════════════════════════════════════════════════════════════════════════

class TestRiskComputation:

    def test_no_findings_is_none_risk(self, agent):
        assert agent._compute_risk([]) == "none"

    def test_single_high_is_high_risk(self, agent):
        findings = [{"severity": "high"}]
        assert agent._compute_risk(findings) == "high"

    def test_three_high_is_critical(self, agent):
        findings = [{"severity": "high"}] * 3
        assert agent._compute_risk(findings) == "critical"

    def test_medium_only_is_medium(self, agent):
        findings = [{"severity": "medium"}, {"severity": "low"}]
        assert agent._compute_risk(findings) == "medium"

    def test_low_only_is_low(self, agent):
        findings = [{"severity": "low"}]
        assert agent._compute_risk(findings) == "low"


# ═══════════════════════════════════════════════════════════════════════════════
# Full 4-stage pipeline integration tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestPipelineIntegration:
    """Run the full 4-stage pipeline on real test case files (--no-llm mode)."""

    @pytest.fixture(autouse=True)
    def setup_pipeline(self):
        from src.pipeline.pipeline import CompilerOptimizationPipeline
        from src.llm.llm_client import LLMClient
        llm = LLMClient()
        llm._available = False  # offline mode — rules only
        self.pipeline = CompilerOptimizationPipeline(llm_client=llm)

    def _tc_path(self, name):
        return os.path.join(
            os.path.dirname(__file__), "..",
            "MicroBenchmarks", "Testcases", name,
        )

    def test_pipeline_has_security_report_field(self):
        tc = self._tc_path("TC01_uninit_arithmetic.cpp")
        if not os.path.isfile(tc):
            pytest.skip("TC01 not found")
        result = self.pipeline.run(tc)
        assert hasattr(result, "security_report"), \
            "PipelineResult missing security_report field"
        assert isinstance(result.security_report, dict)

    def test_pipeline_tc11_buffer_overflow(self):
        tc = self._tc_path("TC11_buffer_overflow_loop.cpp")
        if not os.path.isfile(tc):
            pytest.skip("TC11 not found")
        result = self.pipeline.run(tc)
        assert result.status in ("success", "partial", "rollback", "failed")
        # Security report must exist
        assert result.security_report.get("status") in ("PASS", "ROLLBACK")

    def test_pipeline_tc14_memory_leak(self):
        tc = self._tc_path("TC14_memory_leak.cpp")
        if not os.path.isfile(tc):
            pytest.skip("TC14 not found")
        result = self.pipeline.run(tc)
        assert result.status in ("success", "partial", "rollback", "failed")
        assert isinstance(result.security_report.get("all_vulnerabilities"), list)

    def test_pipeline_tc16_use_after_free(self):
        tc = self._tc_path("TC16_use_after_free.cpp")
        if not os.path.isfile(tc):
            pytest.skip("TC16 not found")
        result = self.pipeline.run(tc)
        assert result.status in ("success", "partial", "rollback", "failed")
        sec = result.security_report
        # TC16 contains use_after_free — security agent should detect it
        all_types = [v["type"] for v in sec.get("all_vulnerabilities", [])]
        assert "use_after_free" in all_types, \
            f"Expected use_after_free in {all_types}"

    def test_pipeline_tc19_heap_overflow(self):
        tc = self._tc_path("TC19_heap_overflow.cpp")
        if not os.path.isfile(tc):
            pytest.skip("TC19 not found")
        result = self.pipeline.run(tc)
        assert result.status in ("success", "partial", "rollback", "failed")
        assert "overall_risk" in result.security_report

    def test_pipeline_summary_includes_security_section(self):
        tc = self._tc_path("TC01_uninit_arithmetic.cpp")
        if not os.path.isfile(tc):
            pytest.skip("TC01 not found")
        result = self.pipeline.run(tc)
        summary = result.summary()
        assert "[Security]" in summary, \
            "PipelineResult.summary() missing [Security] section"

    def test_pipeline_result_status_is_valid(self):
        tc = self._tc_path("TC01_uninit_arithmetic.cpp")
        if not os.path.isfile(tc):
            pytest.skip("TC01 not found")
        result = self.pipeline.run(tc)
        assert result.status in ("success", "partial", "rollback", "failed")
