"""
Verification Agent — Multi-Layer Correctness, Performance, and Regression Verification.

Upgrades:
  1. Preserves and strengthens the 4 verification layers:
     - Layer 1: Differential Testing (diff_tester.py)
     - Layer 2: Z3 SMT Equivalence (z3_verifier.py)
     - Layer 3: Performance Benchmarking (perf_benchmarker.py)
     - Layer 4: LLM Reasoning Verification (VerificationPromptTemplate)
  2. Candidate compilation & static analysis validation
  3. Finding reassessment: evaluates each original finding as resolved, unresolved, or new
  4. Generates structured feedback reports to drive subsequent iterations in the bounded loop
  5. Truthful acceptance evaluation distinguishing blocking errors from harmless skips
"""

import logging
import os
import re
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

_root = os.path.join(os.path.dirname(__file__), "..", "..")
if _root not in sys.path:
    sys.path.insert(0, _root)

from agent_framework import BaseAgent, ContextManager
from src.analysis.finding_schema import Finding, deduplicate_findings
from src.analysis.tool_runner import ToolRunner, ToolStatus
from src.llm.llm_client import LLMClient
from src.llm.prompt_templates import VerificationPromptTemplate
from src.reasoning.cot_validator import CoTValidator
from src.verification.diff_tester import DifferentialTester, DiffTestResult
from src.verification.z3_verifier import Z3Verifier, Z3Result
from src.verification.perf_benchmarker import PerfBenchmarker, PerfResult

logger = logging.getLogger(__name__)


@dataclass
class VerificationReport:
    status: str                         # "PASS" | "FAIL" | "ROLLBACK"
    passes_acceptance: bool = True
    diff_result: Optional[DiffTestResult] = None
    z3_result: Optional[Z3Result] = None
    perf_result: Optional[PerfResult] = None
    llm_verdict: Optional[str] = None
    reasoning_steps: List[str] = None
    resolved_findings: List[Dict[str, Any]] = None
    unresolved_findings: List[Dict[str, Any]] = None
    new_findings: List[Dict[str, Any]] = None
    blocking_reasons: List[str] = None
    conclusion: str = ""
    summary: str = ""

    def __post_init__(self):
        if self.reasoning_steps is None:
            self.reasoning_steps = []
        if self.resolved_findings is None:
            self.resolved_findings = []
        if self.unresolved_findings is None:
            self.unresolved_findings = []
        if self.new_findings is None:
            self.new_findings = []
        if self.blocking_reasons is None:
            self.blocking_reasons = []


