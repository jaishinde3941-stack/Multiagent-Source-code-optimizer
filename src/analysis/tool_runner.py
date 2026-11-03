"""
Shared Tool Runner for C/C++ Conventional Analysis Tools.

Integrates:
  - Clang and Clang++ (compiler diagnostics and warnings)
  - Clang-Tidy (static analysis checks)
  - Cppcheck (machine-readable static analysis)
  - AddressSanitizer (ASan) runtime instrumentation
  - UndefinedBehaviorSanitizer (UBSan) runtime instrumentation

Enforces process safety, non-destructive temporary isolation, safe subprocess argument lists,
and explicit truthful execution statuses.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET

from .finding_schema import Finding, normalize_finding

logger = logging.getLogger(__name__)


class ToolStatus:
    """
    Explicit tool execution statuses as required by Section 5.4 & 12:
      - PASSED: Tool ran successfully to completion and reported zero defects or warnings.
      - FINDINGS: Tool ran successfully to completion and reported one or more defects/warnings.
      - FAILED: Tool failed to execute (e.g., non-zero exit code due to tool crash, internal error, or compilation failure).
      - UNAVAILABLE: Tool executable is not present on the system PATH.
      - SKIPPED: Tool was intentionally not run (e.g., runtime sanitizer skipped because compilation failed or binary lacks entry point).
      - INCONCLUSIVE: Tool ran but timed out or produced truncated/unparseable output without a decisive conclusion.
    """
    PASSED = "PASSED"
    FINDINGS = "FINDINGS"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"
    SKIPPED = "SKIPPED"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass
class ToolExecutionResult:
    """Detailed execution result for an individual analysis tool."""
    tool_name: str
    status: str                         # One of ToolStatus.*
    findings: List[Dict[str, Any]] = field(default_factory=list)
    raw_output: str = ""
    error_message: Optional[str] = None
    exit_code: Optional[int] = None
    execution_time_ms: float = 0.0
    command: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "status": self.status,
            "findings_count": len(self.findings),
            "findings": self.findings,
            "raw_output": self.raw_output,
            "error_message": self.error_message,
            "exit_code": self.exit_code,
            "limitations": self.limitations,
        }


class ToolRunner:
    """
    Manages discovery, concurrent execution, and output normalization of
    conventional C/C++ static and dynamic analysis tools.
    """

    DEFAULT_CLANG_TIDY_CHECKS = (
        "clang-analyzer-*,"
        "bugprone-*,"
        "cert-*,"
        "performance-*,"
        "modernize-use-nullptr"
    )

    def __init__(self, timeout_sec: int = 15):
        self.timeout = timeout_sec
        self._tool_cache: Dict[str, Optional[str]] = {}

    def find_executable(self, name: str) -> Optional[str]:
        """Discover an executable on the system PATH with caching and standard Windows fallback paths."""
        if name not in self._tool_cache:
            found = shutil.which(name)
            if not found:
                candidate_dirs = [
                    r"C:\Program Files\LLVM\bin",
                    r"C:\Program Files (x86)\LLVM\bin",
                    os.path.expandvars(r"%LOCALAPPDATA%\Programs\LLVM\bin"),
                    r"C:\Program Files\Cppcheck",
                    r"C:\Program Files (x86)\Cppcheck",
                    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Cppcheck"),
                ]
                for cdir in candidate_dirs:
                    cand = os.path.join(cdir, f"{name}.exe" if not name.endswith(".exe") else name)
                    if os.path.isfile(cand):
                        found = cand
                        break
            self._tool_cache[name] = found
        return self._tool_cache[name]

    def check_availability(self) -> Dict[str, bool]:
        """Check availability of all configured analysis tools."""
        return {
            "clang": bool(self.find_executable("clang")),
            "clang++": bool(self.find_executable("clang++")),
            "clang-tidy": bool(self.find_executable("clang-tidy")),
            "cppcheck": bool(self.find_executable("cppcheck")),
        }

    # ── Clang / Clang++ Compiler Analysis ─────────────────────────────────────

    def run_clang_compiler(
        self,
        source_code: str,
        file_path: str = "<source>",
        compilation_database_dir: Optional[str] = None,
    ) -> ToolExecutionResult:
        """
        Run Clang or Clang++ to collect compiler diagnostics, warnings, and syntax errors.
        """
        is_cpp = self._is_cpp_file(file_path, source_code)
        compiler_name = "clang++" if is_cpp else "clang"
        exe_path = self.find_executable(compiler_name)

        if not exe_path:
            # Check if generic clang or g++ is available as alternative indicator, but report clang unavailable
            return ToolExecutionResult(
                tool_name=compiler_name,
                status=ToolStatus.UNAVAILABLE,
                error_message=f"{compiler_name} executable was not found on PATH.",
                limitations=[f"{compiler_name} not available in system environment."],
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            ext = ".cpp" if is_cpp else ".c"
            src_file = os.path.join(tmpdir, f"source{ext}")
            obj_file = os.path.join(tmpdir, "output.o")

            with open(src_file, "w", encoding="utf-8") as f:
                f.write(source_code)

            cmd = [exe_path, "-fsyntax-only", "-Wall", "-Wextra"]
            limitations = []

            # Check for compilation database (extract flags safely without passing -p to compiler)
            comp_db_used = False
            if compilation_database_dir and os.path.isfile(os.path.join(compilation_database_dir, "compile_commands.json")):
                try:
                    with open(os.path.join(compilation_database_dir, "compile_commands.json"), "r", encoding="utf-8") as cdf:
                        db_entries = json.load(cdf)
                    target_entry = None
                    file_base = os.path.basename(file_path)
                    for entry in db_entries:
                        e_file = entry.get("file", "")
                        if e_file.endswith(file_base) or os.path.basename(e_file) == file_base:
                            target_entry = entry
                            break
                    if target_entry:
                        comp_db_used = True
                        # Safely inherit include dirs (-I) and macro definitions (-D)
                        args = target_entry.get("arguments") or target_entry.get("command", "").split()
                        for a in args:
                            if a.startswith(("-I", "-D", "-isystem")):
                                if a not in cmd:
                                    cmd.append(a)
                    else:
                        limitations.append(f"Source file '{file_path}' not found in compilation database.")
                except Exception as db_err:
                    limitations.append(f"Failed to parse compilation database: {db_err}")

            std_flag = "-std=c++17" if is_cpp else "-std=c11"
            if not any(a.startswith("-std=") for a in cmd):
                cmd.append(std_flag)

            if not comp_db_used:
                limitations.append("No matching compilation database entry found; used standalone fallback flags (-Wall -Wextra).")

            cmd.append(src_file)

            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    shell=False,
                )
                raw = (proc.stderr or "") + (proc.stdout or "")
                findings = self._parse_clang_diagnostics(raw, file_path, tool=compiler_name)

                if proc.returncode != 0:
                    status = ToolStatus.FAILED if not findings else ToolStatus.FINDINGS
                    err_msg = "Clang compilation reported errors or warnings."
                elif findings:
                    status = ToolStatus.FINDINGS
                    err_msg = None
                else:
                    status = ToolStatus.PASSED
                    err_msg = None

                return ToolExecutionResult(
                    tool_name=compiler_name,
                    status=status,
                    findings=findings,
                    raw_output=raw,
                    error_message=err_msg,
                    exit_code=proc.returncode,
                    command=cmd,
                    limitations=limitations,
                )
            except subprocess.TimeoutExpired:
                return ToolExecutionResult(
                    tool_name=compiler_name,
                    status=ToolStatus.INCONCLUSIVE,
                    error_message=f"{compiler_name} execution timed out after {self.timeout}s.",
                    command=cmd,
                )
            except Exception as exc:
                return ToolExecutionResult(
                    tool_name=compiler_name,
                    status=ToolStatus.FAILED,
                    error_message=str(exc),
                    command=cmd,
                )

    # ── Clang-Tidy Static Analysis ────────────────────────────────────────────

    def run_clang_tidy(
        self,
        source_code: str,
        file_path: str = "<source>",
        checks: Optional[str] = None,
        compilation_database_dir: Optional[str] = None,
    ) -> ToolExecutionResult:
        """
        Run clang-tidy static analysis for security, bugprone, and performance checks.
        """
        exe_path = self.find_executable("clang-tidy")
        if not exe_path:
            return ToolExecutionResult(
                tool_name="clang-tidy",
                status=ToolStatus.UNAVAILABLE,
                error_message="clang-tidy executable was not found on PATH.",
                limitations=["clang-tidy not available in system environment."],
            )

        active_checks = checks or self.DEFAULT_CLANG_TIDY_CHECKS
        is_cpp = self._is_cpp_file(file_path, source_code)

        with tempfile.TemporaryDirectory() as tmpdir:
            ext = ".cpp" if is_cpp else ".c"
            src_file = os.path.join(tmpdir, f"source{ext}")
            with open(src_file, "w", encoding="utf-8") as f:
                f.write(source_code)

            cmd = [exe_path, f"-checks={active_checks}", src_file]
            limitations = []

            if compilation_database_dir and os.path.isfile(os.path.join(compilation_database_dir, "compile_commands.json")):
                cmd.extend(["-p", compilation_database_dir])
            else:
                std_flag = "-std=c++17" if is_cpp else "-std=c11"
                cmd.extend(["--", std_flag])
                limitations.append("No compilation database found; used fallback compilation flags for clang-tidy.")

            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    shell=False,
                )
                raw = (proc.stdout or "") + (proc.stderr or "")
                findings = self._parse_clang_tidy_output(raw, file_path)

                if proc.returncode != 0 and not findings:
                    status = ToolStatus.FAILED
                    err_msg = "clang-tidy execution terminated with error."
                elif findings:
                    status = ToolStatus.FINDINGS
                    err_msg = None
                else:
                    status = ToolStatus.PASSED
                    err_msg = None

                return ToolExecutionResult(
                    tool_name="clang-tidy",
                    status=status,
                    findings=findings,
                    raw_output=raw,
                    error_message=err_msg,
                    exit_code=proc.returncode,
                    command=cmd,
                    limitations=limitations,
                )
            except subprocess.TimeoutExpired:
                return ToolExecutionResult(
                    tool_name="clang-tidy",
                    status=ToolStatus.INCONCLUSIVE,
                    error_message=f"clang-tidy timed out after {self.timeout}s.",
                    command=cmd,
                )
            except Exception as exc:
                return ToolExecutionResult(
                    tool_name="clang-tidy",
                    status=ToolStatus.FAILED,
                    error_message=str(exc),
                    command=cmd,
                )

    # ── Cppcheck Static Analysis ──────────────────────────────────────────────

    def run_cppcheck(
        self,
        source_code: str,
        file_path: str = "<source>",
    ) -> ToolExecutionResult:
        """
        Run Cppcheck static analyzer and extract machine-readable XML diagnostics.
        """
        exe_path = self.find_executable("cppcheck")
        if not exe_path:
            return ToolExecutionResult(
                tool_name="cppcheck",
                status=ToolStatus.UNAVAILABLE,
                error_message="cppcheck executable was not found on PATH.",
                limitations=["cppcheck not installed on this system."],
            )

        is_cpp = self._is_cpp_file(file_path, source_code)
        lang_flag = "c++" if is_cpp else "c"

        with tempfile.TemporaryDirectory() as tmpdir:
            ext = ".cpp" if is_cpp else ".c"
            src_file = os.path.join(tmpdir, f"source{ext}")
            with open(src_file, "w", encoding="utf-8") as f:
                f.write(source_code)

            cmd = [
                exe_path,
                f"--language={lang_flag}",
                "--enable=warning,style,performance,portability",
                "--inconclusive",
                "--xml",
                "--xml-version=2",
                src_file,
            ]

            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    shell=False,
                )
                xml_out = proc.stderr or proc.stdout
                findings = self._parse_cppcheck_xml(xml_out, file_path)

                if proc.returncode != 0 and not findings:
                    status = ToolStatus.FAILED
                    err_msg = "cppcheck failed to execute."
                elif findings:
                    status = ToolStatus.FINDINGS
                    err_msg = None
                else:
                    status = ToolStatus.PASSED
                    err_msg = None

                return ToolExecutionResult(
                    tool_name="cppcheck",
                    status=status,
                    findings=findings,
                    raw_output=xml_out,
                    error_message=err_msg,
                    exit_code=proc.returncode,
                    command=cmd,
                )
            except subprocess.TimeoutExpired:
                return ToolExecutionResult(
                    tool_name="cppcheck",
                    status=ToolStatus.INCONCLUSIVE,
                    error_message=f"cppcheck timed out after {self.timeout}s.",
                    command=cmd,
                )
            except Exception as exc:
                return ToolExecutionResult(
                    tool_name="cppcheck",
                    status=ToolStatus.FAILED,
                    error_message=str(exc),
                    command=cmd,
                )

    # ── Sanitizer Instrumentation (ASan & UBSan) ──────────────────────────────

    def run_sanitizers(
        self,
        source_code: str,
        file_path: str = "<source>",
        test_inputs: Optional[List[str]] = None,
    ) -> Dict[str, ToolExecutionResult]:
        """
        Build and execute runtime instrumented candidate with AddressSanitizer and UndefinedBehaviorSanitizer.
        Returns separate execution results for ASan and UBSan.
        """
        results: Dict[str, ToolExecutionResult] = {}
        is_cpp = self._is_cpp_file(file_path, source_code)

        # Look for clang++/clang, or fallback g++/gcc with sanitizer support
        compiler = self.find_executable("clang++" if is_cpp else "clang")
        if not compiler:
            compiler = self.find_executable("g++" if is_cpp else "gcc")

        if not compiler:
            unavail_asan = ToolExecutionResult(
                tool_name="asan",
                status=ToolStatus.UNAVAILABLE,
                error_message="No compatible compiler found for AddressSanitizer runtime instrumentation.",
                limitations=["Sanitizer runtime requires clang or gcc."],
            )
            unavail_ubsan = ToolExecutionResult(
                tool_name="ubsan",
                status=ToolStatus.UNAVAILABLE,
                error_message="No compatible compiler found for UBSan runtime instrumentation.",
                limitations=["Sanitizer runtime requires clang or gcc."],
            )
            return {"asan": unavail_asan, "ubsan": unavail_ubsan}

        # Check whether code contains a main function to execute
        if not re.search(r'\bmain\s*\(', source_code):
            skip_msg = "Code does not contain an executable main() entry point; runtime sanitizer skipped."
            results["asan"] = ToolExecutionResult(
                tool_name="asan",
                status=ToolStatus.SKIPPED,
                error_message=skip_msg,
                limitations=[skip_msg],
            )
            results["ubsan"] = ToolExecutionResult(
                tool_name="ubsan",
                status=ToolStatus.SKIPPED,
                error_message=skip_msg,
                limitations=[skip_msg],
            )
            return results

        # Attempt to build and run ASan and UBSan
        for sanitizer, sname in [("address", "asan"), ("undefined", "ubsan")]:
            res = self._build_and_run_sanitizer(
                compiler=compiler,
                sanitizer_flag=f"-fsanitize={sanitizer}",
                sname=sname,
                source_code=source_code,
                file_path=file_path,
                is_cpp=is_cpp,
                test_inputs=test_inputs or [""],
            )
            results[sname] = res

        return results

    def _build_and_run_sanitizer(
        self,
        compiler: str,
        sanitizer_flag: str,
        sname: str,
        source_code: str,
        file_path: str,
        is_cpp: bool,
        test_inputs: List[str],
    ) -> ToolExecutionResult:
        with tempfile.TemporaryDirectory() as tmpdir:
            ext = ".cpp" if is_cpp else ".c"
            src_file = os.path.join(tmpdir, f"source{ext}")
            bin_file = os.path.join(tmpdir, f"sanitizer_bin_{sname}.exe" if os.name == "nt" else f"sanitizer_bin_{sname}")

            with open(src_file, "w", encoding="utf-8") as f:
                f.write(source_code)

            compile_cmd = [compiler, sanitizer_flag, "-g", "-O1", src_file, "-o", bin_file]
            if is_cpp:
                compile_cmd.append("-std=c++17")

            try:
                cproc = subprocess.run(
                    compile_cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    shell=False,
                )
                if cproc.returncode != 0:
                    # Platform or compiler does not support this sanitizer
                    c_err = cproc.stderr or cproc.stdout
                    is_unsupported = any(
                        term in c_err.lower()
                        for term in ["unrecognized", "unsupported", "cannot find", "libasan", "libubsan"]
                    )
                    status = ToolStatus.UNAVAILABLE if is_unsupported else ToolStatus.FAILED
                    return ToolExecutionResult(
                        tool_name=sname,
                        status=status,
                        error_message=f"Sanitizer build failed: {c_err.strip()}",
                        raw_output=c_err,
                        exit_code=cproc.returncode,
                        command=compile_cmd,
                        limitations=[f"Platform compiler unable to link {sname} runtime."],
                    )

                # Binary built: run it with test inputs
                findings: List[Dict[str, Any]] = []
                raw_exec_outputs = []
                had_timeout = False
                had_abnormal_exit = False
                last_exit_code = 0

                for inp in test_inputs:
                    try:
                        rproc = subprocess.run(
                            [bin_file],
                            input=inp,
                            capture_output=True,
                            text=True,
                            timeout=self.timeout,
                            shell=False,
                        )
                        last_exit_code = rproc.returncode
                        combined = (rproc.stderr or "") + "\n" + (rproc.stdout or "")
                        raw_exec_outputs.append(combined)

                        if rproc.returncode != 0:
                            had_abnormal_exit = True

                        # Detect sanitizer crashes/reports
                        if "AddressSanitizer" in combined or "runtime error:" in combined or "sanitizer" in combined.lower():
                            detected_findings = self._parse_sanitizer_output(combined, file_path, sname)
                            findings.extend(detected_findings)
                    except subprocess.TimeoutExpired:
                        had_timeout = True
                        raw_exec_outputs.append(f"Execution timed out after {self.timeout}s.")

                final_raw = "\n---\n".join(raw_exec_outputs)
                err_msg = None
                if findings:
                    status = ToolStatus.FINDINGS
                elif had_timeout:
                    status = ToolStatus.INCONCLUSIVE
                    err_msg = f"{sname} target execution timed out."
                elif had_abnormal_exit:
                    status = ToolStatus.FAILED
                    err_msg = f"{sname} target process exited abnormally with code {last_exit_code}."
                else:
                    status = ToolStatus.PASSED

                return ToolExecutionResult(
                    tool_name=sname,
                    status=status,
                    findings=findings,
                    raw_output=final_raw,
                    error_message=err_msg,
                    exit_code=last_exit_code,
                    limitations=[
                        "Analyzed only executed paths with supplied test inputs; does not prove absence of all undefined behavior.",
                    ],
                )

            except subprocess.TimeoutExpired:
                return ToolExecutionResult(
                    tool_name=sname,
                    status=ToolStatus.INCONCLUSIVE,
                    error_message=f"{sname} build timed out.",
                    command=compile_cmd,
                )
            except Exception as exc:
                return ToolExecutionResult(
                    tool_name=sname,
                    status=ToolStatus.FAILED,
                    error_message=str(exc),
                    command=compile_cmd,
                )

    # ── Concurrent Static Orchestration ───────────────────────────────────────

    def run_all_tools_concurrently(
        self,
        source_code: str,
        file_path: str = "<source>",
        compilation_database_dir: Optional[str] = None,
        test_inputs: Optional[List[str]] = None,
    ) -> Dict[str, ToolExecutionResult]:
        """
        Run independent static tools concurrently (Clang, Clang-Tidy, Cppcheck),
        then run dynamic sanitizers (ASan, UBSan).
        Preserves isolated results and diagnostics.
        """
        results: Dict[str, ToolExecutionResult] = {}

        # 1. Concurrent static analyses
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_tool = {
                executor.submit(
                    self.run_clang_compiler, source_code, file_path, compilation_database_dir
                ): "compiler",
                executor.submit(
                    self.run_clang_tidy, source_code, file_path, None, compilation_database_dir
                ): "clang-tidy",
                executor.submit(
                    self.run_cppcheck, source_code, file_path
                ): "cppcheck",
            }

            for future in as_completed(future_to_tool):
                tool_label = future_to_tool[future]
                try:
                    res = future.result()
                    results[res.tool_name] = res
                except Exception as exc:
                    results[tool_label] = ToolExecutionResult(
                        tool_name=tool_label,
                        status=ToolStatus.FAILED,
                        error_message=f"Subprocess runner exception: {exc}",
                    )

        # 2. Dynamic sanitizers
        sanitizer_results = self.run_sanitizers(source_code, file_path, test_inputs)
        results.update(sanitizer_results)

        return results

    # ── Diagnostic Parsers ────────────────────────────────────────────────────

    def _parse_clang_diagnostics(
        self, raw: str, file_path: str, tool: str = "clang"
    ) -> List[Dict[str, Any]]:
        findings = []
        diag_re = re.compile(
            r"^(?:.*?):(\d+):(\d+):\s+(warning|error|fatal error):\s+(.*?)(?:\s+\[-(W.*?)\])?$",
            re.MULTILINE,
        )
        for m in diag_re.finditer(raw):
            line_no = int(m.group(1))
            col_no = int(m.group(2))
            level = m.group(3)
            msg = m.group(4).strip()
            warn_flag = m.group(5) or "compiler-diagnostic"

            sev = "high" if "error" in level else "medium"
            findings.append(Finding(
                type=f"{tool}_{warn_flag}",
                category="correctness",
                description=msg,
                severity=sev,
                confidence=0.95,
                source_tool=tool,
                file_path=file_path,
                line=line_no,
                column=col_no,
                evidence=f"{level}: {msg}",
                recommendation="Fix compiler warning or syntax diagnostic.",
                status="confirmed" if "error" in level else "potential",
                is_confirmed=("error" in level),
                raw_diagnostic=m.group(0),
            ).to_dict())
        return findings

    def _parse_clang_tidy_output(self, raw: str, file_path: str) -> List[Dict[str, Any]]:
        findings = []
        pattern = re.compile(
            r"^(?:.*?):(\d+):(\d+):\s+(warning|error):\s+(.*?)\s+\[([^\]]+)\]$",
            re.MULTILINE,
        )
        for m in pattern.finditer(raw):
            line_no = int(m.group(1))
            col_no = int(m.group(2))
            level = m.group(3)
            msg = m.group(4).strip()
            check_name = m.group(5).strip()

            cat = "correctness"
            if "cert" in check_name or "security" in check_name or "overflow" in check_name:
                cat = "security"
            elif "performance" in check_name:
                cat = "performance"
            elif "modernize" in check_name:
                cat = "quality"

            sev = "high" if level == "error" or cat == "security" else "medium"

            findings.append(Finding(
                type=check_name,
                category=cat,
                description=msg,
                severity=sev,
                confidence=0.90,
                source_tool="clang-tidy",
                file_path=file_path,
                line=line_no,
                column=col_no,
                evidence=f"[{check_name}] {msg}",
                recommendation=f"Resolve {check_name} finding.",
                status="potential",
                is_confirmed=False,
                raw_diagnostic=m.group(0),
            ).to_dict())
        return findings

    def _parse_cppcheck_xml(self, xml_str: str, file_path: str) -> List[Dict[str, Any]]:
        findings = []
        if not xml_str or "<results" not in xml_str:
            return findings

        try:
            root = ET.fromstring(xml_str)
            for err in root.iter("error"):
                err_id = err.get("id", "cppcheck_finding")
                severity = err.get("severity", "warning")
                msg = err.get("msg", "")
                cwe = err.get("cwe")
                cwe_id = f"CWE-{cwe}" if cwe else None

                loc = err.find("location")
                line_no = int(loc.get("line")) if loc is not None and loc.get("line") else None
                col_no = int(loc.get("column")) if loc is not None and loc.get("column") else None

                cat = "security" if severity in ("error", "warning") and cwe_id else "correctness"
                norm_sev = "high" if severity == "error" else "medium" if severity == "warning" else "low"

                findings.append(Finding(
                    type=err_id,
                    category=cat,
                    description=msg,
                    severity=norm_sev,
                    confidence=0.85,
                    source_tool="cppcheck",
                    file_path=file_path,
                    line=line_no,
                    column=col_no,
                    evidence=f"[{err_id}] {msg}",
                    recommendation="Review Cppcheck diagnostic and apply safe bounds or initialization.",
                    cwe_id=cwe_id,
                    status="potential",
                    is_confirmed=False,
                    raw_diagnostic=msg,
                ).to_dict())
        except Exception as exc:
            logger.warning(f"Failed to parse Cppcheck XML: {exc}")
        return findings

    def _parse_sanitizer_output(self, raw: str, file_path: str, tool: str) -> List[Dict[str, Any]]:
        findings = []
        # Match lines like: runtime error: load of misaligned address... or ERROR: AddressSanitizer: heap-buffer-overflow
        for line in raw.splitlines():
            line_clean = line.strip()
            if "AddressSanitizer:" in line_clean or "runtime error:" in line_clean:
                findings.append(Finding(
                    type=f"{tool}_runtime_violation",
                    category="security" if tool == "asan" else "correctness",
                    description=line_clean,
                    severity="critical" if tool == "asan" else "high",
                    confidence=1.0,
                    source_tool=tool,
                    file_path=file_path,
                    evidence=line_clean,
                    recommendation=f"Fix runtime memory violation reported by {tool.upper()}.",
                    status="confirmed",
                    is_confirmed=True,
                    raw_diagnostic=line_clean,
                ).to_dict())
        return findings

    @staticmethod
    def _is_cpp_file(file_path: str, code: str) -> bool:
        ext = os.path.splitext(file_path)[1].lower()
        if ext in (".cpp", ".cxx", ".cc", ".hpp", ".hxx"):
            return True
        if ext == ".c":
            return False
        # Heuristic inspection
        if "#include <iostream>" in code or "#include <vector>" in code or "std::" in code or "namespace " in code or "class " in code:
            return True
        return True
