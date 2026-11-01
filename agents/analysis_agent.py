"""
Analysis Agent - LLM-Powered Code Analysis

Uses Qwen 2.5 Coder via Ollama to detect code patterns, bugs,
complexity, and optimization opportunities in C/C++ code.
"""

import logging
from typing import Dict, Any, List

from agent_framework import BaseAgent, MessageType, MessagePriority
from llm.ollama_client import OllamaClient
from llm.prompts import ANALYSIS_PROMPT

logger = logging.getLogger(__name__)


class AnalysisAgent(BaseAgent):
    """Agent that analyzes C/C++ code using LLM"""

    def __init__(self, agent_id, agent_type, context_manager, llm_client=None):
        self._llm = llm_client or OllamaClient()
        super().__init__(agent_id, agent_type, context_manager)

    def get_capabilities(self) -> List[str]:
        return [
            "code_analysis",
            "pattern_detection",
            "complexity_analysis",
            "bug_detection",
        ]

    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze C/C++ code for patterns, bugs, and optimization opportunities.

        Args:
            input_data: {"code": str, "filename": str (optional)}

        Returns:
            Analysis results dict with complexity, patterns, issues, etc.
        """
        code = input_data.get("code", "")
        filename = input_data.get("filename", "unknown")

        if not code.strip():
            return {"error": "No code provided"}

        self.logger.info(f"Analyzing code from {filename}")

        # Try LLM-powered analysis
        try:
            prompt = ANALYSIS_PROMPT.format(code=code)
            result = self._llm.generate_json(prompt)

            # Validate required fields with defaults
            analysis = {
                "complexity": result.get("complexity", {"time": "unknown", "space": "unknown"}),
                "patterns": result.get("patterns", []),
                "issues": result.get("issues", []),
                "optimization_opportunities": result.get("optimization_opportunities", []),
                "reasoning_chain": result.get("reasoning_chain", []),
                "source": "llm",
                "filename": filename,
            }

        except Exception as e:
            self.logger.warning(f"LLM analysis failed, using fallback: {e}")
            analysis = self._fallback_analysis(code, filename)

        # Store in shared context
        self.context.set("analysis_results", analysis)

        # Notify optimization agent if there are opportunities or issues
        if analysis.get("issues") or analysis.get("optimization_opportunities"):
            self.send_message(
                receiver_id="optimization_agent",
                payload={
                    "action": "optimize",
                    "code": code,
                    "analysis": analysis,
                },
                message_type=MessageType.REQUEST,
                priority=MessagePriority.HIGH,
            )

        self.logger.info(
            f"Analysis complete: {len(analysis.get('issues', []))} issues, "
            f"{len(analysis.get('optimization_opportunities', []))} opportunities"
        )
        return analysis

    def _fallback_analysis(self, code: str, filename: str) -> Dict[str, Any]:
        """Basic string-based analysis when LLM is unavailable."""
        issues = []
        patterns = []

        # Simple pattern detection
        if code.count("for") > 1:
            patterns.append("nested_loops")
        elif "for" in code or "while" in code:
            patterns.append("loop")

        if "malloc" in code or "new " in code:
            patterns.append("dynamic_allocation")
        if "free(" in code or "delete " in code:
            patterns.append("manual_deallocation")

        # Simple bug detection
        if "malloc" in code and "free" not in code:
            issues.append({
                "type": "memory_leak",
                "severity": "high",
                "description": "Memory allocated but never freed",
                "confidence": 0.6,
            })
        if "arr[" in code or "array[" in code:
            issues.append({
                "type": "potential_buffer_overflow",
                "severity": "medium",
                "description": "Array access detected - bounds checking recommended",
                "confidence": 0.4,
            })

        return {
            "complexity": {
                "time": "O(n^2)" if "nested_loops" in patterns else "O(n)",
                "space": "O(n)" if "dynamic_allocation" in patterns else "O(1)",
            },
            "patterns": patterns,
            "issues": issues,
            "optimization_opportunities": [],
            "reasoning_chain": [
                {
                    "step": 1,
                    "observation": "LLM unavailable, used pattern matching",
                    "inference": "Results may be incomplete",
                    "conclusion": "Manual review recommended",
                }
            ],
            "source": "fallback",
            "filename": filename,
        }
