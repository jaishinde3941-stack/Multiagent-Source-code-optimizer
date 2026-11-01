"""
run_optimizer.py — Dedicated Optimizer Agent Entry Point
=========================================================
Runs the Optimization Agent (with a quick Analysis pass for context).
NO verification step — for full E2E including verification use run_pipeline.py.

Usage
-----
  python run_optimizer.py <file.cpp>
  python run_optimizer.py MicroBenchmarks/Testcases/TC01_uninit_arithmetic.cpp
  python run_optimizer.py MicroBenchmarks/Testcases/TC11_buffer_overflow_loop.cpp --no-llm
  python run_optimizer.py MicroBenchmarks/Testcases/TC07_div_by_zero_var.cpp --out /tmp/out.cpp

Flags
-----
  --no-llm          Rule-based fixes only (faster, no Ollama needed)
  --out <path>      Custom path for the optimized output file
  --verbose / -v    DEBUG logging
  --quiet   / -q    WARNING-only logging

Related commands
----------------
  Full pipeline   →  python run_pipeline.py <file>
  Single agents   →  python run_agent.py analyze|optimize|verify <file>
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
from src.llm.llm_client import LLMClient
from src.agents.analysis_agent import AnalysisAgent
from src.agents.optimization_agent import OptimizationAgent

logger = logging.getLogger(__name__)

# ── Colours ───────────────────────────────────────────────────────────────────
R       = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
CYAN    = "\033[96m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
RED     = "\033[91m"


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


def _step(n, total, name):
    print(f"\n{_c(f'[{n}/{total}]', CYAN)}  {BOLD}{name}{R}")
    print(_c("  " + "·" * 50, DIM))


def main():
    _enable_ansi()

    parser = argparse.ArgumentParser(
        prog="run_optimizer.py",
        description="AI-Driven Compiler Optimization — Optimizer Agent only",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Runs Analysis → Optimization (no verification).
For the full 3-agent pipeline use: python run_pipeline.py <file>

Examples:
  python run_optimizer.py MicroBenchmarks/Testcases/TC01_uninit_arithmetic.cpp
  python run_optimizer.py MicroBenchmarks/Testcases/TC11_buffer_overflow_loop.cpp --no-llm
  python run_optimizer.py MicroBenchmarks/Testcases/TC07_div_by_zero_var.cpp -v
        """,
    )
    parser.add_argument("file",       help="C/C++ source file to optimize")
    parser.add_argument("--no-llm",   action="store_true",
                        help="Skip LLM — use rule-based fixes only (faster)")
    parser.add_argument("--out",      metavar="PATH", default=None,
                        help="Custom output path for the optimized file")
    parser.add_argument("--verbose",  "-v", action="store_true",
                        help="Enable DEBUG logging")
    parser.add_argument("--quiet",    "-q", action="store_true",
                        help="Only show warnings/errors")
    args = parser.parse_args()

    # ── Logging ────────────────────────────────────────────────────────────────
    if args.verbose:
        level = "DEBUG"
    elif args.quiet:
        level = "WARNING"
    else:
        level = "INFO"
    log_path = setup_logging(level=level)

    # ── Header ─────────────────────────────────────────────────────────────────
    print()
    _banner("AI COMPILER OPTIMIZATION — OPTIMIZER AGENT")

    file_path = os.path.abspath(args.file)
    print(f"\n  Target : {_c(file_path, BOLD)}")
    print(f"  Log    : {_c(log_path, DIM)}")
    print(f"  Mode   : {_c('rule-based only' if args.no_llm else 'full (LLM + rules)', YELLOW)}\n")

    if not os.path.isfile(file_path):
        logger.error(f"File not found: {file_path}")
        print(_c(f"\n  [ERROR] File not found: {file_path}", RED))
        sys.exit(1)

    with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
        source_code = fh.read()

    # ── Build agents ───────────────────────────────────────────────────────────
    context = ContextManager()
    llm     = LLMClient()

    analysis_agent     = AnalysisAgent("analysis_1", context, llm)
    optimization_agent = OptimizationAgent("optimization_1", context, llm)

    if args.no_llm:
        analysis_agent.llm._available     = False
        optimization_agent.llm._available = False
        print(_c("  [LLM] Disabled — rule-based mode", YELLOW))
    else:
        status = llm.health_check()
        if status.get("available"):
            print(_c(f"  [LLM] Connected → {status.get('model')}", GREEN))
        else:
            print(_c("  [LLM] Ollama not running — stub/rule-based fallback", YELLOW))

    # ── Step 1: Analysis ───────────────────────────────────────────────────────
    _step(1, 2, "Analysis Agent   — scanning for issues")
    logger.info("Step 1/2: Analysis")

    try:
        analysis_result = analysis_agent.process({
            "source_code": source_code,
            "file_path":   file_path,
        })
    except Exception as exc:
        logger.error(f"Analysis failed: {exc}")
        print(_c(f"\n  [ERROR] Analysis step failed: {exc}", RED))
        sys.exit(1)

    n_findings = len(analysis_result.get("all_findings", []))
    print(f"\n  → {_c(str(n_findings), YELLOW + BOLD)} finding(s) detected")

    # Show a compact list of findings
    sev_col = {"high": RED, "medium": YELLOW, "low": GREEN}
    for f in analysis_result.get("all_findings", []):
        sev = f.get("severity", "?")
        col = sev_col.get(sev, DIM)
        ln  = f"  [line {f['line']}]" if f.get("line") else ""
        print(f"    {col}[{sev.upper()}]{ln}{R}  {f.get('type','?')}")

    # ── Step 2: Optimization ───────────────────────────────────────────────────
    _step(2, 2, "Optimization Agent — applying transformations")
    logger.info("Step 2/2: Optimization")

    # Override output dir if --out given
    out_dir = None
    if args.out:
        out_dir = os.path.dirname(os.path.abspath(args.out))

    if out_dir:
        optimization_agent.output_dir = out_dir
        os.makedirs(out_dir, exist_ok=True)

    try:
        opt_result = optimization_agent.process({
            "source_code":     source_code,
            "file_path":       file_path,
            "analysis_report": analysis_result,
        })
    except Exception as exc:
        logger.error(f"Optimization failed: {exc}")
        print(_c(f"\n  [ERROR] Optimization step failed: {exc}", RED))
        sys.exit(1)

    # Rename output to the custom name if --out specified
    actual_out = opt_result.get("output_file", "")
    if args.out and actual_out and os.path.isfile(actual_out):
        target = os.path.abspath(args.out)
        try:
            os.replace(actual_out, target)
            actual_out = target
            opt_result["output_file"] = target
        except OSError as exc:
            logger.warning(f"Could not rename output file: {exc}")

    # ── Result ─────────────────────────────────────────────────────────────────
    transforms = opt_result.get("transformations", [])
    diff       = opt_result.get("unified_diff", "")

    print()
    _banner("OPTIMIZER RESULT")
    print(f"\n  File           : {_c(file_path, BOLD)}")
    print(f"  Findings found : {_c(str(n_findings), YELLOW + BOLD)}")
    print(f"  Transformations: {_c(str(len(transforms)), YELLOW + BOLD)}")
    print(f"  Confidence     : {opt_result.get('confidence', 0):.0%}")
    print(f"  Conclusion     : {opt_result.get('conclusion', '')}")

    if transforms:
        print()
        for i, t in enumerate(transforms, 1):
            print(f"  {DIM}{i}.{R}  {t.get('type','?')}  —  {t.get('description','')}")

    # Show diff
    if diff and diff.strip():
        print(f"\n{CYAN}--- Unified Diff ---{R}")
        diff_lines = diff.splitlines()
        for line in diff_lines[:80]:
            if line.startswith("+") and not line.startswith("+++"):
                print(_c(line, GREEN))
            elif line.startswith("-") and not line.startswith("---"):
                print(_c(line, RED))
            elif line.startswith("@@"):
                print(_c(line, CYAN))
            else:
                print(_c(line, DIM))
        if len(diff_lines) > 80:
            remaining = len(diff_lines) - 80
            print(_c(f"  … {remaining} more lines — see output file for full diff", DIM))
    else:
        print(f"\n  {DIM}No diff — code unchanged (no fixes found or applied){R}")

    if actual_out:
        print(f"\n  {GREEN}{BOLD}Optimized file saved →  {actual_out}{R}")
    else:
        print(f"\n  {YELLOW}Warning: output file not saved (check logs){R}")

    print(f"\n  Full log: {_c(log_path, DIM)}\n")
    logger.info("run_optimizer.py finished.")


if __name__ == "__main__":
    main()
