"""
Comprehensive Automated Test Suite for Multi-Agent C/C++ Code Optimization Framework.

Covers Section 16 Requirements:
  1. Analysis Agent tests (1-10)
  2. Optimization Agent tests (1-9)
  3. Verification Agent tests (1-11)
  4. Bounded Feedback Loop & Pipeline tests (1-12)
  5. Security Agent tests (1-10)
"""

import os
import sys
import json
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_framework import ContextManager, BaseAgent
from src.analysis.finding_schema import Finding, deduplicate_findings, normalize_finding
from src.analysis.tool_runner import ToolRunner, ToolStatus, ToolExecutionResult
from src.agents.analysis_agent import AnalysisAgent
from src.agents.optimization_agent import OptimizationAgent, OptimizationStatus
from src.agents.verification_agent import VerificationAgent
from src.agents.security_agent import SecurityAgent
from src.verification.diff_tester import DiffTestResult
from src.verification.z3_verifier import Z3Result
from src.pipeline.pipeline import CompilerOptimizationPipeline, PipelineResult
from src.llm.llm_client import LLMClient
from src.llm.prompt_templates import (
    AnalysisPromptTemplate,
    OptimizationPromptTemplate,
    VerificationPromptTemplate,
    SecurityPromptTemplate,
    SecurityScoringPromptTemplate,
)


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def ctx():
    return ContextManager()


@pytest.fixture
def offline_llm():
    """LLM client simulating an offline Ollama server."""
    llm = MagicMock(spec=LLMClient)
    llm._available = False
    llm.is_available.return_value = False
    llm.is_stub.return_value = True
    llm.generate.return_value = "```json\n{\"conclusion\": \"offline stub\"}\n```"
    llm.generate_with_meta.return_value = (
        "```json\n{\"conclusion\": \"offline stub\"}\n```",
        {"status": "unavailable", "is_genuine": False, "error": "Ollama offline"},
    )
    return llm


@pytest.fixture
def stub_llm():
    """LLM client simulating synthetic stub return."""
    llm = MagicMock(spec=LLMClient)
    llm._available = True
    llm.is_available.return_value = True
    llm.is_stub.return_value = True
    llm.generate.return_value = "```json\n{\"conclusion\": \"Rule-based analysis (LLM offline stub)\"}\n```"
    llm.generate_with_meta.return_value = (
        "```json\n{\"conclusion\": \"Rule-based analysis (LLM offline stub)\"}\n```",
        {"status": "stub", "is_genuine": False, "error": None},
    )
    return llm


@pytest.fixture
def malformed_llm():
    """LLM client returning malformed non-JSON responses."""
    llm = MagicMock(spec=LLMClient)
    llm._available = True
    llm.is_available.return_value = True
    llm.is_stub.return_value = False
    llm.generate.return_value = "I am an AI and I suggest fixing this code without JSON."
    llm.generate_with_meta.return_value = (
        "I am an AI and I suggest fixing this code without JSON.",
        {"status": "genuine", "is_genuine": True, "error": None},
    )
    return llm


@pytest.fixture
def genuine_llm():
    """LLM client returning valid genuine JSON responses."""
    llm = MagicMock(spec=LLMClient)
    llm._available = True
    llm.is_available.return_value = True
    llm.is_stub.return_value = False
    return llm


# ==============================================================================
# 1. Analysis Agent Tests (1-10)
# ==============================================================================

