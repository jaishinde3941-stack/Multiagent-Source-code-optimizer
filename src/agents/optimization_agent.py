"""
Optimization Agent — Evidence-Driven C/C++ Code Transformation.

Upgrades:
  1. Evidence-driven optimization using full analysis reports and compiler diagnostics
  2. Bounded iterative feedback support (accepts feedback report & unresolved findings from verification)
  3. Strict prioritization: 1. Correctness -> 2. Security -> 3. Performance -> 4. Code quality
  4. Validated structured response schema with explicit claims vs verified reality
  5. Truthful fallback behavior without false success reporting
"""

import difflib
import logging
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

_root = os.path.join(os.path.dirname(__file__), "..", "..")
if _root not in sys.path:
    sys.path.insert(0, _root)

from agent_framework import BaseAgent, ContextManager
from src.llm.llm_client import LLMClient
from src.llm.prompt_templates import OptimizationPromptTemplate
from src.reasoning.cot_validator import CoTValidator

logger = logging.getLogger(__name__)

_OUTPUT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..",
    "MicroBenchmarks", "Generated_optimisation"
)


class OptimizationStatus:
    """Explicit optimization statuses as required by Section 6.5."""
    OPTIMIZATION_GENERATED = "optimization_generated"
    NO_CHANGES_GENERATED = "no_changes_generated"
    FALLBACK_ORIGINAL_CODE = "fallback_original_code"
    LLM_UNAVAILABLE = "llm_unavailable"
    INVALID_LLM_OUTPUT = "invalid_llm_output"
    CANDIDATE_GENERATED_UNVERIFIED = "candidate_generated_unverified"


