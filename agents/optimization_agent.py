"""
Optimization Agent - LLM-Powered Code Optimization

Uses Qwen 2.5 Coder via Ollama to generate optimized versions of C/C++ code
based on analysis results.
"""

import json
import logging
from typing import Dict, Any, List

from agent_framework import BaseAgent, MessageType, MessagePriority
from llm.ollama_client import OllamaClient
from llm.prompts import OPTIMIZATION_PROMPT

logger = logging.getLogger(__name__)


class OptimizationAgent(BaseAgent):
    """Agent that generates optimized C/C++ code using LLM"""

    def __init__(self, agent_id, agent_type, context_manager, llm_client=None):
        self._llm = llm_client or OllamaClient()
        super().__init__(agent_id, agent_type, context_manager)

    def get_capabilities(self) -> List[str]:
        return [
            "code_optimization",
            "bug_fixing",
            "transformation_generation",
        ]

    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate optimized code based on analysis results.

        Args:
            input_data: {"code": str, "analysis": dict}

        Returns:
            Optimization results with transformed code
        """
        code = input_data.get("code", "")
        analysis = input_data.get("analysis", {})

        if not code.strip():
            return {"error": "No code provided"}

        self.logger.info("Generating optimization suggestions...")

        try:
            analysis_str = json.dumps(analysis, indent=2)
            prompt = OPTIMIZATION_PROMPT.format(code=code, analysis=analysis_str)
            result = self._llm.generate_json(prompt)

            optimization = {
                "original_code": code,
                "optimized_code": result.get("optimized_code", code),
                "transformations": result.get("transformations", []),
                "preserved_behavior": result.get("preserved_behavior", False),
                "reasoning_chain": result.get("reasoning_chain", []),
                "source": "llm",
            }

        except Exception as e:
            self.logger.warning(f"LLM optimization failed, using fallback: {e}")
            optimization = self._fallback_optimization(code, analysis)

        # Store in context
        self.context.append("optimization_suggestions", optimization)

        # Notify verification agent
        self.send_message(
            receiver_id="verification_agent",
            payload={
                "action": "verify",
                "original": code,
                "optimized": optimization["optimized_code"],
            },
            message_type=MessageType.REQUEST,
            priority=MessagePriority.HIGH,
        )

        self.logger.info(
            f"Optimization complete: {len(optimization.get('transformations', []))} transformations"
        )
        return optimization

    def _fallback_optimization(self, code: str, analysis: Dict) -> Dict[str, Any]:
        """Basic optimization when LLM is unavailable."""
        # Just return original code with note that LLM was unavailable
        return {
            "original_code": code,
            "optimized_code": code,
            "transformations": [],
            "preserved_behavior": True,
            "reasoning_chain": [
                {
                    "step": 1,
                    "observation": "LLM unavailable",
                    "action": "No transformations applied",
                    "justification": "Cannot generate optimizations without LLM",
                }
            ],
            "source": "fallback",
        }