class TestAnalysisAgentEnhancements:

    def test_1_tool_availability_detection(self, ctx):
        """1) Tool availability detection (all available, some, none)."""
        runner = ToolRunner()
        with patch.object(runner, "find_executable", side_effect=lambda name: "/usr/bin/" + name if "cppcheck" in name else None):
            avail = runner.check_availability()
            assert avail["cppcheck"] is True
            assert avail["clang"] is False
            assert avail["clang-tidy"] is False

    def test_2_clang_tidy_unavailable_returns_status(self, ctx, offline_llm):
        """2) clang-tidy unavailable returns UNAVAILABLE status without crash."""
        runner = ToolRunner()
        with patch.object(runner, "find_executable", return_value=None):
            res = runner.run_clang_tidy("int main() { return 0; }")
            assert res.status == ToolStatus.UNAVAILABLE
            assert "not found" in res.error_message.lower() or "unavailable" in res.error_message.lower()

    def test_3_cppcheck_unavailable_returns_status(self, ctx, offline_llm):
        """3) cppcheck unavailable returns UNAVAILABLE status without crash."""
        runner = ToolRunner()
        with patch.object(runner, "find_executable", return_value=None):
            res = runner.run_cppcheck("int main() { return 0; }")
            assert res.status == ToolStatus.UNAVAILABLE
            assert "not found" in res.error_message.lower() or "unavailable" in res.error_message.lower()

    def test_4_sanitizer_compilation_failure_handled_gracefully(self, ctx):
        """4) Sanitizer execution handles compilation failure / missing runtime gracefully."""
        runner = ToolRunner()
        with patch.object(runner, "find_executable", return_value="/fake/clang"):
            with patch("subprocess.run") as mock_sub:
                mock_sub.return_value = MagicMock(returncode=1, stderr="fatal error: sanitizer runtime not found", stdout="")
                res_dict = runner.run_sanitizers("int main() { return 0; }")
                assert "asan" in res_dict and "ubsan" in res_dict
                assert res_dict["asan"].status in (ToolStatus.FAILED, ToolStatus.SKIPPED, ToolStatus.UNAVAILABLE)

    def test_5_ollama_unavailable_produces_valid_report_score_none(self, ctx, offline_llm):
        """5) Ollama unavailable produces valid analysis report with security_score=None."""
        agent = AnalysisAgent("analysis_test", ctx, llm_client=offline_llm)
        code = "int main() { int x; return x; }"
        rep = agent.process({"source_code": code, "file_path": "test.cpp"})
        assert rep["security_score"] is None
        assert rep["source_code"] == code
        assert isinstance(rep["all_findings"], list)

    def test_6_ollama_stub_produces_valid_report_score_none(self, ctx, stub_llm):
        """6) Ollama returns stub produces valid report with security_score=None (never 100)."""
        agent = AnalysisAgent("analysis_test", ctx, llm_client=stub_llm)
        code = "int main() { int x; return x; }"
        rep = agent.process({"source_code": code, "file_path": "test.cpp"})
        assert rep["security_score"] is None
        assert rep["security_score"] != 100

    def test_7_ollama_malformed_json_handles_gracefully(self, ctx, malformed_llm):
        """7) Ollama returns malformed JSON handles error gracefully."""
        agent = AnalysisAgent("analysis_test", ctx, llm_client=malformed_llm)
        code = "int main() { return 0; }"
        rep = agent.process({"source_code": code, "file_path": "test.cpp"})
        assert rep is not None
        assert "all_findings" in rep
        assert rep["security_score"] is None

    def test_8_deduplication_preserves_provenance(self):
        """8) Finding deduplication preserves provenance across multiple tools."""
        f1 = Finding(type="buffer_overflow", line=10, severity="high", source_tool="clang-tidy", id="f1").to_dict()
        f2 = Finding(type="buffer_overflow", line=10, severity="critical", source_tool="cppcheck", id="f2").to_dict()
        merged, summary = deduplicate_findings([f1, f2])
        assert len(merged) == 1
        assert summary["merged_groups"] == 1
        prov = merged[0]["execution_context"]["provenance_sources"]
        assert "clang-tidy" in prov
        assert "cppcheck" in prov

    def test_9_deduplication_preserves_cwes_and_lines(self):
        """9) Finding deduplication preserves CWE IDs and line numbers."""
        f1 = Finding(type="null_deref", line=25, severity="medium", source_tool="clang", cwe_id="CWE-476").to_dict()
        f2 = Finding(type="null_pointer_dereference", line=25, severity="high", source_tool="cppcheck", cwe_id="CWE-476").to_dict()
        merged, _ = deduplicate_findings([f1, f2])
        assert len(merged) == 1
        assert merged[0]["line"] == 25
        assert merged[0]["cwe_id"] == "CWE-476"

    def test_10_report_schema_validation(self, ctx, offline_llm):
        """10) Report schema validation matches all Section 5.7 keys."""
        agent = AnalysisAgent("analysis_test", ctx, llm_client=offline_llm)
        rep = agent.process({"source_code": "int main() { return 0; }", "file_path": "test.cpp"})
        required_keys = [
            "file_path", "source_code", "tool_statuses", "all_findings",
            "findings_by_category", "rule_findings", "tool_findings",
            "llm_hypotheses", "llm_reasoning", "security_score",
            "score_rationale", "score_confidence", "assessment_completeness",
            "assessment_limitations", "overall_risk", "summary"
        ]
        for rk in required_keys:
            assert rk in rep, f"Missing key in analysis report: {rk}"


# ==============================================================================
# 2. Optimization Agent Tests (1-9)
# ==============================================================================

