"""
run_agent.py — Run a single agent independently
================================================
Run any one of the four pipeline agents on its own, without the full pipeline.

Commands
--------
  python run_agent.py analyze  <file.cpp>  [--no-llm] [-v|-q]
  python run_agent.py optimize <file.cpp>  [--no-llm] [-v|-q]
  python run_agent.py verify   <file.cpp>  [--optimized <opt.cpp>]  [-v|-q]
  python run_agent.py security <file.cpp>  [--optimized <opt.cpp>]  [--no-llm] [-v|-q]

Notes
-----
• 'optimize' automatically runs a quick analysis first (needed for context).
• 'verify'   requires --optimized pointing to the already-optimised file,
             or it will try to find OPT_<basename> in
             MicroBenchmarks/Generated_optimisation/ automatically.
• 'security' scans a single file for vulnerabilities when --optimized is
             omitted.  When --optimized is given it performs a differential
             security audit and reports only NEW vulnerabilities introduced
             by the optimization.  Auto-detection of OPT_* files works the
             same way as in 'verify'.
• For the full 4-agent pipeline  →  run_pipeline.py
• For a focused optimizer-only shortcut  →  run_optimizer.py
"""

import argparse
import logging
import os
import sys

# ── UTF-8 / ANSI setup (Windows) ──────────────────────────────────────────────
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUNBUFFERED", "1")
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.logger_config import setup_logging
from agent_framework import ContextManager
from src.llm.llm_client import LLMClient, make_llm_client
from src.agents.analysis_agent import AnalysisAgent
from src.agents.optimization_agent import OptimizationAgent
from src.agents.verification_agent import VerificationAgent
from src.agents.security_agent import SecurityAgent

# ── Colours ───────────────────────────────────────────────────────────────────
R       = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
CYAN    = "\033[96m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
RED     = "\033[91m"
MAGENTA = "\033[95m"


