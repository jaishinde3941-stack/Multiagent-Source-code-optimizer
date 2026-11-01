"""
Security Agent - LLM-Powered Vulnerability Detection

Uses Qwen 2.5 Coder via Ollama and optionally cppcheck to detect
security vulnerabilities in C/C++ code.
"""

import subprocess
import logging
from typing import Dict, Any, List, Optional

from agent_framework import BaseAgent
from llm.ollama_client import OllamaClient
from llm.prompts import SECURITY_PROMPT

logger = logging.getLogger(__name__)


class SecurityAgent(BaseAgent):
    """Agent that detects security vulnerabilities using LLM + cppcheck"""

    def __init__(self, agent_id, agent_type, context_manager, llm_client=None):
        self._llm = llm_client or OllamaClient()
        self._cppcheck_available = self._check_cppcheck()
        super().__init__(agent_id, agent_type, context_manager)

    def get_capabilities(self) -> List[str]:
        caps = ["vulnerability_detection", "security_audit", "cwe_classification"]
        if self._cppcheck_available:
            caps.append("cppcheck_integration")
        return caps

    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Audit C/C++ code for security vulnerabilities.

        Args:
            input_data: {"code": str, "filename": str (optional)}

        Returns:
            Security findings with vulnerabilities and risk assessment
        """
        code = input_data.get("code", "")
        filename = input_data.get("filename", "unknown")

        if not code.strip():
            return {"error": "No code provided"}

        self.logger.info(f"Running security audit on {filename}")

        # LLM-based analysis
        llm_findings = self._llm_audit(code)

        # cppcheck analysis (if available)
        cppcheck_findings = []
        if self._cppcheck_available and filename != "unknown":
            cppcheck_findings = self._cppcheck_audit(filename)

        # Merge findings
        all_vulnerabilities = llm_findings.get("vulnerabilities", [])
        for finding in cppcheck_findings:
            # Avoid duplicates by checking type overlap
            if not any(
                v["type"] == finding["type"] for v in all_vulnerabilities
            ):
                all_vulnerabilities.append(finding)

        result = {
            "vulnerabilities": all_vulnerabilities,
            "overall_risk": llm_findings.get("overall_risk", "unknown"),
            "reasoning_chain": llm_findings.get("reasoning_chain", []),
            "summary": llm_findings.get("summary", "Analysis incomplete"),
            "sources": ["llm"] + (["cppcheck"] if cppcheck_findings else []),
            "filename": filename,
        }

        # Store in context
        self.context.append("security_findings", result)

        self.logger.info(
            f"Security audit complete: {len(all_vulnerabilities)} vulnerabilities found"
        )
        return result

    def _llm_audit(self, code: str) -> Dict[str, Any]:
        """Run LLM-based security analysis."""
        try:
            prompt = SECURITY_PROMPT.format(code=code)
            return self._llm.generate_json(prompt)
        except Exception as e:
            self.logger.warning(f"LLM security audit failed: {e}")
            return {
                "vulnerabilities": [],
                "overall_risk": "unknown",
                "reasoning_chain": [],
                "summary": f"LLM audit failed: {e}",
            }

    def _cppcheck_audit(self, filepath: str) -> List[Dict[str, Any]]:
        """Run cppcheck on a file and parse results."""
        try:
            result = subprocess.run(
                [
                    "cppcheck",
                    "--enable=all",
                    "--output-format=json",
                    "--quiet",
                    filepath,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            findings = []
            for line in result.stderr.split("\n"):
                line = line.strip()
                if not line:
                    continue
                # Parse cppcheck text output format
                if "error" in line.lower() or "warning" in line.lower():
                    severity = "high" if "error" in line.lower() else "medium"
                    findings.append({
                        "type": "cppcheck_finding",
                        "severity": severity,
                        "description": line,
                        "confidence": 0.9,
                        "source": "cppcheck",
                    })
            return findings
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning(f"cppcheck failed: {e}")
            return []

    @staticmethod
    def _check_cppcheck() -> bool:
        """Check if cppcheck is available."""
        try:
            subprocess.run(
                ["cppcheck", "--version"],
                capture_output=True,
                timeout=5,
            )
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
