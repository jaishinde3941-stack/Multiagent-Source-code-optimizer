"""
Chain-of-Thought (CoT) Validator — Week 6

Parses and validates the JSON CoT output produced by the LLM.
Handles responses wrapped in markdown code fences as well as raw JSON.
"""

import json
import re
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Required CoT keys ─────────────────────────────────────────────────────────
_REQUIRED_KEYS = {"reasoning_steps", "conclusion", "confidence"}


@dataclass
class CoTResult:
    """Parsed and validated Chain-of-Thought output."""
    is_valid: bool
    reasoning_steps: List[str]
    findings: List[Dict[str, Any]]
    conclusion: str
    confidence: float
    # Optimization agent may include this
    optimized_code: Optional[str] = None
    # Verification agent may include this
    verdict: Optional[str] = None
    error: Optional[str] = None
    raw_json: Optional[Dict[str, Any]] = None


class CoTValidator:
    """
    Validates LLM Chain-of-Thought JSON output.

    Usage
    -----
    validator = CoTValidator()
    cot = validator.validate(llm_response_string)
    if cot.is_valid:
        print(cot.conclusion)
    """

    _FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)

    def validate(self, llm_output: str) -> CoTResult:
        """
        Parse and validate LLM output.

        Returns a CoTResult with is_valid=False and error message when
        the output cannot be parsed or fails validation.
        """
        raw = self._extract_json(llm_output)
        if raw is None:
            return CoTResult(
                is_valid=False,
                reasoning_steps=[],
                findings=[],
                conclusion="",
                confidence=0.0,
                error="No JSON found in LLM output.",
            )

        error = self._check_required_keys(raw)
        if error:
            return CoTResult(
                is_valid=False,
                reasoning_steps=[],
                findings=[],
                conclusion="",
                confidence=0.0,
                error=error,
                raw_json=raw,
            )

        # Validate types
        steps = raw.get("reasoning_steps", [])
        if not isinstance(steps, list) or len(steps) == 0:
            return CoTResult(
                is_valid=False,
                reasoning_steps=[],
                findings=[],
                conclusion="",
                confidence=0.0,
                error="reasoning_steps must be a non-empty list.",
                raw_json=raw,
            )

        confidence = raw.get("confidence", 0.0)
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = 0.0
        if not (0.0 <= confidence <= 1.0):
            logger.warning(f"Confidence {confidence} out of [0,1] – clamping.")
            confidence = max(0.0, min(1.0, confidence))

        conclusion = raw.get("conclusion", "")
        if not isinstance(conclusion, str):
            conclusion = str(conclusion)

        findings = raw.get("findings", [])
        if not isinstance(findings, list):
            findings = []

        return CoTResult(
            is_valid=True,
            reasoning_steps=[str(s) for s in steps],
            findings=findings,
            conclusion=conclusion,
            confidence=confidence,
            optimized_code=raw.get("optimized_code"),
            verdict=raw.get("verdict"),
            raw_json=raw,
        )

    # ── Internals ─────────────────────────────────────────────────────────────

    def extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Public helper to extract and parse JSON from a response string or code fence."""
        return self._extract_json(text)

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Try to extract JSON either from a code fence or the raw string."""
        # First try markdown fences
        for m in self._FENCE_RE.finditer(text):
            candidate = m.group(1).strip()
            parsed = self._try_parse(candidate)
            if parsed is not None:
                return parsed

        # Fallback: try the entire text as JSON
        return self._try_parse(text.strip())

    def _try_parse(self, text: str) -> Optional[Dict[str, Any]]:
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
        return None

    def _check_required_keys(self, data: Dict) -> Optional[str]:
        missing = _REQUIRED_KEYS - set(data.keys())
        if missing:
            return f"Missing required CoT keys: {missing}"
        return None
