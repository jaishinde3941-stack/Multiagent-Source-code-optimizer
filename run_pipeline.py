"""
run_pipeline.py — CLI Entry Point for AI Compiler Optimization System

Usage:
    python run_pipeline.py <path/to/file.cpp>
    python run_pipeline.py MicroBenchmarks/Testcases/TC01_uninit_arithmetic.cpp
    python run_pipeline.py --verbose MicroBenchmarks/Testcases/TC11_buffer_overflow_loop.cpp
    python run_pipeline.py --no-llm MicroBenchmarks/Testcases/TC07_div_by_zero_var.cpp
    python run_pipeline.py --quiet MicroBenchmarks/Testcases/TC01_uninit_arithmetic.cpp
    python run_pipeline.py --no-security MicroBenchmarks/Testcases/TC01_uninit_arithmetic.cpp
"""

import argparse
import logging
import os
import sys

# Ensure UTF-8 output on Windows terminals
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

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.logger_config import setup_logging
from src.message_logger import MessageLogger
from src.pipeline.pipeline import CompilerOptimizationPipeline
from src.llm.llm_client import make_llm_client

logger = logging.getLogger(__name__)

_RESET  = "\033[0m"
_CYAN   = "\033[96m"
_GREEN  = "\033[92m"
_YELLOW = "\033[93m"
_RED    = "\033[91m"
_BOLD   = "\033[1m"
_DIM    = "\033[2m"


def _enable_ansi():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleMode(
                ctypes.windll.kernel32.GetStdHandle(-11), 7
            )
        except Exception:
            pass


def _c(text: str, code: str) -> str:
    return f"{code}{text}{_RESET}"


def _banner(msg: str, width: int = 60):
    print(_c("─" * width, _CYAN))
    print(_c(f"  {msg}", _BOLD))
    print(_c("─" * width, _CYAN))


def _step(n: int, total: int, name: str):
    """Print a big step header so it's easy to see where we are."""
    bar = _c(f"[{n}/{total}]", _CYAN)
    print(f"\n{bar}  {_BOLD}{name}{_RESET}")
    print(_c("  " + "·" * 50, _DIM))


