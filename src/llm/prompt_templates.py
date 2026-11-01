"""
Prompt Templates for AI-Driven Compiler Optimization System.

Includes templates for:
  - AnalysisPromptTemplate (hybrid conventional + LLM reasoning)
  - SecurityScoringPromptTemplate (0-100 rubric-based security scoring)
  - OptimizationPromptTemplate (evidence-driven, correctness/security-constrained code generation)
  - VerificationPromptTemplate (multi-layer equivalence and regression verification)
  - SecurityAuditPromptTemplate (final candidate security assessment and comparison)
"""

import json
from typing import Any, Dict, List, Optional


class AnalysisPromptTemplate:
    """Template for the Analysis Agent to correlate conventional findings and reason about root causes."""

    SYSTEM = (
        "You are an expert C/C++ compiler and security analysis specialist. "
        "You analyze source code alongside conventional static/dynamic tool diagnostics. "
        "Correlate findings, explain likely root causes, detect higher-level patterns, "
        "and distinguish confirmed tool evidence from your own additional hypotheses. "
        "Do NOT invent fabricated compiler diagnostics or claim a missing tool succeeded. "
        "Always respond ONLY with a single JSON object."
    )

    @staticmethod
    def build(
        source_code: str,
        file_path: str = "",
        parse_summary: str = "",
        tool_findings: Optional[List[Dict[str, Any]]] = None,
        tool_statuses: Optional[Dict[str, str]] = None,
    ) -> str:
        parts = [
            f"Analyze the following C/C++ code. Correlate conventional tool findings, identify relationships,\n"
            f"explain likely root causes, and prioritize issues.\n\n"
        ]
        if file_path:
            parts.append(f"Target File: {file_path}\n")
        if parse_summary:
            parts.append(f"Code Structure Summary:\n{parse_summary}\n\n")

        if tool_statuses:
            parts.append("Conventional Tool Execution Statuses:\n")
            for tool, status in tool_statuses.items():
                parts.append(f"  - {tool}: {status}\n")
            parts.append("\n")

        if tool_findings:
            parts.append("Structured Findings from Conventional Tools:\n")
            for f in tool_findings[:15]:
                sev = f.get("severity", "medium").upper()
                tool = f.get("source_tool", "tool")
                ln = f"line {f['line']}: " if f.get("line") else ""
                parts.append(f"  - [{sev}] ({tool}) {ln}{f.get('description', '')}\n")
            parts.append("\n")

        parts.append(f"Source Code:\n```cpp\n{source_code}\n```\n\n")
        parts.append(
            "Respond ONLY with a JSON object in this exact schema:\n"
            "```json\n"
            "{\n"
            '  "reasoning_steps": ["<step 1>", "<step 2>", ...],\n'
            '  "findings": [\n'
            '    {\n'
            '      "type": "<defect_type>",\n'
            '      "description": "<root cause and impact>",\n'
            '      "line": <line_number_or_null>,\n'
            '      "severity": "<critical|high|medium|low>",\n'
            '      "category": "<correctness|security|performance|quality>",\n'
            '      "is_hypothesis": <true_if_llm_hypothesis_false_if_tool_confirmed>,\n'
            '      "recommendation": "<suggested action>"\n'
            '    }\n'
            '  ],\n'
            '  "conclusion": "<concise summary of code health and key risks>",\n'
            '  "confidence": <0.0-1.0>\n'
            "}\n"
            "```"
        )
        return "".join(parts)


