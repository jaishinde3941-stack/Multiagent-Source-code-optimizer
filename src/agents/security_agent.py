"""
Security Agent — Final Security Assessment, Vulnerability Auditing, and Score Generation.

Upgrades:
  1. Conventional tool family integration (Clang/Clang++, Clang-Tidy, Cppcheck, ASan, UBSan)
  2. Evaluates the actual candidate from the optimization-verification loop (no silent revert)
  3. Reassesses original findings and identifies newly introduced vulnerabilities
  4. Generates rubric-based final security score (0-100) using local LLM with range validation
  5. Initial-to-final score comparison (initial score, final score, score change, explanation)
  6. Truthful failure handling when Ollama or tools are unavailable (no fabricated scores)
"""

import json
import logging
import os
import re
import shutil
import sys
from typing import Any, Dict, List, Optional, Tuple

_root = os.path.join(os.path.dirname(__file__), "..", "..")
if _root not in sys.path:
    sys.path.insert(0, _root)

from agent_framework import BaseAgent, ContextManager
from src.analysis.finding_schema import Finding, deduplicate_findings
from src.analysis.tool_runner import ToolRunner, ToolStatus
from src.llm.llm_client import LLMClient
from src.llm.prompt_templates import SecurityPromptTemplate, SecurityScoringPromptTemplate
from src.reasoning.cot_validator import CoTValidator

logger = logging.getLogger(__name__)


