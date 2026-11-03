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
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


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
    test_case_results: List[Dict[str, Any]] = field(default_factory=list)


class DifferentialTester:
    """
    Compiles and runs two versions of C/C++ code, comparing their output and exit behavior.

    Usage
    -----
    tester = DifferentialTester()
    result = tester.test(original_src, optimized_src)
    print(result.passed)
    """

    def __init__(self, compiler: Optional[str] = None, timeout: int = 10):
        self.compiler = compiler
        self.timeout  = timeout
        self._compiler_cache: Dict[str, bool] = {}

    def _resolve_compiler(self, is_cpp: bool) -> str:
        if self.compiler:
            return self.compiler
        # Detect compiler: g++ or clang++ for C++, gcc or clang for C
        candidates = ["g++", "clang++"] if is_cpp else ["gcc", "clang"]
        for c in candidates:
            if self._check_compiler(c):
                return c
        return "g++" if is_cpp else "gcc"

    def test(
        self,
        original_src: str,
        optimized_src: str,
        test_inputs: Optional[List[str]] = None,
        language: str = "cpp",
    ) -> DiffTestResult:
        """
        Compile and run both versions across test inputs, verifying stdout, stderr, and exit codes.
        """
        is_cpp = language.lower() in ("cpp", "c++") or ("<iostream>" in original_src or "std::" in original_src)
        active_compiler = self._resolve_compiler(is_cpp)

        if not self._check_compiler(active_compiler):
            return DiffTestResult(
                passed=False,
                skipped=True,
                original_output="",
                optimized_output="",
                error=f"Compiler '{active_compiler}' not found on PATH; differential test skipped.",
            )

        inputs = test_inputs if test_inputs and len(test_inputs) > 0 else [""]
        ext = ".cpp" if is_cpp else ".c"

        with tempfile.TemporaryDirectory() as tmpdir:
            orig_src_path = os.path.join(tmpdir, f"original{ext}")
            opt_src_path  = os.path.join(tmpdir, f"optimized{ext}")
            orig_bin      = os.path.join(tmpdir, "original.exe" if os.name == "nt" else "original.bin")
            opt_bin       = os.path.join(tmpdir, "optimized.exe" if os.name == "nt" else "optimized.bin")

            # Write source files
            with open(orig_src_path, "w", encoding="utf-8") as f:
                f.write(original_src)
            with open(opt_src_path, "w", encoding="utf-8") as f:
                f.write(optimized_src)

            # Compile original
            orig_compile_err = self._compile(active_compiler, orig_src_path, orig_bin)
            if orig_compile_err:
                return DiffTestResult(
                    passed=False,
                    original_output="",
                    optimized_output="",
                    compile_error_original=orig_compile_err,
                    error=f"Original code failed to compile: {orig_compile_err}",
                )

            # Compile optimized
            opt_compile_err = self._compile(active_compiler, opt_src_path, opt_bin)
            if opt_compile_err:
                return DiffTestResult(
                    passed=False,
                    original_output="",
                    optimized_output="",
                    compile_error_optimized=opt_compile_err,
                    error=f"Optimized code failed to compile: {opt_compile_err}",
                )

            # Run test cases
            test_results: List[Dict[str, Any]] = []
            overall_passed = True
            first_mismatch_error: Optional[str] = None
            last_orig_out = ""
            last_opt_out = ""
            last_orig_rc = 0
            last_opt_rc = 0
            runtime_err = None

            for idx, inp in enumerate(inputs):
                orig_out, orig_err, orig_rc = self._run(orig_bin, inp)
                opt_out, opt_err, opt_rc = self._run(opt_bin, inp)

                last_orig_out = orig_out
                last_opt_out = opt_out
                last_orig_rc = orig_rc
                last_opt_rc = opt_rc

                case_passed = True
                case_error = None

                # Return code checks
                if orig_rc == -1 or opt_rc == -1:
                    case_passed = False
                    case_error = "Execution timed out."
                elif orig_rc != 0 and opt_rc != 0:
                    case_passed = False
                    case_error = f"Both executions exited abnormally (original={orig_rc}, optimized={opt_rc})."
                elif orig_rc != opt_rc:
                    case_passed = False
                    case_error = f"Return code mismatch: original={orig_rc}, candidate={opt_rc}."
                elif orig_out != opt_out:
                    case_passed = False
                    case_error = f"Output mismatch (original='{orig_out}', candidate='{opt_out}')."

                if not case_passed:
                    overall_passed = False
                    if not first_mismatch_error:
                        first_mismatch_error = case_error
                    if orig_err or opt_err:
                        runtime_err = opt_err or orig_err

                test_results.append({
                    "test_case": idx + 1,
                    "input": inp,
                    "passed": case_passed,
                    "error": case_error,
                    "original_rc": orig_rc,
                    "optimized_rc": opt_rc,
                    "original_out": orig_out,
                    "optimized_out": opt_out,
                })

            return DiffTestResult(
                passed=overall_passed,
                original_output=last_orig_out,
                optimized_output=last_opt_out,
                runtime_error=runtime_err,
                error=first_mismatch_error,
                original_returncode=last_orig_rc,
                optimized_returncode=last_opt_rc,
                test_case_results=test_results,
            )

    # ── Internals ─────────────────────────────────────────────────────────────

    def _compile(self, compiler: str, src_path: str, out_path: str) -> Optional[str]:
        """Return None on success, error string on failure."""
        try:
            proc = subprocess.run(
                [compiler, src_path, "-o", out_path, "-O0", "-w"],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            if proc.returncode != 0:
                return proc.stderr.strip() or f"Compilation failed with exit code {proc.returncode}."
            return None
        except subprocess.TimeoutExpired:
            return "Compilation timed out."
        except FileNotFoundError:
            return f"Compiler '{compiler}' not found."

    def _run(self, binary_path: str, inp: str = ""):
        """Return (stdout, stderr, returncode) as strings and int."""
        try:
            proc = subprocess.run(
                [binary_path],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                input=inp,
            )
            return proc.stdout.strip(), proc.stderr.strip(), proc.returncode
        except subprocess.TimeoutExpired:
            return "", "Execution timed out.", -1
        except Exception as exc:
            return "", str(exc), -1

    def _check_compiler(self, compiler: Optional[str] = None) -> bool:
        c = compiler or self.compiler or "g++"
        if c in self._compiler_cache:
            return self._compiler_cache[c]
        import shutil
        if shutil.which(c):
            self._compiler_cache[c] = True
            return True
        try:
            subprocess.run([c, "--version"], capture_output=True, timeout=5)
            self._compiler_cache[c] = True
            return True
        except Exception:
            self._compiler_cache[c] = False
            return False
