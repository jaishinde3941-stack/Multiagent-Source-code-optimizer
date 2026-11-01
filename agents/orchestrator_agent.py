"""
Orchestrator Agent - Pipeline Coordinator

Coordinates the full analysis pipeline: Analysis -> Optimization -> Verification -> Security.
Takes a C++ file and runs it through all agents sequentially.
"""

import time
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

from agent_framework import (
    BaseAgent, AgentRegistry, ContextManager,
    MessageType, MessagePriority,
)
from llm.ollama_client import OllamaClient
from utils.file_utils import read_cpp_file

logger = logging.getLogger(__name__)


class OrchestratorAgent(BaseAgent):
    """Coordinates the multi-agent optimization pipeline"""

    def __init__(self, agent_id, agent_type, context_manager, llm_client=None):
        self._llm = llm_client or OllamaClient()
        super().__init__(agent_id, agent_type, context_manager)

    def get_capabilities(self) -> List[str]:
        return ["pipeline_coordination", "workflow_management"]

    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run the full optimization pipeline on a C++ file.

        Args:
            input_data: {"file_path": str} or {"code": str, "filename": str}

        Returns:
            Combined results from all pipeline stages
        """
        # Get code from file or directly
        file_path = input_data.get("file_path")
        if file_path:
            code = read_cpp_file(file_path)
            filename = Path(file_path).name
        else:
            code = input_data.get("code", "")
            filename = input_data.get("filename", "unknown")

        if not code.strip():
            return {"error": "No code provided"}

        self.logger.info(f"Starting pipeline for {filename}")

        # Store original code in context
        self.context.set("original_code", code, save_version=False)
        self.context.set("source_file", filename)

        results = {"filename": filename, "stages": {}}

        # Stage 1: Analysis
        self.logger.info("Stage 1: Analysis")
        from agents.analysis_agent import AnalysisAgent

        analysis_agent = AnalysisAgent(
            "pipeline_analysis", "analysis", self.context, self._llm
        )
        try:
            analysis_result = analysis_agent.process(
                {"code": code, "filename": filename}
            )
            results["stages"]["analysis"] = analysis_result
        except Exception as e:
            self.logger.error(f"Analysis failed: {e}")
            results["stages"]["analysis"] = {"error": str(e)}
            return results

        # Stage 2: Optimization
        self.logger.info("Stage 2: Optimization")
        from agents.optimization_agent import OptimizationAgent

        opt_agent = OptimizationAgent(
            "pipeline_optimization", "optimization", self.context, self._llm
        )
        try:
            opt_result = opt_agent.process(
                {"code": code, "analysis": analysis_result}
            )
            results["stages"]["optimization"] = opt_result
        except Exception as e:
            self.logger.error(f"Optimization failed: {e}")
            results["stages"]["optimization"] = {"error": str(e)}

        # Stage 3: Verification (only if we have optimized code)
        optimized_code = opt_result.get("optimized_code", "") if "error" not in results["stages"].get("optimization", {}) else ""
        if optimized_code and optimized_code != code:
            self.logger.info("Stage 3: Verification")
            from agents.verification_agent import VerificationAgent

            ver_agent = VerificationAgent(
                "pipeline_verification", "verification", self.context
            )
            try:
                ver_result = ver_agent.process(
                    {"original": code, "optimized": optimized_code}
                )
                results["stages"]["verification"] = ver_result
            except Exception as e:
                self.logger.error(f"Verification failed: {e}")
                results["stages"]["verification"] = {"error": str(e)}
        else:
            results["stages"]["verification"] = {
                "status": "skipped",
                "reason": "No changes to verify",
            }

        # Stage 4: Security
        self.logger.info("Stage 4: Security")
        from agents.security_agent import SecurityAgent

        sec_agent = SecurityAgent(
            "pipeline_security", "security", self.context, self._llm
        )
        try:
            sec_result = sec_agent.process({"code": code, "filename": filename})
            results["stages"]["security"] = sec_result
        except Exception as e:
            self.logger.error(f"Security audit failed: {e}")
            results["stages"]["security"] = {"error": str(e)}

        # Build summary
        results["summary"] = self._build_summary(results)

        self.logger.info(f"Pipeline complete for {filename}")
        return results

    def _build_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Build a summary of all pipeline results."""
        analysis = results["stages"].get("analysis", {})
        optimization = results["stages"].get("optimization", {})
        verification = results["stages"].get("verification", {})
        security = results["stages"].get("security", {})

        return {
            "issues_found": len(analysis.get("issues", [])),
            "optimizations_applied": len(optimization.get("transformations", [])),
            "verification_status": verification.get("status", "not_run"),
            "vulnerabilities_found": len(security.get("vulnerabilities", [])),
            "overall_risk": security.get("overall_risk", "unknown"),
        }