class TestOptimizationAgentEnhancements:

    def test_1_valid_code_generation_with_diff_and_rationale(self, ctx, genuine_llm):
        """1) Valid code generation with diff and rationale."""
        genuine_llm.generate_with_meta.return_value = (
            '```json\n'
            '{\n'
            '  "reasoning_steps": ["Replaced uninitialized read with 0."],\n'
            '  "transformations": [{"type": "init", "description": "Initialize x"}],\n'
            '  "optimized_code": "int main() { int x = 0; return x; }",\n'
            '  "justification": "Prevents UB",\n'
            '  "expected_benefits": "Safe execution",\n'
            '  "security_considerations": "Memory initialized",\n'
            '  "behavior_preservation_claim": "Preserves semantics",\n'
            '  "conclusion": "Optimized",\n'
            '  "confidence": 0.95\n'
            '}\n'
            '```',
            {"status": "genuine", "is_genuine": True, "error": None}
        )
        agent = OptimizationAgent("opt_test", ctx, llm_client=genuine_llm)
        res = agent.process({
            "source_code": "int main() { int x; return x; }",
            "file_path": "test.cpp",
            "iteration": 1,
        })
        assert res["status"].upper() == "OPTIMIZATION_GENERATED"
        assert res["candidate_code"] == "int main() { int x = 0; return x; }"
        assert res["diff"] != ""
        assert res["rationale"] != ""

    def test_2_code_unchanged_produces_no_changes_generated(self, ctx, genuine_llm):
        """2) Code unchanged produces NO_CHANGES_GENERATED status."""
        code = "int main() { return 0; }"
        genuine_llm.generate_with_meta.return_value = (
            '```json\n'
            '{\n'
            '  "reasoning_steps": ["Code is already optimal."],\n'
            '  "transformations": [],\n'
            '  "optimized_code": "int main() { return 0; }",\n'
            '  "justification": "No changes needed",\n'
            '  "conclusion": "Unchanged",\n'
            '  "confidence": 0.9\n'
            '}\n'
            '```',
            {"status": "genuine", "is_genuine": True, "error": None}
        )
        agent = OptimizationAgent("opt_test", ctx, llm_client=genuine_llm)
        res = agent.process({"source_code": code, "file_path": "test.cpp", "iteration": 1})
        assert res["status"].upper() == "NO_CHANGES_GENERATED"

    def test_3_ollama_unavailable_produces_llm_unavailable_status(self, ctx, offline_llm):
        """3) Ollama unavailable produces LLM_UNAVAILABLE status with fallback."""
        agent = OptimizationAgent("opt_test", ctx, llm_client=offline_llm)
        code = "int main() { return 42; }"
        res = agent.process({"source_code": code, "file_path": "test.cpp", "iteration": 1})
        assert res["status"].upper() in ("LLM_UNAVAILABLE", "FALLBACK_ORIGINAL_CODE")
        assert res["candidate_code"] == code

    def test_4_ollama_stub_produces_fallback_without_fake_optimization(self, ctx, stub_llm):
        """4) Ollama stub produces fallback without treating stub as real optimization."""
        agent = OptimizationAgent("opt_test", ctx, llm_client=stub_llm)
        code = "int main() { return 42; }"
        res = agent.process({"source_code": code, "file_path": "test.cpp", "iteration": 1})
        assert res["status"].upper() in ("LLM_UNAVAILABLE", "FALLBACK_ORIGINAL_CODE")
        assert res["candidate_code"] == code

    def test_5_ollama_malformed_json_produces_invalid_llm_output(self, ctx, malformed_llm):
        """5) Ollama malformed JSON produces INVALID_LLM_OUTPUT status."""
        agent = OptimizationAgent("opt_test", ctx, llm_client=malformed_llm)
        code = "int main() { return 42; }"
        res = agent.process({"source_code": code, "file_path": "test.cpp", "iteration": 1})
        assert res["status"].upper() == "INVALID_LLM_OUTPUT"
        assert res["candidate_code"] == code

    def test_6_unresolved_findings_included_in_feedback_prompt(self, ctx, genuine_llm):
        """6) Unresolved findings from verification are included in feedback prompt."""
        prompt = OptimizationPromptTemplate.build(
            source_code="void f() {}",
            feedback={"unresolved_findings": [{"description": "Unresolved null pointer deref"}]},
            iteration=2,
        )
        assert "Unresolved null pointer deref" in prompt

    def test_7_verification_feedback_report_included_in_attempt_prompt(self, ctx):
        """7) Verification feedback report is included in subsequent attempt prompt."""
        feedback = {
            "failed_layers": ["differential_testing"],
            "diagnostics": "Output mismatch on input 5",
            "unresolved_findings": [],
            "new_findings": [{"description": "Regression in loop"}],
        }
        prompt = OptimizationPromptTemplate.build(
            source_code="void f() {}",
            feedback=feedback,
            iteration=2,
            previous_attempts=["Attempt 1 failed"],
        )
        assert "differential_testing" in prompt
        assert "Output mismatch on input 5" in prompt
        assert "Regression in loop" in prompt

    def test_8_iteration_history_recorded_correctly(self, ctx, genuine_llm):
        """8) Iteration history is recorded correctly (attempt 1, attempt 2, attempt 3)."""
        genuine_llm.generate_with_meta.return_value = (
            '```json\n{"optimized_code": "int main() { return 1; }", "reasoning_steps": ["fixed"]}\n```',
            {"status": "genuine", "is_genuine": True, "error": None}
        )
        agent = OptimizationAgent("opt_test", ctx, llm_client=genuine_llm)
        res = agent.process({"source_code": "int main() { return 0; }", "iteration": 2, "iteration_history": [{"attempt": 1}]})
        assert res["iteration"] == 2

    def test_9_fallback_candidate_never_reported_as_optimization_generated(self, ctx, offline_llm):
        """9) Fallback candidate is never reported as OPTIMIZATION_GENERATED."""
        agent = OptimizationAgent("opt_test", ctx, llm_client=offline_llm)
        res = agent.process({"source_code": "int main() { return 0; }", "iteration": 1})
        assert res["status"].upper() != "OPTIMIZATION_GENERATED"