class OptimizationAgent(BaseAgent):
    """
    Evidence-driven Optimization Agent that generates candidate C/C++ source code
    under correctness, security, and performance constraints.
    """

    def __init__(
        self,
        agent_id: str,
        context_manager: ContextManager,
        llm_client: Optional[LLMClient] = None,
        output_dir: str = _OUTPUT_DIR,
    ):
        super().__init__(agent_id, "optimization", context_manager)
        self.llm = llm_client or LLMClient()
        self.cot_val = CoTValidator()
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def get_capabilities(self) -> List[str]:
        return [
            "off_by_one_fix",
            "uninitialized_variable_fix",
            "loop_bound_correction",
            "algorithm_replacement_suggestion",
            "diff_generation",
            "llm_code_transformation",
            "iterative_feedback_handling",
            "prioritized_transformation",
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
        """
        Generate candidate optimization addressing analysis findings and previous verification feedback.
        """
        source_code = input_data.get("source_code") or input_data.get("code") or self.context.get("original_code", "")
        file_path = input_data.get("file_path") or self.context.get("source_file") or "<unknown>"
        analysis_report = (
            input_data.get("analysis_report")
            or self.context.get("initial_analysis_report")
            or self.context.get("analysis_results")
            or {}
        )
        iteration = input_data.get("iteration", self.context.get("iteration_count", 1) or 1)
        feedback = input_data.get("feedback")
        previous_attempts = input_data.get("previous_attempts") or self.context.get("iteration_history") or []
        unresolved_findings = input_data.get("unresolved_findings") or self.context.get("unresolved_findings") or []

        if not source_code:
            logger.error("OptimizationAgent: no source_code provided")
            return {
                "error": "No source_code provided",
                "optimization_status": OptimizationStatus.FALLBACK_ORIGINAL_CODE,
                "optimized_code": "",
                "transformations": [],
            }

        logger.info(
            f"OptimizationAgent: running attempt {iteration}/3 for '{os.path.basename(file_path)}'"
        )

        # ── 1. Call LLM for evidence-driven transformation (Ollama is sole code generator) ──
        (
            llm_code,
            llm_transforms,
            llm_metadata,
            reasoning_steps,
            conclusion,
            confidence,
            opt_status,
        ) = self._llm_optimize(
            source_code=source_code,
            analysis_report=analysis_report,
            iteration=iteration,
            feedback=feedback,
            previous_attempts=previous_attempts,
        )

        # ── 2. Select candidate code ──────────────────────────────────────────
        # Preserve original source if LLM is unavailable, returns invalid output, or unchanged code.
        # Never fall back to unvalidated regex mutations.
        if llm_code and llm_code.strip() and llm_code != source_code:
            final_code = llm_code
            all_transforms = llm_transforms
            status = OptimizationStatus.OPTIMIZATION_GENERATED
        elif llm_code == source_code:
            final_code = source_code
            all_transforms = []
            status = OptimizationStatus.NO_CHANGES_GENERATED
            conclusion = "Optimizer inspected code and generated no changes."
        else:
            final_code = source_code
            all_transforms = []
            status = opt_status or OptimizationStatus.FALLBACK_ORIGINAL_CODE
            conclusion = "LLM unavailable or failed; original code preserved without unvalidated mutation."

        # ── 4. Build unified diff ─────────────────────────────────────────────
        diff = self._make_diff(source_code, final_code, file_path)

        # ── 5. Save output file ───────────────────────────────────────────────
        output_file = self._save_output(final_code, file_path)

        result = {
            "file_path": file_path,
            "original_code": source_code,
            "optimized_code": final_code,
            "unified_diff": diff,
            "transformations": all_transforms,
            "related_findings": llm_metadata.get("related_findings", []),
            "justification": llm_metadata.get("justification", ""),
            "expected_benefits": llm_metadata.get("expected_benefits", ""),
            "security_considerations": llm_metadata.get("security_considerations", ""),
            "behavior_preservation_claim": llm_metadata.get("behavior_preservation_claim", ""),
            "assumptions": llm_metadata.get("assumptions", []),
            "unresolved_issues": llm_metadata.get("unresolved_issues", []),
            "reasoning_steps": reasoning_steps,
            "conclusion": conclusion,
            "confidence": confidence,
            "optimization_status": status,
            "status": status,
            "candidate_code": final_code,
            "diff": diff,
            "rationale": llm_metadata.get("justification", ""),
            "output_file": output_file,
            "iteration": iteration,
            "summary": self._build_summary(file_path, all_transforms, conclusion, diff, status),
        }

        # Store in shared context using canonical & backward-compatible keys
        self.context.set("optimization_results", result)
        self.context.set("optimization_suggestions", result)
        self.context.set("current_candidate", final_code)

        logger.info(
            f"Optimization attempt {iteration} complete: status={status}, "
            f"transforms={len(all_transforms)}"
        )
        return result

    # ── LLM Optimization Core ─────────────────────────────────────────────────

    def _llm_optimize(
        self,
        source_code: str,
        analysis_report: Dict[str, Any],
        iteration: int,
        feedback: Optional[Dict[str, Any]],
        previous_attempts: List[Dict[str, Any]],
    ) -> Tuple[Optional[str], List[Dict[str, Any]], Dict[str, Any], List[str], str, float, str]:
        """
        Query Ollama with structured optimization prompt and verification feedback.
        """
        if not self._is_llm_ready():
            logger.warning("OptimizationAgent: Ollama is offline – skipping LLM optimization.")
            return (
                None,
                [],
                {},
                ["LLM is unavailable; skipping LLM code generation."],
                "LLM unavailable; using rule-based fallback.",
                0.5,
                OptimizationStatus.LLM_UNAVAILABLE,
            )

        prompt = OptimizationPromptTemplate.build(
            source_code=source_code,
            analysis_report=analysis_report,
            iteration=iteration,
            feedback=feedback,
            previous_attempts=previous_attempts,
        )

        raw, meta = self._call_llm(
            prompt,
            system_prompt=OptimizationPromptTemplate.SYSTEM,
        )

        if not meta.get("is_genuine") or self._is_stub(raw):
            logger.warning("OptimizationAgent: Ollama returned synthetic stub or failed.")
            return (
                None,
                [],
                {},
                ["LLM returned synthetic stub or failed to connect."],
                "LLM unavailable or stub received; preserving original code.",
                0.5,
                OptimizationStatus.FALLBACK_ORIGINAL_CODE,
            )

        parsed = self.cot_val.extract_json(raw)
        if not parsed:
            logger.warning("OptimizationAgent: malformed JSON returned by LLM.")
            return (
                None,
                [],
                {},
                ["LLM returned malformed or unparseable JSON."],
                "LLM output could not be parsed.",
                0.0,
                OptimizationStatus.INVALID_LLM_OUTPUT,
            )

        optimized_code = parsed.get("optimized_code")
        raw_transforms = parsed.get("transformations") or parsed.get("findings") or []
        transforms: List[Dict[str, Any]] = []

        if isinstance(raw_transforms, list):
            for t in raw_transforms:
                if isinstance(t, dict):
                    transforms.append({
                        "type": t.get("type", "optimization"),
                        "description": t.get("description", ""),
                        "line": t.get("line"),
                        "severity": t.get("severity", "info"),
                        "related_finding": t.get("related_finding", ""),
                    })

        metadata = {
            "related_findings": parsed.get("related_findings", []),
            "justification": str(parsed.get("justification", "")),
            "expected_benefits": str(parsed.get("expected_benefits", "")),
            "security_considerations": str(parsed.get("security_considerations", "")),
            "behavior_preservation_claim": str(parsed.get("behavior_preservation_claim", "")),
            "assumptions": parsed.get("assumptions", []),
            "unresolved_issues": parsed.get("unresolved_issues", []),
        }

        steps = parsed.get("reasoning_steps", ["Optimization reasoning completed."])
        if not isinstance(steps, list):
            steps = [str(steps)]

        conclusion = str(parsed.get("conclusion", "Candidate generated."))
        try:
            confidence = float(parsed.get("confidence", 0.8))
        except (ValueError, TypeError):
            confidence = 0.75

        opt_status = (
            OptimizationStatus.OPTIMIZATION_GENERATED
            if optimized_code and optimized_code != source_code
            else OptimizationStatus.NO_CHANGES_GENERATED
        )

        return (
            optimized_code,
            transforms,
            metadata,
            [str(s) for s in steps],
            conclusion,
            confidence,
            opt_status,
        )

    # ── Rule-based fixes ──────────────────────────────────────────────────────

    def _rule_based_fix(
        self, src: str, analysis_report: Dict[str, Any]
    ) -> Tuple[str, List[Dict[str, Any]]]:
        code = src
        transforms: List[Dict[str, Any]] = []
        findings = (
            analysis_report.get("all_findings")
            or analysis_report.get("findings")
            or analysis_report.get("rule_findings")
            or []
        )

        for finding in findings:
            ftype = finding.get("type", "")

            # Fix off-by-one: `i <= N` -> `i < N` in for-loop conditions
            if ftype in ("off_by_one_error", "potential_buffer_overflow"):
                fixed, change = self._fix_off_by_one(code)
                if change:
                    code = fixed
                    transforms.append({
                        "type": "off_by_one_fix",
                        "description": "Changed '<=' to '<' in loop condition to prevent buffer overflow.",
                        "severity": "info",
                        "related_finding": finding.get("id", ftype),
                    })

            # Fix uninitialized variable: add = 0
            if ftype == "uninitialized_variable":
                var = self._extract_varname(finding.get("description", ""))
                if var:
                    fixed, change = self._fix_uninit_var(code, var)
                    if change:
                        code = fixed
                        transforms.append({
                            "type": "initialize_variable",
                            "description": f"Initialized variable '{var}' to 0.",
                            "severity": "info",
                            "related_finding": finding.get("id", ftype),
                        })

        return code, transforms

    def _fix_off_by_one(self, src: str) -> Tuple[str, bool]:
        """Replace `<= <integer>` in `for(...)` conditions -> `< <integer>`."""
        pattern = re.compile(
            r'(for\s*\([^;]*;\s*\w+\s*)<=(\s*\d+)',
            re.MULTILINE,
        )
        new_src, n = pattern.subn(lambda m: m.group(1) + "<" + m.group(2), src)
        return new_src, n > 0

    def _fix_uninit_var(self, src: str, varname: str) -> Tuple[str, bool]:
        """Add `= 0` to a bare variable declaration."""
        pattern = re.compile(
            r'(\b(?:int|float|double|char|long|short|unsigned|bool)\s+'
            + re.escape(varname) + r')\s*;'
        )
        new_src, n = pattern.subn(r'\g<1> = 0;', src)
        return new_src, n > 0

    def _extract_varname(self, description: str) -> Optional[str]:
        m = re.search(r"Variable '(\w+)'", description)
        return m.group(1) if m else None

    # ── Utilities ─────────────────────────────────────────────────────────────

    def _make_diff(self, original: str, optimized: str, file_path: str) -> str:
        orig_lines = original.splitlines(keepends=True)
        opt_lines = optimized.splitlines(keepends=True)
        diff = difflib.unified_diff(
            orig_lines,
            opt_lines,
            fromfile=f"original/{os.path.basename(file_path)}",
            tofile=f"optimized/{os.path.basename(file_path)}",
            lineterm="",
        )
        return "".join(diff)

    def _save_output(self, code: str, file_path: str) -> str:
        base = os.path.basename(file_path) if file_path != "<unknown>" else "output.cpp"
        out_name = "OPT_" + base
        out_path = os.path.join(self.output_dir, out_name)
        try:
            with open(out_path, "w", encoding="utf-8") as fh:
                fh.write(code)
            logger.info(f"Saved optimized code to {out_path}")
        except OSError as exc:
            logger.error(f"Could not save optimized file: {exc}")
        return out_path

    def _build_summary(
        self, file_path: str, transforms: List[Dict[str, Any]], conclusion: str, diff: str, status: str
    ) -> str:
        diff_lines = diff.count("\n+") + diff.count("\n-")
        lines = [
            f"Optimization Report: {file_path}",
            f"Status             : {status}",
            f"Transformations    : {len(transforms)}",
            f"Diff lines changed : ~{diff_lines}",
            f"Conclusion         : {conclusion}",
        ]
        for i, t in enumerate(transforms, 1):
            lines.append(f"  {i}. {t.get('type')}: {t.get('description')}")
        return "\n".join(lines)