def _enable_ansi():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleMode(
                ctypes.windll.kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass


def _c(text, colour):
    return f"{colour}{text}{R}"


def _banner(title, width=64, colour=CYAN):
    print(_c("─" * width, colour))
    print(_c(f"  {title}", BOLD))
    print(_c("─" * width, colour))


def _section(title, colour=CYAN):
    print(f"\n{colour}{BOLD}▶  {title}{R}")
    print(_c("  " + "·" * 50, DIM))


def _read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _disable_llm(*agents):
    for ag in agents:
        ag.llm._available = False


# ── Sub-command: analyze ──────────────────────────────────────────────────────

def cmd_analyze(args):
    file_path = os.path.abspath(args.file)
    if not os.path.isfile(file_path):
        print(_c(f"\n  [ERROR] File not found: {file_path}", RED))
        sys.exit(1)

    source = _read_file(file_path)
    context = ContextManager()
    llm = make_llm_client(getattr(args, "llm", "ollama"))
    agent = AnalysisAgent("analysis_1", context, llm)

    if args.no_llm:
        agent.llm._available = False
        print(_c("  [LLM] Disabled via --no-llm", YELLOW))

    _section("Running Analysis Agent")
    result = agent.process({"source_code": source, "file_path": file_path})

    _banner("ANALYSIS RESULT")
    findings = result.get("all_findings", [])
    print(f"\n  File      : {_c(file_path, BOLD)}")
    print(f"  Findings  : {_c(str(len(findings)), YELLOW + BOLD)}")
    print(f"  Confidence: {result.get('confidence', 0):.0%}")
    print(f"  Conclusion: {result.get('conclusion', '')}")

    if findings:
        print()
        sev_col = {"high": RED, "medium": YELLOW, "low": GREEN}
        for i, f in enumerate(findings, 1):
            sev = f.get("severity", "?")
            col = sev_col.get(sev, DIM)
            ln  = f"  [line {f['line']}]" if f.get("line") else ""
            print(f"  {DIM}{i}.{R} {col}[{sev.upper()}]{ln}{R}"
                  f"  {f.get('type','?')}  —  {f.get('description','')}")
    else:
        print(f"\n  {GREEN}No issues found.{R}")

    print()
    return result


# ── Sub-command: optimize ─────────────────────────────────────────────────────

def cmd_optimize(args):
    file_path = os.path.abspath(args.file)
    if not os.path.isfile(file_path):
        print(_c(f"\n  [ERROR] File not found: {file_path}", RED))
        sys.exit(1)

    source  = _read_file(file_path)
    context = ContextManager()
    llm     = make_llm_client(getattr(args, "llm", "ollama"))

    analysis_agent     = AnalysisAgent("analysis_1", context, llm)
    optimization_agent = OptimizationAgent("optimization_1", context, llm)

    if args.no_llm:
        _disable_llm(analysis_agent, optimization_agent)
        print(_c("  [LLM] Disabled via --no-llm", YELLOW))

    # Step 1 – quick analysis (needed to guide optimizer)
    _section("Step 1/2 — Analysis Agent  (collecting context for optimizer)")
    analysis_result = analysis_agent.process({"source_code": source, "file_path": file_path})

    n_findings = len(analysis_result.get("all_findings", []))
    print(f"\n  Findings : {_c(str(n_findings), YELLOW + BOLD)}")

    # Step 2 – optimize
    _section("Step 2/2 — Optimization Agent")
    opt_result = optimization_agent.process({
        "source_code":     source,
        "file_path":       file_path,
        "analysis_report": analysis_result,
    })

    _banner("OPTIMIZATION RESULT")
    transforms = opt_result.get("transformations", [])
    out_file   = opt_result.get("output_file", "")
    diff       = opt_result.get("unified_diff", "")

    print(f"\n  File           : {_c(file_path, BOLD)}")
    print(f"  Transformations: {_c(str(len(transforms)), YELLOW + BOLD)}")
    print(f"  Confidence     : {opt_result.get('confidence', 0):.0%}")
    print(f"  Conclusion     : {opt_result.get('conclusion', '')}")

    if transforms:
        print()
        for i, t in enumerate(transforms, 1):
            print(f"  {DIM}{i}.{R} {t.get('type','?')}  —  {t.get('description','')}")

    if diff:
        print(f"\n{CYAN}--- Unified Diff (first 60 lines) ---{R}")
        for line in diff.splitlines()[:60]:
            if line.startswith("+"):
                print(_c(line, GREEN))
            elif line.startswith("-"):
                print(_c(line, RED))
            elif line.startswith("@@"):
                print(_c(line, CYAN))
            else:
                print(_c(line, DIM))
        if len(diff.splitlines()) > 60:
            print(_c(f"  … (truncated — {len(diff.splitlines())} lines total)", DIM))

    if out_file:
        print(f"\n  {GREEN}Optimized file saved →  {out_file}{R}")
    print()
    return opt_result


# ── Sub-command: verify ───────────────────────────────────────────────────────

def cmd_verify(args):
    orig_path = os.path.abspath(args.file)
    if not os.path.isfile(orig_path):
        print(_c(f"\n  [ERROR] File not found: {orig_path}", RED))
        sys.exit(1)

    # Locate optimized file
    if args.optimized:
        opt_path = os.path.abspath(args.optimized)
    else:
        # Try to auto-find OPT_<basename> in Generated_optimisation/
        basename = os.path.basename(orig_path)
        candidate = os.path.normpath(os.path.join(
            os.path.dirname(orig_path), "..", "..",
            "MicroBenchmarks", "Generated_optimisation",
            "OPT_" + basename,
        ))
        if os.path.isfile(candidate):
            opt_path = candidate
            print(_c(f"  [AUTO] Found optimized file: {opt_path}", DIM))
        else:
            print(_c(
                f"\n  [ERROR] No --optimized file given and auto-detect failed.\n"
                f"  Expected: {candidate}\n"
                f"  Run 'python run_agent.py optimize {args.file}' first.",
                RED,
            ))
            sys.exit(1)

    if not os.path.isfile(opt_path):
        print(_c(f"\n  [ERROR] Optimized file not found: {opt_path}", RED))
        sys.exit(1)

    original  = _read_file(orig_path)
    optimized = _read_file(opt_path)

    context = ContextManager()
    llm     = make_llm_client(getattr(args, "llm", "ollama"))
    agent   = VerificationAgent("verification_1", context, llm)

    _section("Running Verification Agent  (4 layers)")
    ver_result = agent.process({
        "original_code":  original,
        "optimized_code": optimized,
        "file_path":      orig_path,
    })

    status     = ver_result.get("status", "?")
    status_col = {"PASS": GREEN, "FAIL": RED, "ROLLBACK": RED}.get(status, YELLOW)

    _banner("VERIFICATION RESULT")
    print(f"\n  Original  : {_c(orig_path, BOLD)}")
    print(f"  Optimized : {_c(opt_path, BOLD)}")
    print(f"\n  Status           : {_c(status, status_col + BOLD)}")
    print(f"  Differential Test: "
          f"{_c('PASS', GREEN) if ver_result.get('diff_passed') else _c('FAIL', RED)}")
    print(f"  Z3 Equivalence   : {ver_result.get('z3_status', 'N/A')}")
    print(f"  Performance      : {ver_result.get('perf_summary', 'N/A')}")
    print(f"  LLM Verdict      : {ver_result.get('llm_verdict', 'N/A')}")
    print(f"  Conclusion       : {ver_result.get('conclusion', '')}")

    if status == "ROLLBACK":
        print(_c("\n  ⚠  Context rolled back — original code is preserved.", RED))

    print()
    return ver_result


# ── Sub-command: security ─────────────────────────────────────────────────────

def cmd_security(args):
    orig_path = os.path.abspath(args.file)
    if not os.path.isfile(orig_path):
        print(_c(f"\n  [ERROR] File not found: {orig_path}", RED))
        sys.exit(1)

    # ── Locate optimized file (optional) ──────────────────────────────────────
    differential = False
    opt_path     = None

    if args.optimized:
        opt_path     = os.path.abspath(args.optimized)
        differential = True
        if not os.path.isfile(opt_path):
            print(_c(f"\n  [ERROR] Optimized file not found: {opt_path}", RED))
            sys.exit(1)
    else:
        # Try auto-detect OPT_<basename> in Generated_optimisation/
        basename  = os.path.basename(orig_path)
        candidate = os.path.normpath(os.path.join(
            os.path.dirname(orig_path), "..", "..",
            "MicroBenchmarks", "Generated_optimisation",
            "OPT_" + basename,
        ))
        if os.path.isfile(candidate):
            opt_path     = candidate
            differential = True
            print(_c(f"  [AUTO] Found optimized file: {opt_path}", DIM))
        else:
            # Single-file mode — scan the file for vulnerabilities as-is
            opt_path     = orig_path
            differential = False
            print(_c("  [INFO] No optimized file found — scanning single file.", DIM))

    original  = _read_file(orig_path)
    optimized = _read_file(opt_path)

    context = ContextManager()
    llm     = make_llm_client(getattr(args, "llm", "ollama"))
    agent   = SecurityAgent("security_1", context, llm)

    if args.no_llm:
        agent.llm._available = False
        print(_c("  [LLM] Disabled via --no-llm", YELLOW))

    mode_label = "Differential Security Audit" if differential else "Security Scan"
    _section(f"Running Security Agent  — {mode_label}  (4 layers)")

    sec_result = agent.process({
        "original_code":  original,
        "optimized_code": optimized,
        "file_path":      orig_path,
    })

    status     = sec_result.get("status", "?")
    risk       = sec_result.get("overall_risk", "?").upper()
    all_vulns  = sec_result.get("all_vulnerabilities", [])
    new_vulns  = sec_result.get("new_vulnerabilities", [])
    sources    = sec_result.get("sources", [])

    status_col = {"PASS": GREEN, "ROLLBACK": RED}.get(status, YELLOW)
    risk_col   = {
        "CRITICAL": RED, "HIGH": RED,
        "MEDIUM": YELLOW, "LOW": GREEN, "NONE": GREEN,
    }.get(risk, DIM)

    _banner("SECURITY RESULT")
    print(f"\n  File          : {_c(orig_path, BOLD)}")
    if differential:
        print(f"  Optimized     : {_c(opt_path, BOLD)}")
    print(f"\n  Status        : {_c(status, status_col + BOLD)}")
    print(f"  Overall Risk  : {_c(risk, risk_col + BOLD)}")
    print(f"  Total findings: {_c(str(len(all_vulns)), YELLOW + BOLD)}")
    if differential:
        new_col = RED if new_vulns else GREEN
        print(f"  New (by opt.) : {_c(str(len(new_vulns)), new_col + BOLD)}")
    print(f"  Scan sources  : {', '.join(sources) or 'none'}")

    # ── All findings ──────────────────────────────────────────────────────────
    sev_col = {"high": RED, "medium": YELLOW, "low": GREEN}
    if all_vulns:
        title = "New vulnerabilities" if differential else "Vulnerabilities found"
        display = new_vulns if differential else all_vulns
        if display:
            print(f"\n  {BOLD}{title}:{R}")
            for i, v in enumerate(display, 1):
                sev  = v.get("severity", "?")
                col  = sev_col.get(sev, DIM)
                ln   = f"  [line {v['line']}]" if v.get("line") else ""
                cwe  = f"  {v['cwe_id']}" if v.get("cwe_id") else ""
                src  = f"  ({v.get('source', '?')})" if not differential else ""
                print(f"  {DIM}{i}.{R} {col}[{sev.upper()}]{ln}{cwe}{R}{src}"
                      f"  {v.get('type', '?')}  —  {v.get('description', '')}")
                rec = v.get("recommendation", "")
                if rec:
                    print(f"       {DIM}→ {rec}{R}")
        elif differential:
            print(f"\n  {GREEN}No new vulnerabilities introduced by the optimization.{R}")

        # In single-file mode, always show all findings
        if not differential and all_vulns:
            print(f"\n  {BOLD}All findings:{R}")
            for i, v in enumerate(all_vulns, 1):
                sev  = v.get("severity", "?")
                col  = sev_col.get(sev, DIM)
                ln   = f"  [line {v['line']}]" if v.get("line") else ""
                cwe  = f"  {v['cwe_id']}" if v.get("cwe_id") else ""
                src  = f"  ({v.get('source', '?')})"
                print(f"  {DIM}{i}.{R} {col}[{sev.upper()}]{ln}{cwe}{R}{src}"
                      f"  {v.get('type', '?')}  —  {v.get('description', '')}")
                rec = v.get("recommendation", "")
                if rec:
                    print(f"       {DIM}→ {rec}{R}")
    else:
        print(f"\n  {GREEN}No vulnerabilities found.{R}")

    # ── Rollback notice ───────────────────────────────────────────────────────
    if status == "ROLLBACK":
        triggers = sec_result.get("rollback_triggers", [])
        print(_c(
            f"\n  ⚠  ROLLBACK triggered — {len(triggers)} new HIGH-severity "
            "vulnerability(ies) introduced by the optimization.",
            RED,
        ))

    # ── Heuristic scores (verbose only) ───────────────────────────────────────
    scores = sec_result.get("heuristic_scores", {})
    if scores and getattr(args, "verbose", False):
        print(f"\n  {DIM}Heuristic scores:{R}")
        for signal, score in scores.items():
            bar = "█" * int(score * 20)
            print(f"    {signal:<30} {score:.2f}  {DIM}{bar}{R}")

    print()
    return sec_result


# ── Argument parser ───────────────────────────────────────────────────────────

def _add_common_flags(p, include_no_llm=True):
    """Add --verbose / --quiet / --llm (and optionally --no-llm) to a sub-parser."""
    p.add_argument("--verbose", "-v", action="store_true", help="DEBUG logging")
    p.add_argument("--quiet",   "-q", action="store_true", help="WARNING-only logging")
    if include_no_llm:
        p.add_argument("--no-llm", action="store_true", help="Skip LLM (rule-based only)")
        p.add_argument(
            "--llm", choices=["ollama", "gemini"], default="ollama",
            metavar="BACKEND",
            help="LLM backend: 'ollama' (Qwen, default) or 'gemini' (Google Gemini API)",
        )


def build_parser():
    parser = argparse.ArgumentParser(
        prog="run_agent.py",
        description="Run a single agent independently (analyze / optimize / verify)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_agent.py analyze  MicroBenchmarks/Testcases/TC01_uninit_arithmetic.cpp --no-llm
  python run_agent.py optimize MicroBenchmarks/Testcases/TC01_uninit_arithmetic.cpp --no-llm
  python run_agent.py verify   MicroBenchmarks/Testcases/TC01_uninit_arithmetic.cpp \\
        --optimized MicroBenchmarks/Generated_optimisation/OPT_TC01_uninit_arithmetic.cpp
  python run_agent.py security MicroBenchmarks/Testcases/TC48_format_string.cpp
  python run_agent.py security MicroBenchmarks/Testcases/TC48_format_string.cpp \\
        --optimized MicroBenchmarks/Generated_optimisation/OPT_TC48_format_string.cpp

Full pipeline  →  python run_pipeline.py <file>
Optimizer only →  python run_optimizer.py <file>
        """,
    )

    sub = parser.add_subparsers(dest="command", metavar="<command>")
    sub.required = True

    # --- analyze ---
    p_analyze = sub.add_parser("analyze", help="Run only the Analysis Agent")
    p_analyze.add_argument("file", help="C/C++ source file")
    _add_common_flags(p_analyze)

    # --- optimize ---
    p_optimize = sub.add_parser(
        "optimize",
        help="Run Analysis → Optimization (no verification pass)",
    )
    p_optimize.add_argument("file", help="C/C++ source file")
    _add_common_flags(p_optimize)

    # --- verify ---
    p_verify = sub.add_parser("verify", help="Run only the Verification Agent")
    p_verify.add_argument("file", help="Original C/C++ source file")
    p_verify.add_argument(
        "--optimized", metavar="OPT_FILE",
        help="Path to the optimized version (auto-detected if omitted)",
    )
    _add_common_flags(p_verify, include_no_llm=False)

    # --- security ---
    p_security = sub.add_parser(
        "security",
        help="Run only the Security Agent (scan a file, or diff original vs optimized)",
    )
    p_security.add_argument("file", help="C/C++ source file to scan")
    p_security.add_argument(
        "--optimized", metavar="OPT_FILE",
        help=(
            "Optimized file to compare against (auto-detected if omitted). "
            "When omitted the single file is scanned for vulnerabilities as-is."
        ),
    )
    _add_common_flags(p_security)

    return parser


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    _enable_ansi()
    parser = build_parser()
    args   = parser.parse_args()

    # Logging — read from sub-command args
    verbose = getattr(args, "verbose", False)
    quiet   = getattr(args, "quiet",   False)
    if verbose:
        level = "DEBUG"
    elif quiet:
        level = "WARNING"
    else:
        level = "INFO"
    setup_logging(level=level)

    print()
    _banner(f"AI COMPILER OPTIMIZATION — {args.command.upper()} AGENT")
    print()

    dispatch = {
        "analyze":  cmd_analyze,
        "optimize": cmd_optimize,
        "verify":   cmd_verify,
        "security": cmd_security,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