class SecurityAgent(BaseAgent):
    """
    Security Agent: performs final security assessment of the candidate code,
    detects new vulnerabilities, reassesses original findings, and generates final score.
    """

    # ── Layer 1: Unsafe function patterns ─────────────────────────────────────
    _UNSAFE_FUNCTIONS = [
        (
            r"\bgets\s*\(",
            "unsafe_gets", "high", "CWE-242",
            "gets() is unconditionally unsafe — no bound checking on input length.",
            "Replace gets() with fgets(buf, sizeof(buf), stdin).",
        ),
        (
            r'\bscanf\s*\(\s*"[^"]*%s',
            "unsafe_scanf_s", "high", "CWE-134",
            "scanf %s reads an unbounded string — add a field width limit e.g. %127s.",
            "Add field width to format: scanf(\"%127s\", buf).",
        ),
        (
            r"\bstrcpy\s*\(",
            "unsafe_strcpy", "medium", "CWE-676",
            "strcpy() copies without bound checking — destination may overflow.",
            "Replace with strncpy(dst, src, sizeof(dst) - 1) or strlcpy().",
        ),
        (
            r"\bstrcat\s*\(",
            "unsafe_strcat", "medium", "CWE-676",
            "strcat() appends without bound checking — destination may overflow.",
            "Replace with strncat(dst, src, sizeof(dst) - strlen(dst) - 1).",
        ),
        (
            r"\bsprintf\s*\(",
            "unsafe_sprintf", "medium", "CWE-676",
            "sprintf() writes unbounded output — use snprintf() with explicit size.",
            "Replace with snprintf(buf, sizeof(buf), fmt, ...).",
        ),
    ]

    _FORMAT_STRING_RE = re.compile(
        r"\b(printf|fprintf|sprintf|snprintf|vprintf|vsprintf)\s*\(\s*(\w+)\s*[,)]",
        re.MULTILINE,
    )

    def __init__(
        self,
        agent_id: str,
        context_manager: ContextManager,
        llm_client: Optional[LLMClient] = None,
        tool_runner: Optional[ToolRunner] = None,
    ):
        self.tool_runner = tool_runner or ToolRunner()
        self.llm = llm_client or LLMClient()
        self.cot_val = CoTValidator()
        self._cppcheck_available = bool(self.tool_runner.find_executable("cppcheck"))
        super().__init__(agent_id, "security", context_manager)

    def get_capabilities(self) -> List[str]:
        caps = [
            "buffer_overflow_detection",
            "format_string_detection",
            "use_after_free_detection",
            "integer_overflow_detection",
            "null_dereference_detection",
            "taint_flow_heuristics",
            "security_rollback",
            "llm_security_analysis",
            "final_security_scoring",
            "score_comparison",
            "conventional_tool_integration",
        ]
        if self._cppcheck_available:
            caps.append("cppcheck_static_analysis")
        return caps

    @staticmethod
    def _check_cppcheck() -> bool:
        """Check if cppcheck executable is available on PATH or standard install dirs."""
        if shutil.which("cppcheck"):
            return True
        for p in [r"C:\Program Files\Cppcheck\cppcheck.exe", r"C:\Program Files (x86)\Cppcheck\cppcheck.exe"]:
            if os.path.isfile(p):
                return True
        return False

    def _cppcheck_scan(self, code: str, filename: str = "test.cpp") -> List[Dict[str, Any]]:
        """Run cppcheck and return findings list (backward compatibility helper)."""
        res = self.tool_runner.run_cppcheck(code, filename)
        findings = []
        for f in res.findings:
            raw_type = f.get("type", "finding")
            t_name = raw_type if raw_type.startswith("cppcheck_") else f"cppcheck_{raw_type}"
            findings.append({
                "type": t_name,
                "severity": f.get("severity", "medium"),
                "description": f.get("description", ""),
                "source": "cppcheck",
                "cwe_id": f.get("cwe_id", "CWE-398"),
                "line": f.get("line", 1),
            })
        return findings

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
        """Perform comprehensive security assessment on the final candidate code."""
        original_code = input_data.get("original_code") or self.context.get("original_code") or ""
        optimized_code = input_data.get("optimized_code") or self.context.get("current_candidate") or original_code
        file_path = input_data.get("file_path") or self.context.get("source_file") or "<unknown>"

        initial_report = (
            input_data.get("initial_analysis_report")
            or input_data.get("analysis_report")
            or self.context.get("initial_analysis_report")
            or self.context.get("analysis_report")
            or self.context.get("analysis_results")
            or {}
        )
        initial_score = input_data.get("initial_score", initial_report.get("security_score"))
        if initial_score is None:
            initial_score = self.context.get("initial_security_score")

        unresolved_input = input_data.get("unresolved_findings") or self.context.get("unresolved_findings") or []

        if not optimized_code.strip():
            logger.error("SecurityAgent: no code provided for security audit")
            return {
                "file_path": file_path,
                "error": "No code provided",
                "status": "PASS",
                "overall_risk": "none",
                "security_score": None,
                "all_vulnerabilities": [],
                "new_vulnerabilities": [],
            }

        logger.info(
            f"SecurityAgent: auditing candidate '{os.path.basename(file_path)}' "
            f"({len(optimized_code)} chars)"
        )

        sources: List[str] = []
        assessment_limitations: List[str] = []

        # ── 1. Layer 1: Rule-based scan ───────────────────────────────────────
        orig_rule = self._rule_scan(original_code)
        opt_rule = self._rule_scan(optimized_code)
        sources.append("rules")

        # ── 2. Layer 2: Heuristic scan ────────────────────────────────────────
        orig_heuristic, _ = self._heuristic_scan(original_code)
        opt_heuristic, opt_scores = self._heuristic_scan(optimized_code)
        sources.append("heuristics")

        # ── 3. Layer 3: Conventional Tool Runner on Candidate ─────────────────
        tool_results = self.tool_runner.run_all_tools_concurrently(
            source_code=optimized_code,
            file_path=file_path,
        )
        tool_statuses: Dict[str, str] = {}
        tool_findings: List[Dict[str, Any]] = []

        for tname, tres in tool_results.items():
            tool_statuses[tname] = tres.status
            if tres.findings:
                tool_findings.extend(tres.findings)
            if tres.limitations:
                assessment_limitations.extend(tres.limitations)
            if tres.status == ToolStatus.UNAVAILABLE:
                assessment_limitations.append(f"{tname} is unavailable on this system.")

        if any(tres.status in (ToolStatus.PASSED, ToolStatus.FINDINGS) for tres in tool_results.values()):
            sources.append("conventional_tools")

        # ── 4. Layer 4: LLM Semantic Scan ─────────────────────────────────────
        orig_all_base = orig_rule + orig_heuristic
        baseline_types = list({f["type"] for f in orig_all_base})
        llm_findings, llm_reasoning, llm_conclusion, llm_conf = self._llm_scan(
            optimized_code=optimized_code,
            original_code=original_code,
            baseline_types=baseline_types,
            tool_findings=tool_findings,
            tool_statuses=tool_statuses,
        )
        if llm_findings:
            sources.append("llm")

        # ── 5. Consolidate and Deduplicate Candidate Vulnerabilities ──────────
        raw_opt_vulns = opt_rule + opt_heuristic + tool_findings + llm_findings
        all_vulns, _ = deduplicate_findings(raw_opt_vulns)

        # ── 6. Detect New and Resolved Vulnerabilities ────────────────────────
        orig_findings_combined = list(initial_report.get("all_findings", [])) + orig_all_base
        if original_code.strip() == optimized_code.strip():
            new_vulns = []
        else:
            new_vulns = self._find_new_vulnerabilities(orig_findings_combined, all_vulns)
        resolved_findings, unresolved_findings = self._partition_resolved(
            initial_report.get("all_findings") or orig_all_base,
            all_vulns,
        )

        # ── 7. Overall Risk Assessment ────────────────────────────────────────
        overall_risk = self._compute_risk(all_vulns)

        # ── 8. Final Security Scoring (0 to 100) ──────────────────────────────
        final_score, score_rationale, score_conf, completeness, extra_limits = self._generate_final_score(
            candidate_code=optimized_code,
            all_vulns=all_vulns,
            new_vulns=new_vulns,
            resolved_findings=resolved_findings,
            unresolved_findings=unresolved_findings,
            tool_statuses=tool_statuses,
            initial_score=initial_score,
        )
        if extra_limits:
            assessment_limitations.extend(extra_limits)
        assessment_limitations = list(dict.fromkeys(assessment_limitations))

        # ── 9. Score Comparison ───────────────────────────────────────────────
        score_change = None
        score_explanation = ""
        if initial_score is not None and final_score is not None:
            score_change = final_score - initial_score
            if score_change > 0:
                score_explanation = f"Security score improved by +{score_change} points after resolving vulnerabilities."
            elif score_change < 0:
                score_explanation = f"Security score decreased by {score_change} points due to introduced or remaining risks."
            else:
                score_explanation = "Security score remained unchanged."
        elif initial_score is not None and final_score is None:
            score_explanation = "Initial score was available, but final LLM security score could not be completed."
        else:
            score_explanation = "Scores are not directly comparable because LLM scoring was unavailable for one or both phases."

        # ── 10. Rollback / Decision Logic ─────────────────────────────────────
        rollback_triggers = [
            v for v in new_vulns
            if v.get("severity") in ("high", "critical")
            and (
                v.get("source_tool") in ("rule", "heuristic", "conventional_tools", "asan", "ubsan", "clang-tidy", "cppcheck")
                or v.get("source") in ("rule", "heuristic", "conventional_tools", "asan", "ubsan", "clang-tidy", "cppcheck")
            )
            and v.get("confidence", 0) >= 0.8
        ]

        if rollback_triggers:
            logger.warning(
                f"SecurityAgent: {len(rollback_triggers)} new high-severity defect(s) detected in candidate."
            )
            status = "ROLLBACK"
        else:
            status = "PASS"

        # ── 11. Final Summary ─────────────────────────────────────────────────
        summary = self._build_summary(
            file_path=file_path,
            all_vulns=all_vulns,
            new_vulns=new_vulns,
            risk=overall_risk,
            status=status,
            final_score=final_score,
            initial_score=initial_score,
            score_change=score_change,
            completeness=completeness,
        )

        result = {
            "file_path": file_path,
            "security_score": final_score,
            "initial_score": initial_score,
            "score_change": score_change,
            "score_explanation": score_explanation,
            "score_rationale": score_rationale,
            "score_confidence": score_conf,
            "assessment_completeness": completeness,
            "all_vulnerabilities": all_vulns,
            "new_vulnerabilities": new_vulns,
            "resolved_findings": resolved_findings,
            "unresolved_findings": unresolved_findings,
            "heuristic_scores": opt_scores,
            "tool_statuses": tool_statuses,
            "overall_risk": overall_risk,
            "status": status,
            "rollback_triggers": rollback_triggers,
            "llm_reasoning": llm_reasoning,
            "llm_conclusion": llm_conclusion,
            "assessment_limitations": assessment_limitations,
            "sources": sources,
            "summary": summary,
        }

        # Store in shared context
        self.context.set("security_report", result)
        self.context.set("security_findings", result)
        self.context.set("final_security_score", final_score)

        logger.info(
            f"SecurityAgent: audit complete — status={status}, risk={overall_risk}, "
            f"score={final_score if final_score is not None else 'N/A'}/100"
        )
        return result

    # ── Final Score Generation ────────────────────────────────────────────────

    def _generate_final_score(
        self,
        candidate_code: str,
        all_vulns: List[Dict[str, Any]],
        new_vulns: List[Dict[str, Any]],
        resolved_findings: List[Dict[str, Any]],
        unresolved_findings: List[Dict[str, Any]],
        tool_statuses: Dict[str, str],
        initial_score: Optional[int],
    ) -> Tuple[Optional[int], str, float, str, List[str]]:
        """Generate final security score (0-100) using Ollama and rubric."""
        if not self._is_llm_ready():
            return (
                None,
                "Final security score could not be completed because Ollama was offline.",
                0.0,
                "partial - conventional tools only",
                ["Ollama unavailable for final security score; score not fabricated."],
            )

        prompt = SecurityPromptTemplate.build(
            optimized_code=candidate_code,
            tool_findings=all_vulns,
            tool_statuses=tool_statuses,
            unresolved_findings=unresolved_findings,
            initial_score=initial_score,
        )

        raw, meta = self._call_llm(
            prompt,
            system_prompt=SecurityPromptTemplate.SYSTEM,
        )

        if not meta.get("is_genuine") or self._is_stub(raw):
            return (
                None,
                "Final security score could not be completed (Ollama returned stub or connection failed).",
                0.0,
                "partial - conventional tools only",
                ["Ollama unavailable or returned synthetic stub; score not fabricated."],
            )

        parsed = self.cot_val.extract_json(raw)
        if not parsed or "security_score" not in parsed:
            return (
                None,
                "Final LLM security scoring output could not be parsed as valid JSON.",
                0.0,
                "incomplete",
                ["Malformed LLM scoring response."],
            )

        raw_score = parsed["security_score"]
        # Explicitly reject booleans (True/False are subclasses of int in Python)
        if isinstance(raw_score, bool):
            return (
                None,
                "LLM returned boolean value for security score instead of an integer.",
                0.0,
                "invalid_type",
                ["Boolean score received from LLM."],
            )
        # Reject floating point values that are not exact integers
        if isinstance(raw_score, float) and not raw_score.is_integer():
            return (
                None,
                f"LLM returned fractional float value {raw_score} for security score.",
                0.0,
                "invalid_type",
                ["Floating point score cannot be silently truncated to integer."],
            )

        try:
            score_val = int(raw_score)
            if not (0 <= score_val <= 100):
                logger.warning(f"Final score {score_val} outside [0, 100] – rejecting.")
                return (
                    None,
                    f"LLM final score {score_val} was outside valid range [0, 100].",
                    0.0,
                    "invalid_range",
                    ["LLM returned out-of-range final security score."],
                )
        except (ValueError, TypeError):
            return (
                None,
                "LLM returned non-integer final security score.",
                0.0,
                "invalid_type",
                ["Non-numeric score received from LLM."],
            )

        rationale = str(parsed.get("score_rationale", "Evidence-based final security rubric score."))
        raw_conf = parsed.get("score_confidence", 0.8)
        try:
            conf = float(raw_conf)
            if not (0.0 <= conf <= 1.0):
                conf = max(0.0, min(1.0, conf))
        except (ValueError, TypeError):
            conf = 0.8
        completeness = str(parsed.get("assessment_completeness", "full"))
        extra_limits = [str(x) for x in parsed.get("assessment_limitations", [])]

        return score_val, rationale, conf, completeness, extra_limits

    # ── Layer 1: Rule-based scan ───────────────────────────────────────────────

    def _rule_scan(self, code: str) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        if not code.strip():
            return findings

        lines = code.splitlines()

        for pattern, vtype, severity, cwe, desc, fix in self._UNSAFE_FUNCTIONS:
            for ln_no, line in enumerate(lines, 1):
                if re.search(pattern, line):
                    findings.append(Finding(
                        type=vtype,
                        category="security",
                        description=desc,
                        severity=severity,
                        line=ln_no,
                        cwe_id=cwe,
                        recommendation=fix,
                        confidence=0.9,
                        source_tool="rule",
                        status="confirmed",
                        is_confirmed=True,
                    ).to_dict())

        for m in self._FORMAT_STRING_RE.finditer(code):
            fn_name, arg = m.group(1), m.group(2)
            if not arg.startswith('"'):
                ln_no = code[: m.start()].count("\n") + 1
                findings.append(Finding(
                    type="format_string_bug",
                    category="security",
                    severity="high",
                    line=ln_no,
                    description=f"{fn_name}() called with variable '{arg}' as format string (CWE-134).",
                    cwe_id="CWE-134",
                    recommendation=f'Always use literal format string: {fn_name}("%s", {arg}).',
                    confidence=0.9,
                    source_tool="rule",
                    status="confirmed",
                    is_confirmed=True,
                ).to_dict())

        findings.extend(self._detect_use_after_free(code, lines))
        return findings

    def _detect_use_after_free(self, code: str, lines: List[str]) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        dealloc_re = re.compile(
            r"\bfree\s*\(\s*(\w+)\s*\)"
            r"|\bdelete\s*\[\s*\]\s*(\w+)"
            r"|\bdelete\s+(\w+)",
            re.MULTILINE,
        )

        freed_vars: Dict[str, int] = {}
        for m in dealloc_re.finditer(code):
            var = m.group(1) or m.group(2) or m.group(3)
            freed_vars[var] = code[: m.start()].count("\n") + 1

        for var, free_line in freed_vars.items():
            deref_re = re.compile(
                rf"\*\s*{re.escape(var)}\b"
                rf"|{re.escape(var)}\s*->\s*\w+"
                rf"|{re.escape(var)}\s*\["
            )
            direct_assign_re = re.compile(
                rf"(?<![*\[])\b{re.escape(var)}\s*=\s*(?!=)"
            )
            for ln_no, line in enumerate(lines, 1):
                if ln_no <= free_line:
                    continue
                if re.search(
                    rf"\bfree\s*\(\s*{re.escape(var)}\s*\)"
                    rf"|\bdelete(?:\s*\[\s*\])?\s+{re.escape(var)}",
                    line,
                ):
                    break
                if direct_assign_re.search(line) and "->" not in line and not re.search(rf"\*\s*{re.escape(var)}", line):
                    break
                if deref_re.search(line):
                    findings.append(Finding(
                        type="use_after_free",
                        category="security",
                        severity="high",
                        line=ln_no,
                        description=f"Variable '{var}' dereferenced at line {ln_no} after deallocation at line {free_line}.",
                        cwe_id="CWE-416",
                        recommendation=f"Set '{var} = NULL/nullptr' immediately after deallocation.",
                        confidence=0.9,
                        source_tool="rule",
                        status="confirmed",
                        is_confirmed=True,
                    ).to_dict())
                    break

        return findings

    # ── Layer 2: Heuristic scan ────────────────────────────────────────────────

    def _heuristic_scan(self, code: str) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
        findings: List[Dict[str, Any]] = []
        scores: Dict[str, float] = {}

        if not code.strip():
            return findings, scores

        h1 = self._h_taint_flow(code)
        scores["taint_flow"] = h1
        if h1 >= 0.5:
            findings.append(Finding(
                type="taint_flow_risk",
                category="security",
                severity="high" if h1 >= 0.8 else "medium",
                description="User input flows into buffer write without apparent size check.",
                cwe_id="CWE-120",
                recommendation="Validate input length before copying into fixed buffers.",
                confidence=h1,
                source_tool="heuristic",
                status="suspicious",
            ).to_dict())

        h2 = self._h_unchecked_malloc(code)
        scores["unchecked_malloc"] = h2
        if h2 >= 0.6:
            findings.append(Finding(
                type="unchecked_malloc",
                category="security",
                severity="medium",
                description="malloc/calloc return value not checked for NULL before use.",
                cwe_id="CWE-476",
                recommendation="Always check: if (!ptr) { /* handle error */ }",
                confidence=h2,
                source_tool="heuristic",
                status="potential",
            ).to_dict())

        h3 = self._h_signed_unsigned(code)
        scores["signed_unsigned_mismatch"] = h3
        if h3 >= 0.6:
            findings.append(Finding(
                type="signed_unsigned_mismatch",
                category="security",
                severity="medium",
                description="Signed integer used as array index or malloc size expression.",
                cwe_id="CWE-195",
                recommendation="Use size_t or unsigned types for sizes and array indices.",
                confidence=h3,
                source_tool="heuristic",
                status="potential",
            ).to_dict())

        h4, h4_line = self._h_int_overflow_malloc(code)
        scores["int_overflow_malloc"] = h4
        if h4 >= 0.7:
            findings.append(Finding(
                type="integer_overflow_malloc",
                category="security",
                severity="high",
                line=h4_line,
                description="malloc() called with multiplication expression — may overflow before allocation (CWE-190).",
                cwe_id="CWE-190",
                recommendation="Check multiplication bounds before calling malloc().",
                confidence=h4,
                source_tool="heuristic",
                status="potential",
            ).to_dict())

        h5, h5_line = self._h_buffer_loop_write(code)
        scores["unbounded_loop_write"] = h5
        if h5 >= 0.7:
            findings.append(Finding(
                type="unbounded_loop_write",
                category="security",
                severity="high",
                line=h5_line,
                description="Buffer write in loop bounded by variable without apparent size guard (CWE-120).",
                cwe_id="CWE-120",
                recommendation="Ensure loop termination bound does not exceed buffer capacity.",
                confidence=h5,
                source_tool="heuristic",
                status="potential",
            ).to_dict())

        return findings, scores

    def _h_taint_flow(self, code: str) -> float:
        input_sources = [r"\bscanf\b", r"\bfgets\b", r"\bread\b", r"\bargv\[", r"\bcin\b"]
        sink_fns = [r"\bstrcpy\b", r"\bstrcat\b", r"\bsprintf\b", r"\bmemcpy\b"]
        has_src = any(re.search(p, code) for p in input_sources)
        has_sink = any(re.search(p, code) for p in sink_fns)
        if not (has_src and has_sink):
            return 0.0
        has_len_check = bool(re.search(
            r"if\s*\([^)]*(?:strlen|sizeof|length|\bcount\b|max_len)[^)]*[><=]", code
        ))
        return 0.5 if has_len_check else 0.85

    def _h_unchecked_malloc(self, code: str) -> float:
        alloc_vars = set(re.findall(r"(\w+)\s*=\s*(?:\([^)]*\)\s*)?malloc\s*\(", code))
        if not alloc_vars:
            return 0.0
        all_checked = all(
            re.search(rf"if\s*\(\s*!?\s*{re.escape(var)}\b", code)
            or re.search(rf"assert\s*\(\s*{re.escape(var)}\b", code)
            for var in alloc_vars
        )
        return 0.0 if all_checked else 0.75

    def _h_signed_unsigned(self, code: str) -> float:
        lines = code.splitlines()
        for i, line in enumerate(lines):
            if re.search(r"\bint\s+(\w+)\s*;", line):
                var = re.search(r"\bint\s+(\w+)\s*;", line).group(1)
                subsequent = "\n".join(lines[i + 1: i + 20])
                if re.search(rf"\b\w+\[\s*{re.escape(var)}\s*\]", subsequent) or \
                   re.search(rf"\bmalloc\s*\([^)]*\b{re.escape(var)}\b", subsequent):
                    return 0.7
        return 0.0

    def _h_int_overflow_malloc(self, code: str) -> Tuple[float, Optional[int]]:
        pattern = re.compile(r"\bmalloc\s*\(\s*(\w+)\s*\*\s*(\w+)\s*\)")
        for m in pattern.finditer(code):
            ln = code[: m.start()].count("\n") + 1
            preceding = code[: m.start()][-500:]
            has_guard = bool(re.search(
                r"if\s*\([^)]*>\s*(?:SIZE_MAX|INT_MAX|UINT_MAX)", preceding
            ))
            if not has_guard:
                return 0.85, ln
        return 0.0, None

    def _h_buffer_loop_write(self, code: str) -> Tuple[float, Optional[int]]:
        buf_match = re.search(r"\b(?:char|int|short|long|uint8_t|int8_t)\s+(\w+)\s*\[\s*(\d+)\s*\]", code)
        if buf_match:
            buf_name = buf_match.group(1)
            loop_match = re.search(r"for\s*\([^;]*;\s*(\w+)\s*<\s*([a-zA-Z_]\w*)\s*;", code)
            if loop_match:
                idx_var = loop_match.group(1)
                if re.search(rf"\b{re.escape(buf_name)}\s*\[\s*{re.escape(idx_var)}\s*\]\s*=", code):
                    ln = code[: loop_match.start()].count("\n") + 1
                    return 0.85, ln
        return 0.0, None

    # ── Layer 4: LLM scan ─────────────────────────────────────────────────────

    def _llm_scan(
        self,
        optimized_code: str,
        original_code: str,
        baseline_types: List[str],
        tool_findings: List[Dict[str, Any]],
        tool_statuses: Dict[str, str],
    ) -> Tuple[List[Dict[str, Any]], List[str], str, float]:
        if not self._is_llm_ready():
            return [], ["LLM is offline; security audit based on conventional tools and rules."], "LLM skipped.", 0.0

        prompt = SecurityPromptTemplate.build(
            optimized_code=optimized_code,
            original_code=original_code,
            baseline_types=baseline_types,
            tool_findings=tool_findings,
            tool_statuses=tool_statuses,
        )

        raw, meta = self._call_llm(prompt, system_prompt=SecurityPromptTemplate.SYSTEM)
        if not meta.get("is_genuine") or self._is_stub(raw):
            return [], ["LLM returned synthetic stub or connection failed."], "LLM analysis skipped.", 0.0

        cot = self.cot_val.validate(raw)
        if cot.is_valid:
            normalized_findings = []
            for f in cot.findings:
                f_norm = Finding(
                    type=f.get("type", "llm_security_risk"),
                    category="security",
                    description=f.get("description", ""),
                    line=f.get("line"),
                    severity=f.get("severity", "medium").lower(),
                    confidence=min(0.70, cot.confidence),
                    source_tool="llm",
                    recommendation=f.get("recommendation", "Review code logic."),
                    cwe_id=f.get("cwe_id"),
                    status="potential",
                ).to_dict()
                normalized_findings.append(f_norm)
            return normalized_findings, cot.reasoning_steps, cot.conclusion, cot.confidence

        return [], ["LLM security response invalid JSON."], "LLM analysis failed.", 0.0

    # ── Comparison Helpers ────────────────────────────────────────────────────

    def _find_new_vulnerabilities(
        self, orig_findings: List[Dict[str, Any]], opt_findings: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        orig_types = {f.get("type") for f in orig_findings if f.get("type")}
        return [f for f in opt_findings if f.get("type") not in orig_types]

    def _partition_resolved(
        self, orig_findings: List[Dict[str, Any]], opt_findings: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        opt_types = {f.get("type") for f in opt_findings if f.get("type")}
        resolved = []
        unresolved = []
        for f in orig_findings:
            if f.get("type") in opt_types:
                unresolved.append(f)
            else:
                resolved.append(f)
        return resolved, unresolved

    def _compute_risk(self, findings: List[Dict[str, Any]]) -> str:
        if not findings:
            return "none"
        sevs = [f.get("severity", "low").lower() for f in findings]
        if "critical" in sevs:
            return "critical"
        if "high" in sevs:
            return "critical" if sevs.count("high") >= 3 else "high"
        if "medium" in sevs:
            return "medium"
        return "low"

    def _build_summary(
        self,
        file_path: str,
        all_vulns: List[Dict[str, Any]],
        new_vulns: List[Dict[str, Any]],
        risk: str,
        status: str,
        final_score: Optional[int],
        initial_score: Optional[int],
        score_change: Optional[int],
        completeness: str,
    ) -> str:
        high = sum(1 for v in all_vulns if v.get("severity") in ("high", "critical"))
        med = sum(1 for v in all_vulns if v.get("severity") == "medium")
        low = sum(1 for v in all_vulns if v.get("severity") in ("low", "info"))

        score_line = f"Score: {final_score}/100" if final_score is not None else "Score: N/A (LLM offline)"
        if score_change is not None:
            sign = "+" if score_change > 0 else ""
            score_line += f" (Change: {sign}{score_change} from initial {initial_score}/100)"

        lines = [
            f"Security Report: {file_path}",
            f"Overall Status: {status} | Final {score_line} | Completeness: {completeness}",
            f"Overall Risk  : {risk.upper()}",
            f"Vulnerabilities: {len(all_vulns)} (High/Crit: {high}, Med: {med}, Low: {low})",
            f"New Flaws     : {len(new_vulns)} introduced by optimization",
        ]
        if new_vulns:
            lines.append("Newly introduced vulnerabilities:")
            for v in new_vulns:
                ln = f" [line {v['line']}]" if v.get("line") else ""
                cwe = f" {v['cwe_id']}" if v.get("cwe_id") else ""
                lines.append(f"  ! [{v.get('severity','?').upper()}]{ln}{cwe} {v.get('type')}: {v.get('description')}")
        return "\n".join(lines)
