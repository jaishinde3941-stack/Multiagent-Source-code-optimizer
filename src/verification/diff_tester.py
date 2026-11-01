"""
Differential Tester — Week 7

Compiles original and optimized C/C++ code, runs both, and compares
stdout output to verify behavioral equivalence.

Requires g++ to be on the system PATH (MinGW/MSYS on Windows).
Falls back gracefully if g++ is unavailable.
"""

import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class DiffTestResult:
    passed: bool
    original_output: str
    optimized_output: str
    skipped: bool = False                          # True when test could not run at all
    compile_error_original: Optional[str] = None
    compile_error_optimized: Optional[str] = None
    runtime_error: Optional[str] = None
    error: Optional[str] = None
    original_returncode: int = 0
    optimized_returncode: int = 0


class DifferentialTester:
    """
    Compiles and runs two versions of C/C++ code, comparing their output.

    Usage
    -----
    tester = DifferentialTester()
    result = tester.test(original_src, optimized_src)
    print(result.passed)
    """

    def __init__(self, compiler: str = "g++", timeout: int = 10):
        self.compiler = compiler
        self.timeout  = timeout
        self._gpp_available = self._check_compiler()

    def test(self, original_src: str, optimized_src: str) -> DiffTestResult:
        """
        Compile and run both versions, return comparison result.

        If the compiler is not available or compilation fails,
        passed is set to None (unknown) with an informative error.
        """
        if not self._gpp_available:
            return DiffTestResult(
                passed=False,
                skipped=True,
                original_output="",
                optimized_output="",
                error="g++ not found on PATH; differential test skipped.",
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            orig_src_path = os.path.join(tmpdir, "original.cpp")
            opt_src_path  = os.path.join(tmpdir, "optimized.cpp")
            orig_bin      = os.path.join(tmpdir, "original.exe")
            opt_bin       = os.path.join(tmpdir, "optimized.exe")

            # Write source files
            with open(orig_src_path, "w", encoding="utf-8") as f:
                f.write(original_src)
            with open(opt_src_path, "w", encoding="utf-8") as f:
                f.write(optimized_src)

            # Compile original
            orig_compile_err = self._compile(orig_src_path, orig_bin)
            if orig_compile_err:
                return DiffTestResult(
                    passed=False,
                    original_output="",
                    optimized_output="",
                    compile_error_original=orig_compile_err,
                    error="Original code failed to compile.",
                )

            # Compile optimized
            opt_compile_err = self._compile(opt_src_path, opt_bin)
            if opt_compile_err:
                return DiffTestResult(
                    passed=False,
                    original_output="",
                    optimized_output="",
                    compile_error_optimized=opt_compile_err,
                    error="Optimized code failed to compile.",
                )

            # Run original
            orig_out, orig_err, orig_rc = self._run(orig_bin)
            # Run optimized
            opt_out, opt_err, opt_rc = self._run(opt_bin)

            passed = (orig_out == opt_out)

            return DiffTestResult(
                passed=passed,
                original_output=orig_out,
                optimized_output=opt_out,
                runtime_error=(orig_err or opt_err) or None,
                original_returncode=orig_rc,
                optimized_returncode=opt_rc,
            )

    # ── Internals ─────────────────────────────────────────────────────────────

    def _compile(self, src_path: str, out_path: str) -> Optional[str]:
        """Return None on success, error string on failure."""
        try:
            proc = subprocess.run(
                [self.compiler, src_path, "-o", out_path, "-O0", "-w"],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            if proc.returncode != 0:
                return proc.stderr.strip()
            return None
        except subprocess.TimeoutExpired:
            return "Compilation timed out."
        except FileNotFoundError:
            self._gpp_available = False
            return f"Compiler '{self.compiler}' not found."

    def _run(self, binary_path: str):
        """Return (stdout, stderr, returncode) as strings and int."""
        try:
            proc = subprocess.run(
                [binary_path],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                input="",          # provide empty stdin → immediate EOF
            )
            return proc.stdout.strip(), proc.stderr.strip(), proc.returncode
        except subprocess.TimeoutExpired:
            return "", "Execution timed out.", -1
        except Exception as exc:
            return "", str(exc), -1

    def _check_compiler(self) -> bool:
        try:
            subprocess.run(
                [self.compiler, "--version"],
                capture_output=True,
                timeout=5,
            )
            return True
        except Exception:
            return False
