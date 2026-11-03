"""
Comprehensive Regression Test Suite for Pipeline Remediation and Architectural Integrity.

Validates:
1. Genuine rollback: restores original source code and never returns rejected candidate as accepted.
2. Removal of false-success exception handling (security exceptions result in ERROR, never PASS).
3. Explicit --no-security configuration (marks security stage SKIPPED without crashing or false success).
4. Differential testing validates return codes, abnormal exits, timeouts, and multiple test inputs.
5. Performance benchmarker supports int main() with 0 arguments and int main(int argc, char* argv[]).
6. ToolRunner sanitizer execution: crashes/timeouts without diagnostic strings are FAILED/INCONCLUSIVE, never PASSED.
7. Security score validation: rejects booleans (True/False), fractional floats, and out-of-range values in both Analysis and Security agents.
8. OptimizationAgent preserves original source and rejects unvalidated regex-based automatic mutation.
9. VerificationAgent tri-state acceptance logic (PASS, FAIL, INCOMPLETE).
10. Language restriction to C and C++ (rejection of unsupported languages).
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from src.pipeline.pipeline import CompilerOptimizationPipeline, PipelineResult
from src.verification.diff_tester import DifferentialTester, DiffTestResult
from src.verification.perf_benchmarker import PerfBenchmarker, PerfResult
from src.verification.z3_verifier import Z3Verifier, Z3Result
from src.analysis.tool_runner import ToolRunner, ToolStatus, ToolExecutionResult
from src.agents.optimization_agent import OptimizationAgent, OptimizationStatus
from src.agents.verification_agent import VerificationAgent
from src.agents.security_agent import SecurityAgent
from src.agents.analysis_agent import AnalysisAgent
from agent_framework import ContextManager


# ── 1. Pipeline Status & Genuine Rollback ────────────────────────────────────

def test_pipeline_genuine_rollback_on_security_rejection():
    """When a candidate is rejected by security audit, original code is restored as selected code."""
    orig_code = "int main() { int x = 0; return x; }"
    bad_cand  = "int main() { char buf[4]; gets(buf); return 0; }"

    pipeline = CompilerOptimizationPipeline()

    # Mock Analysis
    pipeline.analysis_agent.process = MagicMock(return_value={
        "all_findings": [],
        "security_score": 90,
        "conclusion": "Initial code is clean.",
    })
    # Mock Optimization
    pipeline.optimization_agent.process = MagicMock(return_value={
        "optimized_code": bad_cand,
        "transformations": [{"type": "unsafe_change", "description": "added gets"}],
        "optimization_status": OptimizationStatus.OPTIMIZATION_GENERATED,
    })
    # Mock Verification: passes correctness
    pipeline.verification_agent.process = MagicMock(return_value={
        "status": "PASS",
        "passes_acceptance": True,
        "blocking_reasons": [],
        "unresolved_findings": [],
        "new_findings": [],
    })
    # Mock Security: triggers ROLLBACK due to introduced flaw
    pipeline.security_agent.process = MagicMock(return_value={
        "status": "ROLLBACK",
        "overall_risk": "CRITICAL",
        "security_score": 30,
        "new_vulnerabilities": [{"type": "unsafe_gets", "severity": "critical"}],
        "all_vulnerabilities": [{"type": "unsafe_gets", "severity": "critical"}],
        "summary": "Candidate introduced critical gets() vulnerability.",
    })

    res = pipeline.run_string(orig_code, label="test_rollback.cpp")

    assert res.status == "rollback"
    assert res.was_rolled_back is True
    assert res.selected_code == orig_code
    assert res.final_source_code == orig_code
    assert res.candidate_code == bad_cand
    assert "rejected" in res.rollback_reason.lower()


def test_security_exception_never_becomes_pass():
    """A caught exception in SecurityAgent must result in status ERROR, never PASS or success."""
    orig_code = "int main() { return 0; }"
    cand_code = "int main() { return 1 - 1; }"

    pipeline = CompilerOptimizationPipeline()

    pipeline.analysis_agent.process = MagicMock(return_value={"all_findings": [], "security_score": 95})
    pipeline.optimization_agent.process = MagicMock(return_value={
        "optimized_code": cand_code,
        "transformations": [],
        "optimization_status": OptimizationStatus.OPTIMIZATION_GENERATED,
    })
    pipeline.verification_agent.process = MagicMock(return_value={
        "status": "PASS",
        "passes_acceptance": True,
        "blocking_reasons": [],
    })
    # SecurityAgent raises an unexpected error
    pipeline.security_agent.process = MagicMock(side_effect=RuntimeError("Security scanner crashed"))

    res = pipeline.run_string(orig_code, label="test_sec_exc.cpp")

    assert res.security_report["status"] == "ERROR"
    assert res.status == "error"
    assert res.was_rolled_back is True
    assert res.selected_code == orig_code
    assert "crashed" in res.security_report["summary"]


def test_no_security_configuration_marks_skipped_truthfully():
    """When security audit is disabled (--no-security), Step 4 is SKIPPED without failing or false pass."""
    orig_code = "int main() { return 0; }"
    cand_code = "int main() { return 0 + 0; }"

    pipeline = CompilerOptimizationPipeline(enable_security=False)

    pipeline.analysis_agent.process = MagicMock(return_value={"all_findings": [], "security_score": 90})
    pipeline.optimization_agent.process = MagicMock(return_value={
        "optimized_code": cand_code,
        "transformations": [],
        "optimization_status": OptimizationStatus.OPTIMIZATION_GENERATED,
    })
    pipeline.verification_agent.process = MagicMock(return_value={
        "status": "PASS",
        "passes_acceptance": True,
        "blocking_reasons": [],
    })

    res = pipeline.run_string(orig_code, label="test_no_sec.cpp")

    assert res.security_report["status"] == "SKIPPED"
    assert res.security_report["audit_completeness"] == "skipped"
    assert res.final_security_score is None
    assert res.status == "success"
    assert res.selected_code == cand_code


def test_pipeline_failed_verification_restores_original_code():
    """When verification fails on attempts 1-3, candidate is not released as accepted."""
    orig_code = "int main() { return 0; }"
    cand_code = "int main() { return 42; }"

    pipeline = CompilerOptimizationPipeline()
    pipeline.analysis_agent.process = MagicMock(return_value={"all_findings": []})
    pipeline.optimization_agent.process = MagicMock(return_value={
        "optimized_code": cand_code,
        "transformations": [],
        "optimization_status": OptimizationStatus.OPTIMIZATION_GENERATED,
    })
    pipeline.verification_agent.process = MagicMock(return_value={
        "status": "FAIL",
        "passes_acceptance": False,
        "blocking_reasons": ["Differential test mismatch: return 42 != 0"],
    })
    pipeline.security_agent.process = MagicMock(return_value={"status": "PASS", "new_vulnerabilities": []})

    res = pipeline.run_string(orig_code, label="test_fail.cpp")

    assert res.status == "failed"
    assert res.was_rolled_back is True
    assert res.selected_code == orig_code


# ── 2. Differential Testing Checks ──────────────────────────────────────────

def test_diff_tester_rejects_abnormal_exits_even_with_equal_empty_output():
    """If both original and candidate terminate abnormally (e.g. exit code 1 or segfault), passed is False."""
    tester = DifferentialTester()
    tester._check_compiler = MagicMock(return_value=True)
    tester._compile = MagicMock(return_value=None)

    # Both return code 139 (SIGSEGV) with empty stdout
    tester._run = MagicMock(side_effect=[
        ("", "Segmentation fault (core dumped)", 139),  # original
        ("", "Segmentation fault (core dumped)", 139),  # candidate
    ])

    res = tester.test("int main() { return 0; }", "int main() { return 0; }")
    assert res.passed is False
    assert "abnormally" in res.error.lower()


def test_diff_tester_detects_return_code_mismatch():
    """Return code mismatch between original and candidate blocks differential acceptance."""
    tester = DifferentialTester()
    tester._check_compiler = MagicMock(return_value=True)
    tester._compile = MagicMock(return_value=None)

    tester._run = MagicMock(side_effect=[
        ("OK", "", 0),  # original exits 0
        ("OK", "", 1),  # candidate exits 1 with identical stdout
    ])

    res = tester.test("src1", "src2")
    assert res.passed is False
    assert "return code mismatch" in res.error.lower()


def test_diff_tester_handles_timeout():
    """A timeout in either execution marks differential test as failed."""
    tester = DifferentialTester()
    tester._check_compiler = MagicMock(return_value=True)
    tester._compile = MagicMock(return_value=None)

    tester._run = MagicMock(side_effect=[
        ("OK", "", 0),
        ("", "Execution timed out.", -1),
    ])

    res = tester.test("src1", "src2")
    assert res.passed is False
    assert "timed out" in res.error.lower()


def test_diff_tester_multiple_inputs():
    """Runs test inputs and detects failure on the specific input that diverges."""
    tester = DifferentialTester()
    tester._check_compiler = MagicMock(return_value=True)
    tester._compile = MagicMock(return_value=None)

    # Input 1 matches; Input 2 produces mismatch
    tester._run = MagicMock(side_effect=[
        ("out1", "", 0), ("out1", "", 0),
        ("out2", "", 0), ("out_different", "", 0),
    ])

    res = tester.test("src1", "src2", test_inputs=["10", "20"])
    assert res.passed is False
    assert len(res.test_case_results) == 2
    assert res.test_case_results[0]["passed"] is True
    assert res.test_case_results[1]["passed"] is False


# ── 3. Performance Benchmarking Tests ───────────────────────────────────────

def test_perf_benchmarker_timing_harness_supports_zero_arg_main():
    """Verify that _TIMING_HARNESS compiles with both int main() and int main(int, char**)."""
    bench = PerfBenchmarker()
    # Check that template SFINAE helper is present in timing harness
    from src.verification.perf_benchmarker import _TIMING_HARNESS
    assert "_perf_call_main" in _TIMING_HARNESS
    assert "decltype(f())" in _TIMING_HARNESS
    assert "decltype(f(argc, argv))" in _TIMING_HARNESS


# ── 4. Sanitizer Execution Status Tests ──────────────────────────────────────

def test_sanitizer_timeout_marked_inconclusive():
    """A sanitizer execution that times out must report INCONCLUSIVE, never PASSED."""
    tr = ToolRunner()
    tr.find_executable = MagicMock(return_value="clang++")

    with patch("subprocess.run") as mock_run:
        # 1. Compile succeeds
        compile_mock = MagicMock(returncode=0, stdout="", stderr="")
        # 2. Execution times out
        import subprocess
        mock_run.side_effect = [compile_mock, subprocess.TimeoutExpired(cmd=["bin"], timeout=10)]

        res = tr._build_and_run_sanitizer(
            compiler="clang++",
            sanitizer_flag="-fsanitize=address",
            sname="asan",
            source_code="int main() { while(1); return 0; }",
            file_path="loop.cpp",
            is_cpp=True,
            test_inputs=[""],
        )

        assert res.status == ToolStatus.INCONCLUSIVE
        assert "timed out" in res.error_message.lower()


def test_sanitizer_abnormal_exit_marked_failed():
    """A sanitizer target that crashes without diagnostic string must report FAILED, never PASSED."""
    tr = ToolRunner()
    tr.find_executable = MagicMock(return_value="clang++")

    with patch("subprocess.run") as mock_run:
        # 1. Compile succeeds
        compile_mock = MagicMock(returncode=0, stdout="", stderr="")
        # 2. Execution crashes with code 1
        exec_mock = MagicMock(returncode=1, stdout="", stderr="Fatal process failure")
        mock_run.side_effect = [compile_mock, exec_mock]

        res = tr._build_and_run_sanitizer(
            compiler="clang++",
            sanitizer_flag="-fsanitize=address",
            sname="asan",
            source_code="int main() { return 1; }",
            file_path="crash.cpp",
            is_cpp=True,
            test_inputs=[""],
        )

        assert res.status == ToolStatus.FAILED
        assert "abnormally" in res.error_message.lower()


# ── 5. Security Score Validation Tests ──────────────────────────────────────

def test_security_score_rejects_boolean_values():
    """Boolean values like True/False must not be accepted as integer security scores."""
    sa = SecurityAgent("sec_test", ContextManager(), MagicMock())
    sa._is_llm_ready = MagicMock(return_value=True)
    sa._is_stub = MagicMock(return_value=False)
    sa._call_llm = MagicMock(return_value=('{"security_score": true, "score_confidence": 0.8}', {"is_genuine": True}))

    score, rationale, conf, comp, limits = sa._generate_final_score(
        candidate_code="code",
        all_vulns=[],
        new_vulns=[],
        resolved_findings=[],
        unresolved_findings=[],
        tool_statuses={},
        initial_score=80,
    )
    assert score is None
    assert "boolean" in rationale.lower()


def test_security_score_rejects_fractional_floats():
    """Fractional floating-point scores like 85.5 must be rejected rather than silently truncated."""
    sa = SecurityAgent("sec_test", ContextManager(), MagicMock())
    sa._is_llm_ready = MagicMock(return_value=True)
    sa._is_stub = MagicMock(return_value=False)
    sa._call_llm = MagicMock(return_value=('{"security_score": 85.5, "score_confidence": 0.8}', {"is_genuine": True}))

    score, rationale, conf, comp, limits = sa._generate_final_score(
        candidate_code="code",
        all_vulns=[],
        new_vulns=[],
        resolved_findings=[],
        unresolved_findings=[],
        tool_statuses={},
        initial_score=80,
    )
    assert score is None
    assert "float" in rationale.lower()


def test_analysis_score_rejects_boolean_and_floats():
    """AnalysisAgent security score generation strictly rejects boolean and fractional float scores."""
    aa = AnalysisAgent("ana_test", ContextManager(), MagicMock())
    aa._is_llm_ready = MagicMock(return_value=True)
    aa._is_stub = MagicMock(return_value=False)

    # Boolean score
    aa._call_llm = MagicMock(return_value=('{"security_score": false, "score_confidence": 0.8}', {"is_genuine": True}))
    score, rationale, _, _, _ = aa._generate_security_score("code", [], {}, "test.cpp")
    assert score is None
    assert "boolean" in rationale.lower()

    # Fractional float score
    aa._call_llm = MagicMock(return_value=('{"security_score": 72.8, "score_confidence": 0.8}', {"is_genuine": True}))
    score, rationale, _, _, _ = aa._generate_security_score("code", [], {}, "test.cpp")
    assert score is None
    assert "float" in rationale.lower()


# ── 6. Optimization Agent Truthful Behavior ─────────────────────────────────

def test_optimization_agent_preserves_code_when_llm_offline():
    """When LLM is offline, OptimizationAgent preserves original source and does not mutate with regex."""
    ctx = ContextManager()
    opt = OptimizationAgent("opt_test", ctx, MagicMock())
    opt._is_llm_ready = MagicMock(return_value=False)

    source = "int main() { for (int i = 0; i <= 10; i++); return 0; }"
    res = opt.process({
        "source_code": source,
        "file_path": "loop.cpp",
        "analysis_report": {"all_findings": [{"type": "off_by_one_error", "description": "loop <= 10"}]},
    })

    assert res["optimized_code"] == source
    assert "<=" in res["optimized_code"]  # Did NOT mutate <= to < via regex
    assert res["status"] == OptimizationStatus.LLM_UNAVAILABLE
    assert len(res["transformations"]) == 0


# ── 7. Verification Acceptance Tri-State Logic ──────────────────────────────

def test_verification_agent_tri_state_acceptance():
    """VerificationAgent distinguishes PASS, FAIL, and INCOMPLETE."""
    va = VerificationAgent("ver_test", ContextManager(), MagicMock())

    # Case 1: Complete pass
    diff_pass = DiffTestResult(passed=True, original_output="hi", optimized_output="hi")
    z3_pass = Z3Result(status="PROVEN_EQUIVALENT")
    passes, reasons, verdict = va._evaluate_acceptance(diff_pass, z3_pass, "EQUIVALENT", [], [])
    assert passes is True
    assert verdict == "PASS"

    # Case 2: Complete failure
    diff_fail = DiffTestResult(passed=False, original_output="a", optimized_output="b", error="output mismatch")
    passes, reasons, verdict = va._evaluate_acceptance(diff_fail, z3_pass, "NOT_EQUIVALENT", [], [])
    assert passes is False
    assert verdict == "FAIL"

    # Case 3: Incomplete (diff test skipped because compiler missing)
    diff_skip = DiffTestResult(passed=False, skipped=True, original_output="", optimized_output="", error="compiler unavailable")
    passes, reasons, verdict = va._evaluate_acceptance(diff_skip, z3_pass, "EQUIVALENT", [], [])
    assert passes is False
    assert verdict == "INCOMPLETE"


# ── 8. Language Restriction Verification ────────────────────────────────────

def test_app_rejects_unsupported_languages():
    """Verify that app.py stream endpoint rejects Python, Java, Go and requires C or C++."""
    from app import app
    client = app.test_client()

    # Test unsupported Python
    resp = client.post("/api/stream", json={"code": "print('hello')", "language": "python"})
    assert resp.status_code == 400
    assert "unsupported language" in resp.get_json()["error"].lower()

    # Test unsupported Java
    resp = client.post("/api/stream", json={"code": "class A {}", "language": "java"})
    assert resp.status_code == 400

    # Test supported C++
    resp = client.post("/api/stream", json={"code": "int main() { return 0; }", "language": "cpp"})
    assert resp.status_code == 200