def main():
    _enable_ansi()

    parser = argparse.ArgumentParser(
        description="AI-Driven Compiler Optimization System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Logging levels (default: INFO — shows every step):
  --verbose / -v   DEBUG   full detail incl. LLM prompts, regex hits
  (default)        INFO    one line per step (recommended)
  --quiet  / -q   WARNING  only warnings and errors

Log file: logs/pipeline.log  (always DEBUG level, regardless of console setting)

Examples:
  python run_pipeline.py MicroBenchmarks/Testcases/TC01_uninit_arithmetic.cpp
  python run_pipeline.py --verbose MicroBenchmarks/Testcases/TC11_buffer_overflow_loop.cpp
  python run_pipeline.py --no-llm MicroBenchmarks/Testcases/TC07_div_by_zero_var.cpp
        """,
    )
    parser.add_argument("file",      help="Path to C/C++ source file to analyse and optimise")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable DEBUG logging")
    parser.add_argument("--quiet",   "-q", action="store_true", help="Only show warnings/errors")
    parser.add_argument("--no-llm",      action="store_true", help="Skip LLM (rule-based only)")
    parser.add_argument("--no-security", action="store_true", help="Skip security audit (Step 4)")
    parser.add_argument(
        "--llm", choices=["ollama", "gemini"], default="ollama",
        metavar="BACKEND",
        help="LLM backend: 'ollama' (Qwen 2.5 Coder, default) or 'gemini' (Google Gemini API)",
    )
    parser.add_argument(
        "--show-messages", "-m", action="store_true",
        help="Show live inter-agent messages on stdout + summary table"
    )
    parser.add_argument(
        "--save-messages", metavar="FILE",
        default=None,
        help="Save all inter-agent messages as JSON to FILE (e.g. logs/messages.json)"
    )
    args = parser.parse_args()

    # ── Logging setup ──────────────────────────────────────────────────────────
    if args.verbose:
        console_level = "DEBUG"
    elif args.quiet:
        console_level = "WARNING"
    else:
        console_level = "INFO"     # ← default: shows every pipeline step

    log_path = setup_logging(level=console_level)

    # ── Header ─────────────────────────────────────────────────────────────────
    print()
    _banner("AI-DRIVEN COMPILER OPTIMIZATION SYSTEM")
    file_path = os.path.abspath(args.file)
    print(f"\n  Target : {_c(file_path, _BOLD)}")
    print(f"  Log    : {_c(log_path, _DIM)}")
    print(f"  Level  : {_c(console_level, _YELLOW)}\n")

    if not os.path.isfile(file_path):
        logger.error(f"File not found: {file_path}")
        print(_c(f"\n  [ERROR] File not found: {file_path}", _RED))
        sys.exit(1)

    # ── Build pipeline ─────────────────────────────────────────────────────────
    # Build MessageLogger first (before pipeline so it's wired in constructor)
    msg_logger = None
    if args.show_messages or args.save_messages:
        _need_msg_logger = True
    else:
        _need_msg_logger = False

    logger.info("Initialising pipeline agents …")
    llm_client = make_llm_client(args.llm)
    pipeline = CompilerOptimizationPipeline(
        llm_client=llm_client,
        enable_security=not args.no_security,
    )

    if args.no_llm:
        for agent in (pipeline.analysis_agent,
                      pipeline.optimization_agent,
                      pipeline.verification_agent,
                      pipeline.security_agent):
            if agent is not None:
                agent.llm._available = False
        logger.warning("LLM disabled — rule-based analysis only")
        print(_c("  [LLM] Disabled via --no-llm flag", _YELLOW))
    else:
        llm_status = pipeline.analysis_agent.llm.health_check()
        if llm_status.get("available"):
            backend_label = (
                f"Gemini API ({llm_status.get('model')})"
                if args.llm == "gemini"
                else f"Qwen 2.5 Coder ({llm_status.get('model')})"
            )
            logger.info(f"LLM online: {backend_label}")
            print(_c(f"  [LLM] {backend_label} — connected", _GREEN))
        else:
            if args.llm == "gemini":
                logger.warning("Gemini API unavailable — stub/rule-based mode")
                print(_c(
                    "  [LLM] Gemini API unavailable "
                    "(missing google-generativeai package or GEMINI_API_KEY) — stub mode",
                    _YELLOW,
                ))
            else:
                logger.warning("Ollama not running — using stub LLM fallback")
                print(_c("  [LLM] Ollama not running — stub/rule-based mode", _YELLOW))

    # Attach MessageLogger now that pipeline is built
    if _need_msg_logger:
        msg_logger = MessageLogger(
            pipeline.registry,
            show_payload=True,
            output_file=args.save_messages or None,
        )
        pipeline._msg_logger = msg_logger   # wire into pipeline._route()
        msg_logger.attach()                 # also hooks registry for any future use

    if args.no_security:
        pipeline.enable_security = False
        logger.warning("Security audit disabled via --no-security")
        print(_c("  [Security] Disabled via --no-security flag", _YELLOW))

    # ── Run ────────────────────────────────────────────────────────────────────
    total_steps = 3 if args.no_security else 4
    _step(1, total_steps, "Analysis Agent   — detecting bugs & inefficiencies")

    result = pipeline.run(file_path)

    if msg_logger:
        msg_logger.detach()
        msg_logger.print_summary()

    # Visual banners for the remaining steps (pipeline logs them internally too)
    _step(2, total_steps, "Optimization Agent — applying transformations")
    _step(3, total_steps, "Verification Agent — checking correctness & performance")
    if not args.no_security:
        _step(4, total_steps, "Security Agent     — vulnerability audit")

    # ── Result ─────────────────────────────────────────────────────────────────
    status_colour = {
        "success":         _GREEN,
        "partial":         _YELLOW,
        "rollback":        _RED,
        "failed":          _RED,
        "error":           _RED,
        "incomplete":      _YELLOW,
        "no_optimization": _YELLOW,
    }.get(result.status, "")

    print()
    _banner("PIPELINE RESULT")
    print(result.summary())
    print()
    print(_c(f"  Final Status : {result.status.upper()}", status_colour + _BOLD))

    if result.status == "success":
        out = result.optimization_report.get("output_file", "")
        if out:
            print(_c(f"\n  Optimised file saved to:\n    {out}", _GREEN))
    elif result.status == "rollback":
        print(_c("\n  Optimisation rolled back — original code is preserved.", _RED))

    # Security summary
    if result.security_report:
        risk    = result.security_report.get("overall_risk", "?").upper()
        n_new   = len(result.security_report.get("new_vulnerabilities", []))
        sec_st  = result.security_report.get("status", "?")
        risk_colour = _RED if risk in ("CRITICAL", "HIGH") else (
            _YELLOW if risk == "MEDIUM" else _GREEN
        )
        print(_c(f"\n  Security Risk : {risk} | New Vulns: {n_new} | "
                 f"Audit: {sec_st}", risk_colour))

    print(f"\n  Full log: {_c(log_path, _DIM)}\n")
    logger.info("run_pipeline.py finished.")


if __name__ == "__main__":
    main()