class SecurityScoringPromptTemplate:
    """Template for generating a truthful 0-100 security score using a defined rubric."""

    SYSTEM = (
        "You are a senior application security engineer evaluating C/C++ code. "
        "Score the security of the provided code on an integer scale from 0 to 100 based strictly on "
        "evidence and the defined rubric. A score of 100 is NEVER proof of absolute security. "
        "Do not simply count warnings; evaluate severity, exploitability, and tool completeness. "
        "Always respond ONLY with a single JSON object."
    )

    RUBRIC = """
Security Scoring Rubric (0 to 100):
- 90-100: Clean code with defensive coding, bounds checks, safe APIs, zero detected memory safety or UB defects.
- 75-89: Minor code quality or non-exploitable warnings; no memory corruption, bounds errors, or injection risks.
- 50-74: Medium-severity risks (e.g. potential unvalidated input, unchecked arithmetic, deprecated functions without direct exploit).
- 25-49: High-severity defects present (e.g. stack/heap buffer overflow, format string vulnerability, use-after-free, uninitialized variable in critical path).
- 0-24: Critical remote code execution, arbitrary memory overwrite, or multiple severe security defects.
Note: Small numbers of critical defects warrant drastic score reductions. Take tool availability and skipped checks into account.
"""

    @staticmethod
    def build(
        source_code: str,
        findings: List[Dict[str, Any]],
        tool_statuses: Dict[str, str],
        code_label: str = "original",
        unresolved_findings: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        parts = [
            f"Evaluate the security posture of the {code_label} C/C++ code and assign a security score (0-100).\n",
            SecurityScoringPromptTemplate.RUBRIC,
            "\nAnalysis Context:\n",
        ]
        parts.append(f"Tool statuses: {json.dumps(tool_statuses)}\n")
        parts.append(f"Total findings identified: {len(findings)}\n")
        for f in findings[:20]:
            sev = f.get("severity", "medium").upper()
            tool = f.get("source_tool", "scanner")
            cwe = f" ({f['cwe_id']})" if f.get("cwe_id") else ""
            parts.append(f"  - [{sev}] [{tool}]{cwe} {f.get('description')}\n")

        if unresolved_findings:
            parts.append(f"\nUnresolved high/critical findings: {len(unresolved_findings)}\n")
            for uf in unresolved_findings:
                parts.append(f"  - [UNRESOLVED] {uf.get('description')}\n")

        parts.append(f"\nSource Code:\n```cpp\n{source_code}\n```\n\n")
        parts.append(
            "Respond ONLY with a JSON object in this exact schema:\n"
            "```json\n"
            "{\n"
            '  "security_score": <integer 0-100>,\n'
            '  "score_rationale": "<thorough explanation of score based on rubric>",\n'
            '  "score_confidence": <float 0.0-1.0>,\n'
            '  "assessment_completeness": "<full|partial - static only|partial - tools unavailable>",\n'
            '  "unresolved_high_severity_findings": ["<description>", ...],\n'
            '  "assessment_limitations": ["<e.g. dynamic sanitizer unavailable>", ...]\n'
            "}\n"
            "```"
        )
        return "".join(parts)


class OptimizationPromptTemplate:
    """Template for evidence-driven code generation respecting correctness and security constraints."""

    SYSTEM = (
        "You are an expert C/C++ compiler optimization and secure coding specialist. "
        "Given source code, analysis reports, and verification feedback, produce a corrected and optimized candidate. "
        "Strict Requirements:\n"
        "1. Correctness: Preserve intended semantics and functional equivalence. Never break defined behavior.\n"
        "2. Security: Ensure memory safety, add bounds checks, initialize variables, prevent overflows.\n"
        "3. Prioritization: 1. Correctness defects -> 2. Security vulnerabilities -> 3. Performance -> 4. Quality.\n"
        "4. Controlled Changes: Make only minimal necessary transformations. Do not rewrite unrelated code.\n"
        "5. Honesty: Do not claim an issue is resolved without making a relevant code change.\n"
        "Always respond ONLY with a single JSON object."
    )

    @staticmethod
    def build(
        source_code: str,
        analysis_report: Optional[Dict[str, Any]] = None,
        iteration: int = 1,
        feedback: Optional[Dict[str, Any]] = None,
        previous_attempts: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        if analysis_report is None:
            analysis_report = {}
        findings_list = (
            analysis_report.get("all_findings")
            or analysis_report.get("findings")
            or analysis_report.get("rule_findings")
            or []
        )
        findings_text = ""
        for f in findings_list:
            findings_text += (
                f"\n  - [{f.get('severity','?').upper()}] ({f.get('source_tool','scanner')}) "
                f"{f.get('type','unknown')}: {f.get('description','')}"
                + (f" (line {f['line']})" if f.get('line') else "")
            )
        if not findings_text:
            findings_text = "\n  - No specific findings from analysis agent."

        parts = [
            f"Optimize and fix the following C/C++ code (Attempt {iteration}/3).\n\n",
            f"Initial Analysis Findings:{findings_text}\n\n",
        ]

        if feedback:
            parts.append("VERIFICATION FEEDBACK FROM PREVIOUS ATTEMPT:\n")
            if feedback.get("failed_layers"):
                parts.append(f"Failed verification layers: {', '.join(feedback['failed_layers'])}\n")
            if feedback.get("diagnostics"):
                parts.append(f"Diagnostics / Errors:\n{feedback['diagnostics']}\n")
            if feedback.get("unresolved_findings"):
                parts.append("Still Unresolved Findings:\n")
                for uf in feedback["unresolved_findings"]:
                    parts.append(f"  - {uf.get('description', '')}\n")
            if feedback.get("new_findings"):
                parts.append("NEW Issues Introduced by Previous Attempt:\n")
                for nf in feedback["new_findings"]:
                    parts.append(f"  - {nf.get('description', '')}\n")
            parts.append("\n")

        if previous_attempts and iteration > 1:
            parts.append(f"History: {len(previous_attempts)} previous attempt(s) were rejected by verification.\n\n")

        parts.append(f"Original Code:\n```cpp\n{source_code}\n```\n\n")
        parts.append(
            "Respond ONLY with a JSON object in this exact schema:\n"
            "```json\n"
            "{\n"
            '  "reasoning_steps": ["<step 1>", "<step 2>", ...],\n'
            '  "transformations": [\n'
            '    {\n'
            '      "type": "<transformation_name>",\n'
            '      "description": "<exact change made and why>",\n'
            '      "related_finding": "<id or description of finding addressed>",\n'
            '      "line": <line_number_or_null>\n'
            '    }\n'
            '  ],\n'
            '  "optimized_code": "<complete, compilable, corrected C/C++ source code as a single string>",\n'
            '  "justification": "<why these transformations improve performance and safety>",\n'
            '  "expected_benefits": "<expected performance or correctness gain>",\n'
            '  "security_considerations": "<how memory safety and bounds are maintained>",\n'
            '  "behavior_preservation_claim": "<why intended program behavior is preserved>",\n'
            '  "assumptions": ["<assumptions made>", ...],\n'
            '  "unresolved_issues": ["<any known issues left unaddressed>", ...],\n'
            '  "conclusion": "<summary of optimization>",\n'
            '  "confidence": <float 0.0-1.0>\n'
            "}\n"
            "```"
        )
        return "".join(parts)


class VerificationPromptTemplate:
    """Template for Layer 4 LLM semantic equivalence and safety verification."""

    SYSTEM = (
        "You are a formal verification and program equivalence specialist for C/C++. "
        "Independently assess whether the optimized candidate preserves the user's intended behavior, "
        "fixes the target findings, and avoids regressions. "
        "Do NOT claim equivalence if differential testing or Z3 failed. "
        "Verdict must strictly be EQUIVALENT, NOT_EQUIVALENT, or UNCERTAIN. "
        "Always respond ONLY with a single JSON object."
    )

    @staticmethod
    def build(
        original_code: str,
        optimized_code: str,
        diff_test_passed: Optional[bool] = None,
        z3_status: str = "N/A",
        perf_summary: str = "",
        analysis_findings: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        diff_str = "PASSED" if diff_test_passed is True else "FAILED" if diff_test_passed is False else "SKIPPED/UNAVAILABLE"
        parts = [
            "Assess whether the candidate code is behaviorally equivalent and preserves intended semantics.\n\n",
            "Verification Layer Diagnostics:\n",
            f"  - Layer 1 (Differential Test): {diff_str}\n",
            f"  - Layer 2 (Z3 Formal Solver): {z3_status}\n",
            f"  - Layer 3 (Performance): {perf_summary or 'Not benchmarked'}\n\n",
        ]

        if analysis_findings:
            parts.append("Original Findings to Resolve:\n")
            for f in analysis_findings[:10]:
                parts.append(f"  - {f.get('description', '')}\n")
            parts.append("\n")

        parts.append(f"Original Code:\n```cpp\n{original_code}\n```\n\n")
        parts.append(f"Candidate Code:\n```cpp\n{optimized_code}\n```\n\n")
        parts.append(
            "Respond ONLY with a JSON object in this exact schema:\n"
            "```json\n"
            "{\n"
            '  "reasoning_steps": ["<step 1>", "<step 2>", ...],\n'
            '  "verdict": "<EQUIVALENT|NOT_EQUIVALENT|UNCERTAIN>",\n'
            '  "equivalence_evidence": "<detailed rationale>",\n'
            '  "resolved_findings": ["<finding descriptions that were fixed>", ...],\n'
            '  "unresolved_findings": ["<finding descriptions that remain>", ...],\n'
            '  "new_issues_detected": ["<any regressions or new bugs>", ...],\n'
            '  "conclusion": "<summary verdict>",\n'
            '  "confidence": <float 0.0-1.0>\n'
            "}\n"
            "```"
        )
        return "".join(parts)


class SecurityPromptTemplate:
    """Template for the Security Agent's final security assessment and score generation."""

    SYSTEM = (
        "You are an application security specialist conducting a final security audit on optimized C/C++ code. "
        "Assess remaining vulnerabilities, newly introduced flaws, tool findings, and assign a final security score (0-100). "
        "A score of 100 is not proof of absolute security. Always respond ONLY with a single JSON object."
    )

    @staticmethod
    def build(
        optimized_code: str,
        original_code: str = "",
        baseline_types: Optional[List[str]] = None,
        tool_findings: Optional[List[Dict[str, Any]]] = None,
        tool_statuses: Optional[Dict[str, str]] = None,
        unresolved_findings: Optional[List[Dict[str, Any]]] = None,
        initial_score: Optional[int] = None,
    ) -> str:
        parts = [
            "Perform a final security assessment of the candidate code.\n\n",
        ]
        if initial_score is not None:
            parts.append(f"Initial Security Score for Original Code: {initial_score}/100\n")

        if tool_statuses:
            parts.append(f"Conventional Tool Execution Statuses: {json.dumps(tool_statuses)}\n")

        if baseline_types:
            parts.append(f"Known baseline vulnerability types in original code (ALREADY present, do not flag as new): {baseline_types}\n")

        if tool_findings:
            parts.append(f"Conventional tool findings on candidate: {len(tool_findings)}\n")
            for f in tool_findings[:15]:
                sev = f.get("severity", "medium").upper()
                tool = f.get("source_tool", "scanner")
                parts.append(f"  - [{sev}] ({tool}) {f.get('description', '')}\n")

        if unresolved_findings:
            parts.append(f"Original findings that were NOT resolved: {len(unresolved_findings)}\n")
            for uf in unresolved_findings:
                parts.append(f"  - {uf.get('description', '')}\n")

        parts.append(f"\nFinal Candidate Code:\n```cpp\n{optimized_code}\n```\n\n")
        parts.append(
            "Respond ONLY with a JSON object in this exact schema:\n"
            "```json\n"
            "{\n"
            '  "reasoning_steps": ["<step 1>", "<step 2>", ...],\n'
            '  "findings": [\n'
            '    {"type": "<type>", "description": "<desc>", "line": <line_or_null>, "severity": "<critical|high|medium|low>"}\n'
            '  ],\n'
            '  "all_vulnerabilities": [\n'
            '    {"type": "<type>", "description": "<desc>", "line": <line_or_null>, "severity": "<critical|high|medium|low>"}\n'
            '  ],\n'
            '  "new_vulnerabilities": [\n'
            '    {"type": "<type>", "description": "<desc>", "line": <line_or_null>, "severity": "<critical|high|medium|low>"}\n'
            '  ],\n'
            '  "resolved_findings": ["<fixed finding>", ...],\n'
            '  "unresolved_findings": ["<remaining finding>", ...],\n'
            '  "overall_risk": "<critical|high|medium|low|none>",\n'
            '  "conclusion": "<security evaluation conclusion>",\n'
            '  "confidence": <float 0.0-1.0>,\n'
            '  "security_score": <integer 0-100>,\n'
            '  "score_rationale": "<rubric-based explanation>",\n'
            '  "score_confidence": <float 0.0-1.0>,\n'
            '  "assessment_completeness": "<full|partial>",\n'
            '  "llm_reasoning": ["<step 1>", "<step 2>", ...],\n'
            '  "assessment_limitations": ["<limitations>", ...],\n'
            '  "summary": "<comprehensive security summary>"\n'
            "}\n"
            "```"
        )
        return "".join(parts)