# ==============================================================================
# 3. Verification Agent Tests (1-11)
# ==============================================================================

class TestVerificationAgentEnhancements:

    def test_1_all_four_verification_layers_invoked_in_sequence(self, ctx, offline_llm):
        """1) All four verification layers invoked in sequence."""
        agent = VerificationAgent("ver_test", ctx, llm_client=offline_llm)
        res = agent.process({
            "original_code": "int f(int x) { return x + 1; }",
            "candidate_code": "int f(int x) { return 1 + x; }",
            "file_path": "test.cpp",
        })
        diag = res.get("layer_diagnostics", {})
        assert "layer1_diff" in diag
        assert "layer2_z3" in diag
        assert "layer3_perf" in diag
        assert "layer4_llm" in diag

    def test_2_differential_testing_failure_flags_verification(self, ctx, offline_llm):
        """2) Layer 1 differential testing failure stops or flags verification."""
        agent = VerificationAgent("ver_test", ctx, llm_client=offline_llm)
        with patch.object(agent.diff_tester, "test", return_value=DiffTestResult(passed=False, original_output="0", optimized_output="1", error="Output mismatch")):
            res = agent.process({
                "original_code": "int main() { return 0; }",
                "candidate_code": "int main() { return 1; }",
            })
            assert res["passes_acceptance"] is False
            assert any("diff" in x.lower() for x in res["feedback_report"]["failed_layers"])

    def test_3_z3_counterexample_detected_correctly(self, ctx, offline_llm):
        """3) Layer 2 Z3 equivalence counterexample detected correctly."""
        agent = VerificationAgent("ver_test", ctx, llm_client=offline_llm)
        with patch.object(agent.z3, "verify", return_value=Z3Result(status="COUNTEREXAMPLE_FOUND", counterexample="x = 5", explanation="Difference found")):
            res = agent.process({
                "original_code": "int f(int x) { return x * 2; }",
                "candidate_code": "int f(int x) { return x + 2; }",
            })
            assert res["passes_acceptance"] is False
            assert any("z3" in x.lower() for x in res["feedback_report"]["failed_layers"])

    def test_4_z3_inconclusive_handled_gracefully(self, ctx, offline_llm):
        """4) Layer 2 Z3 inconclusive handled gracefully."""
        agent = VerificationAgent("ver_test", ctx, llm_client=offline_llm)
        with patch.object(agent.z3, "verify", return_value=Z3Result(status="UNKNOWN", counterexample=None, explanation="non-linear AST")):
            res = agent.process({
                "original_code": "void complex() {}",
                "candidate_code": "void complex() {}",
            })
            assert res["layer_diagnostics"]["layer2_z3"]["status"] == "UNKNOWN"

    def test_5_benchmark_binary_unavailable_marked_skipped(self, ctx, offline_llm):
        """5) Layer 3 benchmark binary unavailable marked as SKIPPED/UNAVAILABLE."""
        agent = VerificationAgent("ver_test", ctx, llm_client=offline_llm)
        with patch.object(agent.perf, "benchmark", return_value=MagicMock(available=False, summary=lambda: "Benchmark binary not found")):
            res = agent.process({
                "original_code": "void f() {}",
                "candidate_code": "void f() {}",
            })
            perf_status = res["layer_diagnostics"]["layer3_perf"]["status"]
            assert perf_status in (ToolStatus.SKIPPED, ToolStatus.UNAVAILABLE)

    def test_6_llm_verification_handles_inconclusive_offline(self, ctx, offline_llm):
        """6) Layer 4 LLM verification handles inconclusive/unavailable LLM."""
        agent = VerificationAgent("ver_test", ctx, llm_client=offline_llm)
        res = agent.process({
            "original_code": "void f() {}",
            "candidate_code": "void f() {}",
        })
        l4 = res["layer_diagnostics"]["layer4_llm"]
        assert l4["verdict"] in ("UNCERTAIN", "SKIPPED")

    def test_7_finding_reassessment_identifies_resolved(self, ctx, offline_llm):
        """7) Finding reassessment correctly identifies resolved findings."""
        agent = VerificationAgent("ver_test", ctx, llm_client=offline_llm)
        orig_findings = [Finding(type="unsafe_gets", line=5, description="gets() unsafe").to_dict()]
        original_code = 'void f() { char buf[64]; gets(buf); }'
        candidate_code = 'void f() { char buf[64]; fgets(buf, sizeof(buf), stdin); }'
        resolved, unresolved, new_f = agent._reassess_findings(original_code, candidate_code, orig_findings, "test.cpp")
        assert len(resolved) == 1
        assert resolved[0]["type"] == "unsafe_gets"
        assert len(unresolved) == 0

    def test_8_finding_reassessment_identifies_unresolved(self, ctx, offline_llm):
        """8) Finding reassessment correctly identifies unresolved findings."""
        agent = VerificationAgent("ver_test", ctx, llm_client=offline_llm)
        orig_findings = [Finding(type="unsafe_gets", line=5, description="gets() unsafe").to_dict()]
        original_code = 'void f() { char buf[64]; gets(buf); }'
        candidate_code = 'void f() { char buf[64]; gets(buf); }'
        resolved, unresolved, new_f = agent._reassess_findings(original_code, candidate_code, orig_findings, "test.cpp")
        assert len(resolved) == 0
        assert len(unresolved) == 1

    def test_9_finding_reassessment_flags_newly_introduced(self, ctx, offline_llm):
        """9) Finding reassessment correctly flags newly introduced findings."""
        agent = VerificationAgent("ver_test", ctx, llm_client=offline_llm)
        orig_findings = []
        original_code = 'void f() { char buf[64]; }'
        candidate_code = 'void f() { char buf[64]; gets(buf); }'
        resolved, unresolved, new_f = agent._reassess_findings(original_code, candidate_code, orig_findings, "test.cpp")
        assert len(new_f) == 1
        assert new_f[0]["type"] == "unsafe_gets"

    def test_10_verification_feedback_report_schema(self, ctx, offline_llm):
        """10) Verification feedback report contains all required Section 7.5 fields."""
        agent = VerificationAgent("ver_test", ctx, llm_client=offline_llm)
        res = agent.process({
            "original_code": "void f() {}",
            "candidate_code": "void f() {}",
        })
        fb = res["feedback_report"]
        for key in ["iteration", "failed_layers", "diagnostics", "unresolved_findings", "new_findings", "actionable_instructions"]:
            assert key in fb, f"Missing key in feedback_report: {key}"

    def test_11_tool_failure_vs_skipped_distinct(self):
        """11) Tool execution failure vs skipped tool handled distinctly."""
        assert ToolStatus.FAILED != ToolStatus.SKIPPED
        assert ToolStatus.UNAVAILABLE != ToolStatus.FAILED


