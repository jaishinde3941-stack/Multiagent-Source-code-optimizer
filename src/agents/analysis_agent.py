"""
Analysis Agent — Hybrid Conventional Analysis and LLM Reasoning.

Upgrades:
  1. Conventional tool suite integration (Clang/Clang++, Clang-Tidy, Cppcheck, ASan, UBSan)
  2. Concurrent static analysis execution
  3. Truthful tool statuses (PASSED, FINDINGS, FAILED, UNAVAILABLE, SKIPPED, INCONCLUSIVE)
  4. Normalized finding schema with conservative deduplication and provenance preservation
  5. LLM reasoning over consolidated evidence (never mistaking stubs for genuine reasoning)
  6. Rubric-based initial security scoring (0-100) via local LLM with range validation
  7. Graceful degradation when tools or LLM are offline
"""

import json
import logging
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

_root = os.path.join(os.path.dirname(__file__), "..", "..")
if _root not in sys.path:
    sys.path.insert(0, _root)

from agent_framework import BaseAgent, ContextManager
from src.analysis.finding_schema import Finding, deduplicate_findings, normalize_finding
from src.analysis.tool_runner import ToolRunner, ToolStatus, ToolExecutionResult
from src.llm.llm_client import LLMClient
from src.llm.prompt_templates import AnalysisPromptTemplate, SecurityScoringPromptTemplate
from src.parser.code_parser import CodeParser
from src.reasoning.cot_validator import CoTValidator

logger = logging.getLogger(__name__)


