"""
C++ Compiler Wrapper

Provides compilation and execution of C++ source files for differential testing.
"""

import subprocess
import tempfile
import os
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)


@dataclass
class CompileResult:
    """Result of a compilation attempt"""
    success: bool
    output_path: Optional[str]
    errors: str
    warnings: str


@dataclass
class RunResult:
    """Result of running a compiled binary"""
    stdout: str
    stderr: str
    returncode: int
    timed_out: bool


class CppCompiler:
    """Wrapper around g++ for compiling and running C++ code"""

    def __init__(self, compiler: str = "g++"):
        self.compiler = compiler

    def compile(
        self,
        source_path: str,
        output_path: Optional[str] = None,
        flags: Optional[List[str]] = None,
        timeout: int = 30,
    ) -> CompileResult:
        """
        Compile a C++ source file.

        Args:
            source_path: Path to the .cpp file
            output_path: Path for the output binary (auto-generated if None)
            flags: Extra compiler flags (default: ["-O0", "-std=c++17"])
            timeout: Compilation timeout in seconds

        Returns:
            CompileResult with success status and paths
        """
        if flags is None:
            flags = ["-O0", "-std=c++17"]

        if output_path is None:
            # Generate temp path for output
            source = Path(source_path)
            output_path = str(
                Path(tempfile.gettempdir()) / f"{source.stem}_compiled.exe"
            )

        cmd = [self.compiler] + flags + [str(source_path), "-o", output_path]
        logger.info(f"Compiling: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            # Separate warnings from errors in stderr
            stderr_lines = result.stderr.strip().split("\n") if result.stderr.strip() else []
            warnings = "\n".join(l for l in stderr_lines if "warning" in l.lower())
            errors = "\n".join(l for l in stderr_lines if "error" in l.lower())

            if result.returncode == 0:
                return CompileResult(
                    success=True,
                    output_path=output_path,
                    errors="",
                    warnings=warnings,
                )
            else:
                return CompileResult(
                    success=False,
                    output_path=None,
                    errors=errors or result.stderr,
                    warnings=warnings,
                )
        except subprocess.TimeoutExpired:
            return CompileResult(
                success=False,
                output_path=None,
                errors="Compilation timed out",
                warnings="",
            )
        except FileNotFoundError:
            return CompileResult(
                success=False,
                output_path=None,
                errors=f"Compiler not found: {self.compiler}",
                warnings="",
            )

    def run(
        self,
        executable_path: str,
        input_data: str = "",
        timeout: int = 10,
    ) -> RunResult:
        """
        Run a compiled binary.

        Args:
            executable_path: Path to the compiled executable
            input_data: Stdin input for the program
            timeout: Execution timeout in seconds

        Returns:
            RunResult with stdout, stderr, returncode
        """
        logger.info(f"Running: {executable_path}")

        try:
            result = subprocess.run(
                [executable_path],
                input=input_data,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return RunResult(
                stdout=result.stdout,
                stderr=result.stderr,
                returncode=result.returncode,
                timed_out=False,
            )
        except subprocess.TimeoutExpired:
            return RunResult(
                stdout="",
                stderr="Execution timed out",
                returncode=-1,
                timed_out=True,
            )
        except FileNotFoundError:
            return RunResult(
                stdout="",
                stderr=f"Executable not found: {executable_path}",
                returncode=-1,
                timed_out=False,
            )

    def compile_string(
        self,
        code: str,
        output_path: Optional[str] = None,
        flags: Optional[List[str]] = None,
        timeout: int = 30,
    ) -> CompileResult:
        """
        Compile C++ code from a string (writes to temp file first).

        Args:
            code: C++ source code string
            output_path: Path for output binary
            flags: Compiler flags
            timeout: Compilation timeout

        Returns:
            CompileResult
        """
        # Write code to temp file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".cpp", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            temp_source = f.name

        try:
            return self.compile(temp_source, output_path, flags, timeout)
        finally:
            # Clean up temp source
            try:
                os.unlink(temp_source)
            except OSError:
                pass

    @staticmethod
    def cleanup(path: str):
        """Remove a compiled binary."""
        try:
            os.unlink(path)
        except OSError:
            pass