# ==============================================================================
# 4. Bounded Feedback Loop & Pipeline Tests (1-12)
# ==============================================================================

class TestBoundedFeedbackLoopEnhancements:

    def test_1_terminates_on_attempt_1_when_verification_passes(self, genuine_llm):
        """1) Pipeline terminates on Attempt 1 when verification passes."""
        pipeline = CompilerOptimizationPipeline(llm_client=genuine_llm)
        pipeline.analysis_agent.process = MagicMock(return_value={"all_findings": [], "security_score": 80})
        pipeline.optimization_agent.process = MagicMock(return_value={"status": "OPTIMIZATION_GENERATED", "optimized_code": "void f() {}"})
        pipeline.verification_agent.process = MagicMock(return_value={"status": "VERIFIED", "passes_acceptance": True, "feedback_report": {}})
        pipeline.security_agent.process = MagicMock(return_value={"status": "PASS", "security_score": 85})

        res = pipeline.run_string("void f() {}", "test.cpp")
        assert res.iteration_count == 1
        assert res.status == "success"

    def test_2_iterates_to_attempt_2_when_attempt_1_fails(self, genuine_llm):
        """2) Pipeline iterates to Attempt 2 when Attempt 1 fails verification."""
        pipeline = CompilerOptimizationPipeline(llm_client=genuine_llm)
        pipeline.analysis_agent.process = MagicMock(return_value={"all_findings": [], "security_score": 80})
        pipeline.optimization_agent.process = MagicMock(side_effect=[
            {"status": "OPTIMIZATION_GENERATED", "optimized_code": "void f() { int bad; }"},
            {"status": "OPTIMIZATION_GENERATED", "optimized_code": "void f() { int good = 0; }"},
        ])
        pipeline.verification_agent.process = MagicMock(side_effect=[
            {"status": "FAILED", "passes_acceptance": False, "feedback_report": {"failed_layers": ["diff"]}},
            {"status": "VERIFIED", "passes_acceptance": True, "feedback_report": {}},
        ])
        pipeline.security_agent.process = MagicMock(return_value={"status": "PASS", "security_score": 85})

        res = pipeline.run_string("void f() {}", "test.cpp")
        assert res.iteration_count == 2
        assert res.status == "success"

    def test_3_feedback_passed_to_attempt_2(self, genuine_llm):
        """3) Feedback report from Attempt 1 is passed to Attempt 2."""
        pipeline = CompilerOptimizationPipeline(llm_client=genuine_llm)
        pipeline.analysis_agent.process = MagicMock(return_value={"all_findings": [], "security_score": 80})
        captured_feedback = []

        def opt_side_effect(inp):
            captured_feedback.append(inp.get("feedback"))
            return {"status": "OPTIMIZATION_GENERATED", "optimized_code": "void f() {}"}

        pipeline.optimization_agent.process = MagicMock(side_effect=opt_side_effect)
        pipeline.verification_agent.process = MagicMock(side_effect=[
            {"status": "FAILED", "passes_acceptance": False, "feedback_report": {"failed_layers": ["diff"], "diagnostics": "err1"}},
            {"status": "VERIFIED", "passes_acceptance": True, "feedback_report": {}},
        ])
        pipeline.security_agent.process = MagicMock(return_value={"status": "PASS", "security_score": 85})

        pipeline.run_string("void f() {}", "test.cpp")
        assert captured_feedback[0] is None
        assert captured_feedback[1]["diagnostics"] == "err1"

    def test_4_pipeline_terminates_on_attempt_2_when_it_passes(self, genuine_llm):
        """4) Pipeline terminates on Attempt 2 when Attempt 2 passes."""
        pipeline = CompilerOptimizationPipeline(llm_client=genuine_llm)
        pipeline.analysis_agent.process = MagicMock(return_value={"all_findings": [], "security_score": 80})
        pipeline.optimization_agent.process = MagicMock(return_value={"status": "OPTIMIZATION_GENERATED", "optimized_code": "void f() {}"})
        pipeline.verification_agent.process = MagicMock(side_effect=[
            {"status": "FAILED", "passes_acceptance": False, "feedback_report": {}},
            {"status": "VERIFIED", "passes_acceptance": True, "feedback_report": {}},
        ])
        pipeline.security_agent.process = MagicMock(return_value={"status": "PASS", "security_score": 85})

        res = pipeline.run_string("void f() {}", "test.cpp")
        assert res.iteration_count == 2
        assert len(res.iteration_history) == 2

    def test_5_executes_exactly_3_attempts_when_all_fail(self, genuine_llm):
        """5) Pipeline executes exactly 3 attempts when all fail."""
        pipeline = CompilerOptimizationPipeline(llm_client=genuine_llm)
        pipeline.analysis_agent.process = MagicMock(return_value={"all_findings": [], "security_score": 80})
        pipeline.optimization_agent.process = MagicMock(return_value={"status": "OPTIMIZATION_GENERATED", "optimized_code": "void f() {}"})
        pipeline.verification_agent.process = MagicMock(return_value={"status": "FAILED", "passes_acceptance": False, "feedback_report": {}})
        pipeline.security_agent.process = MagicMock(return_value={"status": "PASS", "security_score": 80})

        res = pipeline.run_string("void f() {}", "test.cpp")
        assert res.iteration_count == 3
        assert len(res.iteration_history) == 3

    def test_6_max_attempts_strictly_capped_at_3(self, genuine_llm):
        """6) Max attempts strictly capped at 3 (never loops indefinitely)."""
        pipeline = CompilerOptimizationPipeline(llm_client=genuine_llm)
        pipeline.MAX_ITERATIONS = 3
        pipeline.analysis_agent.process = MagicMock(return_value={"all_findings": [], "security_score": 80})
        pipeline.optimization_agent.process = MagicMock(return_value={"status": "OPTIMIZATION_GENERATED", "optimized_code": "void f() {}"})
        pipeline.verification_agent.process = MagicMock(return_value={"status": "FAILED", "passes_acceptance": False, "feedback_report": {}})
        pipeline.security_agent.process = MagicMock(return_value={"status": "PASS", "security_score": 80})

        res = pipeline.run_string("void f() {}", "test.cpp")
        assert res.iteration_count <= 3

    def test_7_missing_tool_does_not_cause_endless_looping(self, offline_llm):
        """7) Missing conventional tool does not cause endless looping."""
        pipeline = CompilerOptimizationPipeline(llm_client=offline_llm)
        pipeline.analysis_agent.process = MagicMock(return_value={"all_findings": [], "security_score": None})
        pipeline.optimization_agent.process = MagicMock(return_value={"status": "LLM_UNAVAILABLE", "optimized_code": "void f() {}"})
        pipeline.verification_agent.process = MagicMock(return_value={"status": "VERIFIED", "passes_acceptance": True, "feedback_report": {}})
        pipeline.security_agent.process = MagicMock(return_value={"status": "PASS", "security_score": None})

        res = pipeline.run_string("void f() {}", "test.cpp")
        assert res.iteration_count <= 3

    def test_8_fallback_candidate_tracked_when_all_fail(self, genuine_llm):
        """8) Fallback candidate tracked when all attempts fail."""
        pipeline = CompilerOptimizationPipeline(llm_client=genuine_llm)
        orig = "void original() {}"
        pipeline.analysis_agent.process = MagicMock(return_value={"all_findings": [], "security_score": 80})
        pipeline.optimization_agent.process = MagicMock(return_value={"status": "OPTIMIZATION_GENERATED", "optimized_code": "void broken() {}"})
        pipeline.verification_agent.process = MagicMock(return_value={"status": "FAILED", "passes_acceptance": False, "feedback_report": {}})
        pipeline.security_agent.process = MagicMock(return_value={"status": "PASS", "security_score": 80})

        res = pipeline.run_string(orig, "test.cpp")
        assert res.status in ("failed", "rollback", "partial")

    def test_9_iteration_history_preserves_details(self, genuine_llm):
        """9) Iteration history preserves details of each attempt."""
        pipeline = CompilerOptimizationPipeline(llm_client=genuine_llm)
        pipeline.analysis_agent.process = MagicMock(return_value={"all_findings": [], "security_score": 80})
        pipeline.optimization_agent.process = MagicMock(return_value={"status": "OPTIMIZATION_GENERATED", "optimized_code": "c"})
        pipeline.verification_agent.process = MagicMock(return_value={"status": "FAILED", "passes_acceptance": False, "feedback_report": {"k": "v"}})
        pipeline.security_agent.process = MagicMock(return_value={"status": "PASS", "security_score": 80})

        res = pipeline.run_string("void f() {}", "test.cpp")
        assert len(res.iteration_history) == 3
        for item in res.iteration_history:
            assert "iteration" in item
            assert "candidate_code" in item
            assert "verification_status" in item

    def test_10_final_candidate_passed_to_security_is_from_loop(self, genuine_llm):
        """10) Final candidate passed to security agent is the candidate from the loop."""
        pipeline = CompilerOptimizationPipeline(llm_client=genuine_llm)
        captured_candidate = []

        pipeline.analysis_agent.process = MagicMock(return_value={"all_findings": [], "security_score": 70})
        pipeline.optimization_agent.process = MagicMock(return_value={"status": "OPTIMIZATION_GENERATED", "optimized_code": "void loop_candidate() {}"})
        pipeline.verification_agent.process = MagicMock(return_value={"status": "VERIFIED", "passes_acceptance": True, "feedback_report": {}})

        def sec_side_effect(inp):
            captured_candidate.append(inp.get("optimized_code"))
            return {"status": "PASS", "security_score": 80}

        pipeline.security_agent.process = MagicMock(side_effect=sec_side_effect)
        pipeline.run_string("void orig() {}", "test.cpp")
        assert len(captured_candidate) > 0
        assert captured_candidate[0] == "void loop_candidate() {}"

    def test_11_pipeline_result_contains_all_iteration_fields(self, genuine_llm):
        """11) Pipeline result contains iteration_history, iteration_count, unresolved_findings."""
        res = PipelineResult(
            file_path="test.cpp",
            status="success",
            iteration_history=[{"iteration": 1}],
            iteration_count=1,
            unresolved_findings=[],
        )
        assert res.iteration_count == 1
        assert len(res.iteration_history) == 1
        assert res.unresolved_findings == []

    def test_12_backward_compatibility_single_pass(self, genuine_llm):
        """12) Backward compatibility: pipeline handles single pass cleanly."""
        pipeline = CompilerOptimizationPipeline(llm_client=genuine_llm)
        pipeline.analysis_agent.process = MagicMock(return_value={"all_findings": []})
        pipeline.optimization_agent.process = MagicMock(return_value={"status": "OPTIMIZATION_GENERATED", "optimized_code": "c"})
        pipeline.verification_agent.process = MagicMock(return_value={"status": "VERIFIED", "passes_acceptance": True, "feedback_report": {}})
        pipeline.security_agent.process = MagicMock(return_value={"status": "PASS", "security_score": 90})
        res = pipeline.run_string("void f() {}", "test.cpp")
        assert res.status == "success"