class VerificationAgent(BaseAgent):
    """
    Verification Agent: independently evaluates candidates for behavioral equivalence,
    absence of regressions, and resolution of original findings.
    """

    def __init__(
        self,
        agent_id: str,
        context_manager: ContextManager,
        llm_client: Optional[LLMClient] = None,
        tool_runner: Optional[ToolRunner] = None,
    ):
        super().__init__(agent_id, "verification", context_manager)
        self.llm = llm_client or LLMClient()
        self.cot_val = CoTValidator()
        self.diff_tester = DifferentialTester()
        self.z3 = Z3Verifier()
        self.perf = PerfBenchmarker()
        self.tool_runner = tool_runner or ToolRunner()

    def get_capabilities(self) -> List[str]:
        return [
            "differential_testing",
            "z3_smt_verification",
            "performance_benchmarking",
            "llm_reasoning_verification",
            "candidate_compilation_validation",
            "finding_reassessment",
            "feedback_report_generation",
            "context_rollback_on_failure",
        ]

    def _is_llm_ready(self) -> bool:
        if self.llm is None:
            return False
        if hasattr(self.llm, "_available") and not self.llm._available:
            return False
        if hasattr(self.llm, "is_available"):
            try:
                res = self.llm.is_available()
                if isinstance(res, bool):
                    return res
            except Exception:
                pass
        return bool(getattr(self.llm, "_available", True))

    def _is_stub(self, text: str) -> bool:
        if not text:
            return False
        is_stub_fn = getattr(self.llm, "is_stub", None)
        if callable(is_stub_fn):
            try:
                res = is_stub_fn(text)
                if isinstance(res, bool):
                    return res
            except Exception:
                pass
        return "(LLM offline stub)" in str(text) or "offline stub" in str(text)

    def _call_llm(self, prompt: str, system_prompt: str = "") -> Tuple[str, Dict[str, Any]]:
        if hasattr(self.llm, "generate_with_meta"):
            try:
                res = self.llm.generate_with_meta(prompt, system_prompt=system_prompt)
                if isinstance(res, tuple) and len(res) == 2:
                    return res
            except Exception:
                pass
        if hasattr(self.llm, "generate"):
            try:
                text = self.llm.generate(prompt, system_prompt=system_prompt)
                if isinstance(text, str):
                    is_stub = self._is_stub(text)
                    return text, {"status": "stub" if is_stub else "genuine", "is_genuine": not is_stub}
            except Exception as e:
                return "", {"status": "error", "is_genuine": False, "error": str(e)}
        return "", {"status": "unavailable", "is_genuine": False}

    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Verify candidate code against original code and analysis findings."""
        original = input_data.get("original_code") or self.context.get("original_code") or ""
        optimized = input_data.get("optimized_code") or input_data.get("candidate_code")
        if not optimized:
            opt_report = (
                self.context.get("optimization_results")
                or self.context.get("optimization_suggestions")
                or {}
            )
            optimized = opt_report.get("optimized_code", original)
        file_path = input_data.get("file_path") or self.context.get("source_file") or "<unknown>"
        iteration = input_data.get("iteration", self.context.get("iteration_count", 1) or 1)

        # Retrieve initial analysis report
        analysis_report = (
            input_data.get("analysis_report")
            or self.context.get("initial_analysis_report")
            or self.context.get("analysis_results")
            or {}
        )
        original_findings = (
            analysis_report.get("all_findings")
            or analysis_report.get("rule_findings")
            or []
        )

        if not original or not optimized:
            return {
                "status": "FAIL",
                "passes_acceptance": False,
                "error": "Missing original or candidate code.",
                "unresolved_findings": original_findings,
            }

        # ── Layer 1: Differential Testing ─────────────────────────────────────
        logger.info(f"VerificationAgent [Attempt {iteration}/3 - Layer 1/4]: Differential Testing …")
        diff_result = self.diff_tester.test(original, optimized)
        _dt_status = "PASS" if diff_result.passed else f"FAIL ({diff_result.error or 'outputs differ'})"
        logger.info(f"VerificationAgent [Layer 1/4]: Differential Test -> {_dt_status}")

        # ── Layer 2: Z3 SMT Verification ───────────────────────────────────────
        logger.info(f"VerificationAgent [Attempt {iteration}/3 - Layer 2/4]: Z3 Equivalence …")
        z3_result = self.z3.verify(original, optimized)
        logger.info(f"VerificationAgent [Layer 2/4]: Z3 -> {z3_result.status}")

        # ── Layer 3: Performance Benchmarking ─────────────────────────────────
        logger.info(f"VerificationAgent [Attempt {iteration}/3 - Layer 3/4]: Performance Benchmark …")
        perf_result = self.perf.benchmark(original, optimized)
        logger.info(f"VerificationAgent [Layer 3/4]: Perf -> {perf_result.summary()}")

        # ── Layer 4: LLM Reasoning Verification ────────────────────────────────
        logger.info(f"VerificationAgent [Attempt {iteration}/3 - Layer 4/4]: LLM Reasoning …")
        _diff_passed_for_llm = True if diff_result.skipped else diff_result.passed
        llm_verdict, reasoning_steps, llm_resolved, llm_unresolved = self._llm_verify(
            original=original,
            optimized=optimized,
            diff_passed=_diff_passed_for_llm,
            z3_status=z3_result.status,
            perf_summary=perf_result.summary(),
            analysis_findings=original_findings,
        )
        logger.info(f"VerificationAgent [Layer 4/4]: LLM verdict -> {llm_verdict}")

        # ── Reassess Findings and Detect Regressions ──────────────────────────
        resolved_findings, unresolved_findings, new_findings = self._reassess_findings(
            original=original,
            candidate=optimized,
            original_findings=original_findings,
            file_path=file_path,
        )

        # ── Acceptance Evaluation ─────────────────────────────────────────────
        passes_acceptance, blocking_reasons, acceptance_verdict = self._evaluate_acceptance(
            diff_result=diff_result,
            z3_result=z3_result,
            llm_verdict=llm_verdict,
            unresolved_findings=unresolved_findings,
            new_findings=new_findings,
            resolved_findings=resolved_findings,
        )

        status = acceptance_verdict

        # ── Build Feedback Report for Potential Retries ────────────────────────
        feedback_report = {
            "iteration": iteration,
            "max_iterations": 3,
            "passes_acceptance": passes_acceptance,
            "failed_layers": [r.split(":")[0] for r in blocking_reasons],
            "blocking_reasons": blocking_reasons,
            "diagnostics": self._gather_diagnostics(diff_result, z3_result, blocking_reasons),
            "unresolved_findings": unresolved_findings,
            "new_findings": new_findings,
            "specific_corrections": self._generate_corrections(blocking_reasons, unresolved_findings, new_findings),
            "actionable_instructions": self._generate_corrections(blocking_reasons, unresolved_findings, new_findings),
        }

        conclusion = self._build_conclusion(status, diff_result, z3_result, perf_result, blocking_reasons)
        summary = self._build_summary(
            status, file_path, diff_result, z3_result, perf_result, llm_verdict,
            resolved_findings, unresolved_findings, new_findings, blocking_reasons
        )

        result_dict = {
            "status": status,
            "passes_acceptance": passes_acceptance,
            "diff_passed": None if diff_result.skipped else diff_result.passed,
            "diff_error": diff_result.error,
            "z3_status": z3_result.status,
            "z3_explanation": z3_result.explanation,
            "perf_summary": perf_result.summary(),
            "llm_verdict": llm_verdict,
            "reasoning_steps": reasoning_steps,
            "resolved_findings": resolved_findings,
            "unresolved_findings": unresolved_findings,
            "new_findings": new_findings,
            "blocking_reasons": blocking_reasons,
            "feedback_report": feedback_report,
            "conclusion": conclusion,
            "summary": summary,
            "layer_diagnostics": {
                "layer1_diff": {"passed": diff_result.passed, "error": diff_result.error},
                "layer2_z3": {"status": z3_result.status, "explanation": z3_result.explanation},
                "layer3_perf": {"status": "COMPLETED" if perf_result.available else "SKIPPED", "summary": perf_result.summary()},
                "layer4_llm": {"verdict": llm_verdict},
            },
        }

        # Store in shared context
        self.context.set("verification_results", result_dict)
        self.context.set("verification_status", result_dict)
        self.context.set("unresolved_findings", unresolved_findings)

        logger.info(f"Verification complete: status={status}, passes={passes_acceptance}")
        return result_dict

    # ── Acceptance Evaluation ─────────────────────────────────────────────────

    def _evaluate_acceptance(
        self,
        diff_result: DiffTestResult,
        z3_result: Z3Result,
        llm_verdict: str,
        unresolved_findings: List[Dict[str, Any]],
        new_findings: List[Dict[str, Any]],
        resolved_findings: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[bool, List[str], str]:
        """
        Evaluate candidate against strict verification acceptance criteria.
        Returns (passes_acceptance: bool, blocking_reasons: List[str], verdict: str).
        Verdict is one of 'PASS', 'FAIL', 'INCOMPLETE'.
        """
        blocking_reasons: List[str] = []
        is_incomplete = False

        # 1. Candidate compilation failure is always blocking
        if diff_result.compile_error_optimized:
            blocking_reasons.append(
                f"Candidate compilation failed: {diff_result.compile_error_optimized.strip()}"
            )

        # 2. Differential test failure or skip
        if diff_result.skipped:
            is_incomplete = True
            blocking_reasons.append(
                f"Differential testing could not execute: {diff_result.error or 'compiler unavailable'}"
            )
        elif not diff_result.passed and not diff_result.compile_error_original:
            real_diff_failure = True
            # Check if difference is attributable to eliminating original undefined behavior
            has_ub_fix = any(
                f.get("type") in ("uninitialized_variable", "division_by_zero_risk", "use_after_free")
                for f in (resolved_findings or [])
            )
            if has_ub_fix and z3_result.status == "PROVEN_EQUIVALENT":
                logger.info(
                    "Differential output difference tolerated because original program exhibited "
                    "undefined behavior (uninitialized variable/UB) and Z3 proved formal equivalence."
                )
                real_diff_failure = False

            if real_diff_failure:
                err_detail = diff_result.error or f"original='{diff_result.original_output}', candidate='{diff_result.optimized_output}'"
                blocking_reasons.append(f"Differential test output/returncode mismatch: {err_detail}")

        # 3. Z3 solver found a concrete counterexample
        if z3_result.status == "COUNTEREXAMPLE_FOUND":
            blocking_reasons.append(
                f"Z3 formal solver proved non-equivalence: {z3_result.explanation}"
            )

        # 4. LLM verified non-equivalence with definitive verdict
        if llm_verdict == "NOT_EQUIVALENT" and not diff_result.skipped:
            blocking_reasons.append(
                "LLM semantic equivalence analysis determined code is NOT_EQUIVALENT."
            )

        # 5. Candidate introduced new high or critical severity security defects
        new_severe = [
            f for f in new_findings
            if f.get("severity") in ("critical", "high")
        ]
        if new_severe:
            blocking_reasons.append(
                f"Candidate introduced {len(new_severe)} new high/critical severity security finding(s): "
                + ", ".join(f.get("type", "unknown") for f in new_severe)
            )

        # 6. Critical uninitialized or memory corruption finding remains completely unaddressed
        unresolved_critical = [
            f for f in unresolved_findings
            if f.get("severity") in ("critical", "high")
            and f.get("status") == "still_unresolved"
        ]
        if unresolved_critical:
            blocking_reasons.append(
                f"{len(unresolved_critical)} critical/high finding(s) remain unresolved."
            )

        if not blocking_reasons:
            return True, [], "PASS"
        elif is_incomplete and not any("failed" in r.lower() or "mismatch" in r.lower() or "counterexample" in r.lower() for r in blocking_reasons):
            return False, blocking_reasons, "INCOMPLETE"
        else:
            return False, blocking_reasons, "FAIL"

    # ── Reassess Findings ─────────────────────────────────────────────────────

    def _reassess_findings(
        self,
        original: str,
        candidate: str,
        original_findings: List[Dict[str, Any]],
        file_path: str,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Compare original findings to candidate to determine which are resolved,
        which remain unresolved, and what new issues were introduced.
        """
        resolved: List[Dict[str, Any]] = []
        unresolved: List[Dict[str, Any]] = []

        for f in original_findings:
            f_type = f.get("type", "")
            f_desc = f.get("description", "")
            f_copy = dict(f)

            is_fixed = False
            evidence = ""

            # Check unsafe functions (gets, strcpy, sprintf, etc.)
            if "unsafe_" in f_type or "gets" in f_type or "strcpy" in f_type or "sprintf" in f_type:
                fn_name = f_type.replace("unsafe_", "")
                if re.search(rf"\b{re.escape(fn_name)}\s*\(", original) and not re.search(rf"\b{re.escape(fn_name)}\s*\(", candidate):
                    is_fixed = True
                    evidence = f"Unsafe function {fn_name}() was removed/replaced."

            # Check off-by-one / loop boundary
            if "off_by_one" in f_type or "buffer_overflow" in f_type:
                orig_loops = re.findall(r'for\s*\([^;]*;\s*(\w+)\s*<=\s*(\d+|\w+)', original)
                cand_loops = re.findall(r'for\s*\([^;]*;\s*(\w+)\s*<\s*(\d+|\w+)', candidate)
                if orig_loops and cand_loops:
                    is_fixed = True
                    evidence = f"Loop boundary corrected to strict upper bound: '{cand_loops[0][0]} < {cand_loops[0][1]}'."

            # Check uninitialized variable
            if "uninitialized" in f_type:
                var_match = re.search(r"Variable '(\w+)'", f_desc) or re.search(r"\b([a-zA-Z_]\w*)\b", f_desc)
                if var_match:
                    varname = var_match.group(1)
                    init_pat = re.compile(rf'\b(?:int|float|double|char|long|short|unsigned|bool)\s+{re.escape(varname)}\s*=\s*[^;]+;', re.MULTILINE)
                    if init_pat.search(candidate):
                        is_fixed = True
                        evidence = f"Variable '{varname}' is explicitly initialized upon declaration."

            # Check division by zero
            if "division_by_zero" in f_type:
                div_match = re.search(r'(?:divisor|variable)\s*[\'"]?(\w+)[\'"]?', f_desc, re.IGNORECASE)
                varname = div_match.group(1) if div_match else None
                if varname:
                    guard_pat = re.compile(rf'if\s*\([^)]*\b{re.escape(varname)}\s*(?:!=|==|>|<)\s*0', re.MULTILINE)
                    if guard_pat.search(candidate):
                        is_fixed = True
                        evidence = f"Added conditional guard on divisor '{varname}' before division."
                elif re.search(r'if\s*\([^)]*(?:!=|==|>|<)\s*0', candidate):
                    is_fixed = True
                    evidence = "Added zero-check guard prior to division operation."

            # Check memory leak
            if "memory_leak" in f_type:
                ptr_match = re.search(r"pointer\s*[\'\"]?(\w+)[\'\"]?", f_desc, re.IGNORECASE)
                ptr_name = ptr_match.group(1) if ptr_match else None
                if ptr_name and re.search(rf'\bfree\s*\(\s*{re.escape(ptr_name)}\s*\)', candidate):
                    is_fixed = True
                    evidence = f"Deallocation free({ptr_name}) explicitly added for allocated memory."
                elif re.search(r'\bfree\s*\(', candidate) and not re.search(r'\bfree\s*\(', original):
                    is_fixed = True
                    evidence = "Explicit free() deallocation statement added in candidate."

            if is_fixed:
                f_copy["resolution_status"] = "resolved"
                f_copy["resolution_evidence"] = evidence
                resolved.append(f_copy)
            else:
                f_copy["resolution_status"] = "still_unresolved"
                f_copy["resolution_evidence"] = "Finding pattern still present in candidate code."
                unresolved.append(f_copy)

        # Detect new defects introduced in candidate code
        new_findings: List[Dict[str, Any]] = []

        # Check for newly introduced unsafe functions
        unsafe_patterns = [
            (r'\bgets\s*\(', "unsafe_gets", "high", "CWE-242", "gets() is unconditionally unsafe."),
            (r'\bstrcpy\s*\(', "unsafe_strcpy", "medium", "CWE-676", "strcpy() lacks bounds checks."),
            (r'\bstrcat\s*\(', "unsafe_strcat", "medium", "CWE-676", "strcat() lacks bounds checks."),
            (r'\bsprintf\s*\(', "unsafe_sprintf", "medium", "CWE-676", "sprintf() lacks explicit bounds."),
        ]
        for pat, ftype, sev, cwe, desc in unsafe_patterns:
            if re.search(pat, candidate) and not re.search(pat, original):
                new_findings.append(Finding(
                    type=ftype,
                    category="security",
                    description=f"Candidate introduced new unsafe call: {desc}",
                    severity=sev,
                    confidence=0.90,
                    source_tool="verification_regression_checker",
                    cwe_id=cwe,
                    status="confirmed",
                    is_confirmed=True,
                ).to_dict())

        return resolved, unresolved, new_findings

    # ── LLM Verification ──────────────────────────────────────────────────────

    def _llm_verify(
        self,
        original: str,
        optimized: str,
        diff_passed: Optional[bool],
        z3_status: str,
        perf_summary: str,
        analysis_findings: List[Dict[str, Any]],
    ) -> Tuple[str, List[str], List[str], List[str]]:
        if not self._is_llm_ready():
            return "UNCERTAIN", ["LLM is offline; verification based strictly on formal and dynamic tests."], [], []

        prompt = VerificationPromptTemplate.build(
            original_code=original,
            optimized_code=optimized,
            diff_test_passed=diff_passed,
            z3_status=z3_status,
            perf_summary=perf_summary,
            analysis_findings=analysis_findings,
        )

        raw, meta = self._call_llm(
            prompt,
            system_prompt=VerificationPromptTemplate.SYSTEM,
        )

        if not meta.get("is_genuine") or self._is_stub(raw):
            return "UNCERTAIN", ["LLM returned synthetic stub or connection failed."], [], []

        cot = self.cot_val.validate(raw)
        if not cot.is_valid:
            return "UNCERTAIN", ["LLM verification output could not be parsed as valid JSON."], [], []

        verdict = (cot.verdict or "UNCERTAIN").upper()
        if verdict not in ("EQUIVALENT", "NOT_EQUIVALENT", "UNCERTAIN"):
            verdict = "UNCERTAIN"

        return verdict, cot.reasoning_steps, [], []

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _gather_diagnostics(
        self, diff_result: DiffTestResult, z3_result: Z3Result, blocking_reasons: List[str]
    ) -> str:
        parts = []
        if diff_result.compile_error_optimized:
            parts.append(f"Compiler Error:\n{diff_result.compile_error_optimized}")
        if diff_result.error:
            parts.append(f"Differential Test Diagnostic:\n{diff_result.error}")
        if z3_result.status == "COUNTEREXAMPLE_FOUND":
            parts.append(f"Z3 Counterexample:\n{z3_result.explanation}")
        if not parts and blocking_reasons:
            parts.extend(blocking_reasons)
        return "\n\n".join(parts)

    def _generate_corrections(
        self,
        blocking_reasons: List[str],
        unresolved_findings: List[Dict[str, Any]],
        new_findings: List[Dict[str, Any]],
    ) -> List[str]:
        corrections = []
        for r in blocking_reasons:
            if "compilation failed" in r.lower():
                corrections.append("Fix syntax and type declarations so the candidate compiles cleanly.")
            elif "differential test output mismatch" in r.lower():
                corrections.append("Ensure optimized algorithm preserves the exact output produced by the original program.")
            elif "z3" in r.lower():
                corrections.append("Ensure formal equivalence for all inputs: do not alter return calculation semantics.")

        for uf in unresolved_findings:
            corrections.append(f"Resolve finding '{uf.get('type')}': {uf.get('recommendation', uf.get('description'))}")

        for nf in new_findings:
            corrections.append(f"Remove regression '{nf.get('type')}': {nf.get('description')}")

        return list(dict.fromkeys(corrections))

    def _build_conclusion(
        self,
        status: str,
        diff: DiffTestResult,
        z3: Z3Result,
        perf: PerfResult,
        blocking_reasons: List[str],
    ) -> str:
        parts = [f"Verification Status: {status}."]
        diff_str = "PASS" if diff.passed else f"SKIPPED ({diff.error})" if diff.skipped else f"FAIL ({diff.error})"
        parts.append(f"Differential test: {diff_str}")
        parts.append(f"Z3 equivalence: {z3.status}")
        if perf.available and not perf.error:
            parts.append(perf.summary())
        if blocking_reasons:
            parts.append(f"Blocking issues: {'; '.join(blocking_reasons)}")
        return " | ".join(parts)

    def _build_summary(
        self,
        status: str,
        file_path: str,
        diff: DiffTestResult,
        z3: Z3Result,
        perf: PerfResult,
        llm_verdict: str,
        resolved: List[Dict[str, Any]],
        unresolved: List[Dict[str, Any]],
        new_findings: List[Dict[str, Any]],
        blocking_reasons: List[str],
    ) -> str:
        diff_str = "PASS" if diff.passed else f"SKIPPED ({diff.error})" if diff.skipped else f"FAIL ({diff.error})"
        lines = [
            f"Verification Report: {file_path}",
            f"Overall Status    : {status}",
            f"Differential Test : {diff_str}",
            f"Z3 Verification   : {z3.status}" + (f" — {z3.explanation}" if z3.explanation else ""),
            f"Performance       : {perf.summary()}",
            f"LLM Verdict       : {llm_verdict}",
            f"Findings Resolved : {len(resolved)}",
            f"Unresolved        : {len(unresolved)}",
            f"New Regressions   : {len(new_findings)}",
        ]
        if blocking_reasons:
            lines.append("Blocking issues:")
            for b in blocking_reasons:
                lines.append(f"  • {b}")
        return "\n".join(lines)
