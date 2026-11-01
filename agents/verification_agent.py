"""
Verification Agent - Differential Testing

Compiles and runs both original and optimized C++ code,
comparing outputs to verify correctness of transformations.
"""

import logging
from typing import Dict, Any, List

from agent_framework import BaseAgent
from utils.compiler import CppCompiler

logger = logging.getLogger(__name__)


class VerificationAgent(BaseAgent):
    """Agent that verifies optimized code through differential testing"""

    def __init__(self, agent_id, agent_type, context_manager, compiler=None):
        self._compiler = compiler or CppCompiler()
        super().__init__(agent_id, agent_type, context_manager)

    def get_capabilities(self) -> List[str]:
        return [
            "correctness_verification",
            "differential_testing",
            "compilation_check",
        ]

    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verify optimized code by compiling and comparing outputs.

        Args:
            input_data: {"original": str, "optimized": str, "test_input": str (optional)}

        Returns:
            Verification results with pass/fail and details
        """
        original = input_data.get("original", "")
        optimized = input_data.get("optimized", "")
        test_input = input_data.get("test_input", "")

        if not original.strip() or not optimized.strip():
            return {"error": "Both original and optimized code required"}

        self.logger.info("Starting differential verification...")

        result = {
            "original_compiles": False,
            "optimized_compiles": False,
            "outputs_match": False,
            "status": "failed",
            "details": {},
        }

        # Compile original
        orig_compile = self._compiler.compile_string(original)
        result["original_compiles"] = orig_compile.success
        result["details"]["original_compile"] = {
            "success": orig_compile.success,
            "errors": orig_compile.errors,
            "warnings": orig_compile.warnings,
        }

        # Compile optimized
        opt_compile = self._compiler.compile_string(optimized)
        result["optimized_compiles"] = opt_compile.success
        result["details"]["optimized_compile"] = {
            "success": opt_compile.success,
            "errors": opt_compile.errors,
            "warnings": opt_compile.warnings,
        }

        # If both compile, run and compare outputs
        if orig_compile.success and opt_compile.success:
            orig_run = self._compiler.run(orig_compile.output_path, test_input)
            opt_run = self._compiler.run(opt_compile.output_path, test_input)

            result["details"]["original_run"] = {
                "stdout": orig_run.stdout,
                "stderr": orig_run.stderr,
                "returncode": orig_run.returncode,
                "timed_out": orig_run.timed_out,
            }
            result["details"]["optimized_run"] = {
                "stdout": opt_run.stdout,
                "stderr": opt_run.stderr,
                "returncode": opt_run.returncode,
                "timed_out": opt_run.timed_out,
            }

            # Compare outputs
            if not orig_run.timed_out and not opt_run.timed_out:
                result["outputs_match"] = (
                    orig_run.stdout == opt_run.stdout
                    and orig_run.returncode == opt_run.returncode
                )

                if result["outputs_match"]:
                    result["status"] = "passed"
                else:
                    result["status"] = "output_mismatch"
            else:
                result["status"] = "timeout"

            # Cleanup binaries
            if orig_compile.output_path:
                CppCompiler.cleanup(orig_compile.output_path)
            if opt_compile.output_path:
                CppCompiler.cleanup(opt_compile.output_path)

        elif not orig_compile.success and opt_compile.success:
            # Original didn't compile but optimized does - improvement
            result["status"] = "improved_compilability"
            if opt_compile.output_path:
                CppCompiler.cleanup(opt_compile.output_path)
        elif orig_compile.success and not opt_compile.success:
            result["status"] = "optimization_broke_compilation"
            if orig_compile.output_path:
                CppCompiler.cleanup(orig_compile.output_path)
        else:
            result["status"] = "both_fail_compilation"

        # Store in context
        self.context.set("verification_status", result)

        self.logger.info(f"Verification complete: {result['status']}")
        return result