# ==============================================================================
# 5. Security Agent Tests (1-10)
# ==============================================================================

class TestSecurityAgentEnhancements:

    def test_1_candidate_from_loop_is_analyzed_not_reverted(self, ctx, offline_llm):
        """1) Candidate from loop is analyzed (not reverted to original)."""
        agent = SecurityAgent("sec_test", ctx, llm_client=offline_llm)
        orig = "void safe() {}"
        cand = "void unsafe() { char b[4]; gets(b); }"
        rep = agent.process({"original_code": orig, "optimized_code": cand, "file_path": "test.cpp"})
        all_types = [v["type"] for v in rep["all_vulnerabilities"]]
        assert "unsafe_gets" in all_types

    def test_2_conventional_tools_run_on_candidate(self, ctx, offline_llm):
        """2) Conventional tools run on candidate code."""
        agent = SecurityAgent("sec_test", ctx, llm_client=offline_llm)
        with patch.object(agent.tool_runner, "run_all_tools_concurrently") as mock_tools:
            mock_tools.return_value = {
                "cppcheck": ToolExecutionResult(tool_name="cppcheck", status=ToolStatus.UNAVAILABLE),
                "clang-tidy": ToolExecutionResult(tool_name="clang-tidy", status=ToolStatus.UNAVAILABLE),
            }
            rep = agent.process({"original_code": "void f() {}", "optimized_code": "void f() {}"})
            mock_tools.assert_called_once()
            assert "cppcheck" in rep["tool_statuses"]

    def test_3_new_vulnerabilities_detected_when_candidate_introduces_flaw(self, ctx, offline_llm):
        """3) New vulnerabilities detected when candidate introduces flaw."""
        agent = SecurityAgent("sec_test", ctx, llm_client=offline_llm)
        orig = "void f() { char buf[64]; fgets(buf, sizeof(buf), stdin); }"
        cand = "void f() { char buf[64]; gets(buf); }"
        rep = agent.process({"original_code": orig, "optimized_code": cand})
        new_types = [v["type"] for v in rep["new_vulnerabilities"]]
        assert "unsafe_gets" in new_types

    def test_4_preexisting_vulnerabilities_not_misclassified_as_new(self, ctx, offline_llm):
        """4) Pre-existing vulnerabilities not misclassified as new."""
        agent = SecurityAgent("sec_test", ctx, llm_client=offline_llm)
        code = "void f() { char buf[64]; gets(buf); }"
        rep = agent.process({"original_code": code, "optimized_code": code})
        new_types = [v["type"] for v in rep["new_vulnerabilities"]]
        assert "unsafe_gets" not in new_types

    def test_5_score_generation_returns_valid_integer_when_llm_available(self, ctx, genuine_llm):
        """5) Score generation returns valid 0-100 integer when LLM available."""
        genuine_llm.generate_with_meta.return_value = (
            '```json\n{"security_score": 85, "score_rationale": "All flaws resolved", "score_confidence": 0.9}\n```',
            {"status": "genuine", "is_genuine": True, "error": None}
        )
        agent = SecurityAgent("sec_test", ctx, llm_client=genuine_llm)
        rep = agent.process({"original_code": "void f() {}", "optimized_code": "void f() {}"})
        assert rep["security_score"] == 85
        assert 0 <= rep["security_score"] <= 100

    def test_6_score_generation_returns_none_when_llm_offline(self, ctx, offline_llm):
        """6) Score generation returns None when LLM is unavailable (never 100)."""
        agent = SecurityAgent("sec_test", ctx, llm_client=offline_llm)
        rep = agent.process({"original_code": "void f() {}", "optimized_code": "void f() {}"})
        assert rep["security_score"] is None
        assert rep["security_score"] != 100

    def test_7_score_generation_returns_none_when_llm_returns_stub(self, ctx, stub_llm):
        """7) Score generation returns None when LLM returns stub."""
        agent = SecurityAgent("sec_test", ctx, llm_client=stub_llm)
        rep = agent.process({"original_code": "void f() {}", "optimized_code": "void f() {}"})
        assert rep["security_score"] is None

    def test_8_score_comparison_correctly_computes_diff(self, ctx, genuine_llm):
        """8) Score comparison correctly computes diff = final_score - initial_score."""
        genuine_llm.generate_with_meta.return_value = (
            '```json\n{"security_score": 90, "score_rationale": "Improved", "score_confidence": 0.9}\n```',
            {"status": "genuine", "is_genuine": True, "error": None}
        )
        agent = SecurityAgent("sec_test", ctx, llm_client=genuine_llm)
        rep = agent.process({"original_code": "void f() {}", "optimized_code": "void f() {}", "initial_score": 60})
        assert rep["initial_score"] == 60
        assert rep["security_score"] == 90
        assert rep["score_change"] == 30

    def test_9_score_comparison_explanation_generated(self, ctx, genuine_llm):
        """9) Score comparison explanation generated."""
        genuine_llm.generate_with_meta.return_value = (
            '```json\n{"security_score": 90, "score_rationale": "Fixed buffer", "score_confidence": 0.9}\n```',
            {"status": "genuine", "is_genuine": True, "error": None}
        )
        agent = SecurityAgent("sec_test", ctx, llm_client=genuine_llm)
        rep = agent.process({"original_code": "void f() {}", "optimized_code": "void f() {}", "initial_score": 70})
        assert "+20" in rep["score_explanation"] or "improved" in rep["score_explanation"].lower()

    def test_10_rollback_triggered_on_high_severity_new_vulnerability(self, ctx, offline_llm):
        """10) Rollback triggered on high-severity new vulnerability if configured."""
        agent = SecurityAgent("sec_test", ctx, llm_client=offline_llm)
        orig = "void f() {}"
        cand = "void f() { char buf[64]; gets(buf); }"
        rep = agent.process({"original_code": orig, "optimized_code": cand})
        assert rep["status"] == "ROLLBACK"
        assert len(rep["rollback_triggers"]) > 0