class AnalysisAgent(BaseAgent):
    """
    Hybrid Analysis Agent combining compiler diagnostics, static analysis,
    runtime sanitizers, and LLM reasoning.
    """

    def __init__(
        self,
        agent_id: str,
        context_manager: ContextManager,
        llm_client: Optional[LLMClient] = None,
        tool_runner: Optional[ToolRunner] = None,
    ):
        super().__init__(agent_id, "analysis", context_manager)
        self.llm = llm_client or LLMClient()
        self.parser = CodeParser()
        self.cot_val = CoTValidator()
        self.tool_runner = tool_runner or ToolRunner()

    def get_capabilities(self) -> List[str]:
        return [
            "uninitialized_variable_detection",
            "buffer_overflow_detection",
            "nested_loop_detection",
            "memory_leak_detection",
            "division_by_zero_detection",
            "clang_compiler_diagnostics",
            "clang_tidy_static_analysis",
            "cppcheck_static_analysis",
            "asan_ubsan_runtime_instrumentation",
            "llm_severity_classification",
            "hybrid_evidence_correlation",
            "rubric_security_scoring",
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
                return bool(is_stub_fn(text))
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
        """Main entry point for analyzing source code."""
        source_code = input_data.get("source_code") or input_data.get("code") or ""
        file_path = input_data.get("file_path", "<unknown>")
        compilation_database_dir = input_data.get("compilation_database_dir")
        test_inputs = input_data.get("test_inputs")

        if not source_code:
            logger.error("AnalysisAgent: no source_code provided")
            return {
                "error": "No source_code provided",
                "source_code": "",
                "all_findings": [],
                "file_path": file_path,
                "tool_statuses": {},
                "security_score": None,
            }

        logger.info(f"AnalysisAgent: analyzing '{os.path.basename(file_path)}' ({len(source_code)} chars)")

        # ── 1. Code Parsing ───────────────────────────────────────────────────
        parse_result = self.parser.parse_string(source_code, file_path)

        # ── 2. Rule-based checks (built-in, always available) ─────────────────
        rule_findings = self._rule_based_analysis(parse_result, source_code)

        # ── 3. Conventional tools (Clang, Clang-Tidy, Cppcheck, ASan, UBSan) ──
        tool_results = self.tool_runner.run_all_tools_concurrently(
            source_code=source_code,
            file_path=file_path,
            compilation_database_dir=compilation_database_dir,
            test_inputs=test_inputs,
        )

        tool_statuses: Dict[str, str] = {}
        raw_diagnostics: Dict[str, str] = {}
        tool_findings: List[Dict[str, Any]] = []
        assessment_limitations: List[str] = []

        for tname, tres in tool_results.items():
            tool_statuses[tname] = tres.status
            if tres.raw_output:
                raw_diagnostics[tname] = tres.raw_output[:2000]
            if tres.findings:
                tool_findings.extend(tres.findings)
            if tres.limitations:
                assessment_limitations.extend(tres.limitations)
            if tres.status == ToolStatus.UNAVAILABLE:
                assessment_limitations.append(f"{tname} is unavailable on the host system.")

        # ── 4. LLM reasoning over consolidated evidence ───────────────────────
        llm_findings, reasoning_steps, conclusion, confidence = self._llm_analysis(
            source_code=source_code,
            file_path=file_path,
            parse_result=parse_result,
            rule_findings=rule_findings,
            tool_findings=tool_findings,
            tool_statuses=tool_statuses,
            assessment_limitations=assessment_limitations,
        )

        # ── 5. Merge and deduplicate findings conservatively ─────────────────
        raw_all = list(rule_findings) + list(tool_findings) + list(llm_findings)
        all_findings, dedup_summary = deduplicate_findings(raw_all)

        # ── 6. Initial Security Score (0 to 100) ──────────────────────────────
        security_score, score_rationale, score_conf, completeness, extra_limits = self._generate_security_score(
            source_code=source_code,
            all_findings=all_findings,
            tool_statuses=tool_statuses,
            assessment_limitations=assessment_limitations,
        )
        if extra_limits:
            assessment_limitations.extend(extra_limits)
        assessment_limitations = list(dict.fromkeys(assessment_limitations))

        # ── 7. Build consolidated result ──────────────────────────────────────
        summary_text = self._build_summary(
            file_path=file_path,
            findings=all_findings,
            conclusion=conclusion,
            tool_statuses=tool_statuses,
            security_score=security_score,
            completeness=completeness,
        )

        # Findings by category and overall risk
        findings_by_cat: Dict[str, List[Dict[str, Any]]] = {}
        for f in all_findings:
            cat = f.get("category", "correctness")
            findings_by_cat.setdefault(cat, []).append(f)

        risk_val = "none"
        if any(f.get("severity") in ("critical", "high") for f in all_findings):
            risk_val = "high"
        elif any(f.get("severity") == "medium" for f in all_findings):
            risk_val = "medium"
        elif all_findings:
            risk_val = "low"

        result = {
            "file_path": file_path,
            "source_code": source_code,
            "tool_statuses": tool_statuses,
            "raw_tool_diagnostics": raw_diagnostics,
            "rule_findings": rule_findings,
            "tool_findings": tool_findings,
            "llm_findings": llm_findings,
            "llm_hypotheses": [f for f in llm_findings if f.get("execution_context", {}).get("is_hypothesis")],
            "all_findings": all_findings,
            "findings_by_category": findings_by_cat,
            "deduplication_summary": dedup_summary,
            "reasoning_steps": reasoning_steps,
            "llm_reasoning": reasoning_steps,
            "conclusion": conclusion,
            "confidence": confidence,
            "security_score": security_score,
            "score_rationale": score_rationale,
            "score_confidence": score_conf,
            "assessment_completeness": completeness,
            "assessment_limitations": assessment_limitations,
            "overall_risk": risk_val,
            "summary": summary_text,
            "parse_meta": {
                "line_count": parse_result.line_count,
                "functions": [f.name for f in parse_result.functions],
                "has_nested_loops": parse_result.has_nested_loops,
                "max_loop_depth": parse_result.max_loop_depth,
            },
        }

        # Store in shared context using both canonical and legacy keys
        self.context.set("initial_analysis_report", result)
        self.context.set("analysis_results", result)
        self.context.set("original_code", source_code)
        self.context.set("source_file", file_path)
        self.context.set("initial_security_score", security_score)

        logger.info(
            f"Analysis complete: {len(all_findings)} findings in {file_path} "
            f"(Score: {security_score if security_score is not None else 'N/A'}/100)"
        )
        return result

    # ── Rule-based analysis ───────────────────────────────────────────────────

    def _rule_based_analysis(self, parse_result, source_code: str) -> List[Dict[str, Any]]:
        findings = []

        # Uninitialized variables
        for v in parse_result.uninitialized_vars:
            findings.append(Finding(
                type="uninitialized_variable",
                category="correctness",
                description=f"Variable '{v['variable']}' declared at line {v['declared_line']} may be used before initialization.",
                line=v["declared_line"],
                severity="high",
                confidence=0.85,
                source_tool="rule",
                status="potential",
                recommendation=f"Initialize variable '{v['variable']}' upon declaration.",
            ).to_dict())

        # Array accesses with variable index
        if parse_result.has_nested_loops or parse_result.loops:
            for acc in parse_result.array_accesses:
                if acc.get("is_var_index"):
                    findings.append(Finding(
                        type="potential_buffer_overflow",
                        category="security",
                        description=f"Array '{acc['array']}' accessed with variable index '{acc['index']}' at line {acc['line']}. Verify bounds checking.",
                        line=acc["line"],
                        severity="high",
                        confidence=0.80,
                        source_tool="rule",
                        cwe_id="CWE-119",
                        status="suspicious",
                        recommendation="Enforce explicit array bounds validation.",
                    ).to_dict())

        # Off-by-one in loop
        off_by_one = re.findall(r'for\s*\([^;]*;\s*\w+\s*<=\s*(\d+)', source_code)
        if off_by_one:
            for ln_no, ln in enumerate(source_code.splitlines(), 1):
                if re.search(r'for\s*\([^;]*;\s*\w+\s*<=\s*\d+', ln):
                    findings.append(Finding(
                        type="off_by_one_error",
                        category="security",
                        description=f"Loop at line {ln_no} uses '<=' which may cause off-by-one buffer overflow.",
                        line=ln_no,
                        severity="high",
                        confidence=0.90,
                        source_tool="rule",
                        cwe_id="CWE-193",
                        status="confirmed",
                        is_confirmed=True,
                        recommendation="Use strict inequality '<' when iterating over array bounds.",
                    ).to_dict())

        # Nested loops
        if parse_result.has_nested_loops:
            findings.append(Finding(
                type="algorithmic_inefficiency",
                category="performance",
                description="Nested loops detected (potential O(n²) complexity). Consider algorithmic optimization.",
                line=None,
                severity="medium",
                confidence=0.75,
                source_tool="rule",
                status="code_quality",
                recommendation="Evaluate whether nested loop can be flattened or indexed via hash map.",
            ).to_dict())

        # Memory leak heuristic
        if len(parse_result.malloc_calls) > len(parse_result.free_calls):
            findings.append(Finding(
                type="memory_leak",
                category="security",
                description=f"{len(parse_result.malloc_calls)} malloc call(s) but only {len(parse_result.free_calls)} free call(s) found.",
                line=parse_result.malloc_calls[0] if parse_result.malloc_calls else None,
                severity="high",
                confidence=0.85,
                source_tool="rule",
                cwe_id="CWE-401",
                status="potential",
                recommendation="Ensure every allocated pointer is safely freed before returning.",
            ).to_dict())

        # Division by zero heuristic
        _src_nc = re.sub(r'//[^\n]*', '', source_code)
        _src_nc = re.sub(r'/\*.*?\*/', '', _src_nc, flags=re.DOTALL)
        _CPP_KW = frozenset({
            'int', 'char', 'float', 'double', 'long', 'short', 'unsigned',
            'bool', 'void', 'return', 'if', 'else', 'for', 'while', 'do',
            'switch', 'case', 'break', 'continue', 'struct', 'class',
        })
        div_pattern = re.findall(r'\b\w+\s*/\s*(\w+)\b', _src_nc)
        seen_div = set()
        for var in div_pattern:
            if var in seen_div or var in _CPP_KW:
                continue
            seen_div.add(var)
            if re.search(rf'(?:^|\s){re.escape(var)}\s*=\s*0\s*;', _src_nc, re.MULTILINE):
                findings.append(Finding(
                    type="division_by_zero_risk",
                    category="correctness",
                    description=f"Variable '{var}' may be 0 when used as divisor.",
                    line=None,
                    severity="high",
                    confidence=0.85,
                    source_tool="rule",
                    cwe_id="CWE-369",
                    status="potential",
                    recommendation="Add non-zero validation check before division.",
                ).to_dict())

        return findings

    # ── LLM-based analysis ────────────────────────────────────────────────────

    def _llm_analysis(
        self,
        source_code: str,
        file_path: str,
        parse_result: Any,
        rule_findings: List[Dict[str, Any]],
        tool_findings: List[Dict[str, Any]],
        tool_statuses: Dict[str, str],
        assessment_limitations: List[str],
    ) -> Tuple[List[Dict[str, Any]], List[str], str, float]:
        """Call LLM to correlate tool findings, generate hypotheses, and produce reasoning."""
        if not self._is_llm_ready():
            assessment_limitations.append("Ollama service unavailable; LLM reasoning skipped.")
            return (
                [],
                ["Rule-based and conventional tool analysis only (Ollama unavailable)."],
                f"Conventional tools identified {len(rule_findings) + len(tool_findings)} finding(s).",
                0.65,
            )

        prompt = AnalysisPromptTemplate.build(
            source_code=source_code,
            file_path=file_path,
            parse_summary=parse_result.to_summary(),
            tool_findings=rule_findings + tool_findings,
            tool_statuses=tool_statuses,
        )

        raw, meta = self._call_llm(
            prompt,
            system_prompt=AnalysisPromptTemplate.SYSTEM,
        )

        if not meta.get("is_genuine") or self._is_stub(raw):
            assessment_limitations.append("LLM returned synthetic stub or failed.")
            return (
                [],
                ["Conventional analysis completed (LLM reasoning unavailable or stub)."],
                f"Conventional tools identified {len(rule_findings) + len(tool_findings)} finding(s).",
                0.60,
            )

        cot = self.cot_val.validate(raw)
        if not cot.is_valid:
            logger.warning(f"LLM CoT invalid: {cot.error}")
            return (
                [],
                ["LLM response invalid JSON; relying on conventional tool output."],
                f"Conventional tools identified {len(rule_findings) + len(tool_findings)} finding(s).",
                0.60,
            )

        llm_findings = []
        for raw_item in cot.findings:
            f = Finding(
                type=raw_item.get("type", "llm_hypothesis"),
                category=raw_item.get("category", "correctness"),
                description=raw_item.get("description", ""),
                line=raw_item.get("line"),
                severity=raw_item.get("severity", "medium").lower(),
                confidence=min(0.75, cot.confidence),
                source_tool="llm",
                file_path=file_path,
                recommendation=raw_item.get("recommendation", "Review code logic."),
                status="potential",
                is_confirmed=False,
                execution_context={"is_hypothesis": True},
            )
            llm_findings.append(f.to_dict())

        return llm_findings, cot.reasoning_steps, cot.conclusion, cot.confidence

    # ── Security Scoring ──────────────────────────────────────────────────────

    def _generate_security_score(
        self,
        source_code: str,
        all_findings: List[Dict[str, Any]],
        tool_statuses: Dict[str, str],
        assessment_limitations: List[str],
    ) -> Tuple[Optional[int], str, float, str, List[str]]:
        """
        Generate integer security score (0-100) using local Ollama model and rubric.
        Returns (score, rationale, confidence, completeness, extra_limitations).
        """
        if not self._is_llm_ready():
            return (
                None,
                "Security score could not be completed because Ollama LLM was unavailable.",
                0.0,
                "incomplete - conventional tools only",
                ["Ollama unavailable for security scoring; score not fabricated."],
            )

        prompt = SecurityScoringPromptTemplate.build(
            source_code=source_code,
            findings=all_findings,
            tool_statuses=tool_statuses,
            code_label="original",
        )

        raw, meta = self._call_llm(
            prompt,
            system_prompt=SecurityScoringPromptTemplate.SYSTEM,
        )

        if not meta.get("is_genuine") or self._is_stub(raw):
            return (
                None,
                "LLM-dependent assessment and security score could not be completed (Ollama stub/offline).",
                0.0,
                "partial - conventional tools only",
                ["Ollama unavailable or returned synthetic stub; score not fabricated."],
            )

        parsed = self.cot_val.extract_json(raw)
        if not parsed or "security_score" not in parsed:
            return (
                None,
                "LLM security scoring response could not be parsed as valid JSON.",
                0.0,
                "incomplete",
                ["Malformed LLM scoring output."],
            )

        try:
            score_val = int(parsed["security_score"])
            if not (0 <= score_val <= 100):
                logger.warning(f"Score {score_val} outside [0, 100] – rejecting invalid score.")
                return (
                    None,
                    f"LLM score {score_val} was outside valid range [0, 100].",
                    0.0,
                    "invalid_range",
                    ["LLM returned out-of-range security score."],
                )
        except (ValueError, TypeError):
            return (
                None,
                "LLM returned non-integer security score.",
                0.0,
                "invalid_type",
                ["Non-numeric score received from LLM."],
            )

        rationale = str(parsed.get("score_rationale", "Evidence-based rubric score."))
        conf = float(parsed.get("score_confidence", 0.8))
        completeness = str(parsed.get("assessment_completeness", "full"))
        extra_limits = [str(x) for x in parsed.get("assessment_limitations", [])]

        return score_val, rationale, conf, completeness, extra_limits

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_summary(
        self,
        file_path: str,
        findings: List[Dict[str, Any]],
        conclusion: str,
        tool_statuses: Dict[str, str],
        security_score: Optional[int],
        completeness: str,
    ) -> str:
        high = sum(1 for f in findings if f.get("severity") in ("high", "critical"))
        med = sum(1 for f in findings if f.get("severity") == "medium")
        low = sum(1 for f in findings if f.get("severity") in ("low", "info"))

        score_str = f"{security_score}/100" if security_score is not None else "N/A (Ollama offline)"
        lines = [
            f"Analysis Report: {file_path}",
            f"Security Score : {score_str} (Completeness: {completeness})",
            f"Tool Statuses  : " + ", ".join(f"{k}={v}" for k, v in tool_statuses.items()),
            f"Total Findings : {len(findings)} (High/Crit: {high}, Med: {med}, Low: {low})",
            f"Conclusion     : {conclusion}",
        ]
        for i, f in enumerate(findings[:15], 1):
            sev = f.get("severity", "?").upper()
            tool = f.get("source_tool", "tool")
            ln = f" [line {f['line']}]" if f.get("line") else ""
            lines.append(f"  {i}. [{sev}] ({tool}){ln} {f.get('type')}: {f.get('description')}")
        if len(findings) > 15:
            lines.append(f"  ... and {len(findings) - 15} more finding(s).")
        return "\n".join(lines)
