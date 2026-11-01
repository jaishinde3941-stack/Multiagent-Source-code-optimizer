"""
watch_agents.py -- Real-time inter-agent message monitor
---------------------------------------------------------
Runs the full pipeline and prints EVERY message the agents exchange.

Usage:
    python watch_agents.py <file.cpp>
    python watch_agents.py MicroBenchmarks/Testcases/TC11_buffer_overflow_loop.cpp
    python watch_agents.py MicroBenchmarks/Testcases/TC01_uninit_arithmetic.cpp --full
    python watch_agents.py MicroBenchmarks/Testcases/TC05_uninit_struct.cpp --no-llm
"""

import argparse
import io
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any

# Force unbuffered UTF-8 on Windows terminals
import os as _os
_os.environ.setdefault("PYTHONIOENCODING", "utf-8")
_os.environ.setdefault("PYTHONUNBUFFERED", "1")
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
from src.pipeline.pipeline import CompilerOptimizationPipeline

# ---- Colours -----------------------------------------------------------------
R       = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
CYAN    = "\033[96m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
BLUE    = "\033[94m"
MAGENTA = "\033[95m"
RED     = "\033[91m"

AGENT_COL = {
    "pipeline":     MAGENTA,
    "analysis":     GREEN,
    "optimization": YELLOW,
    "verification": CYAN,
}

TYPE_COL = {
    "request":      BLUE,
    "response":     GREEN,
    "notification": YELLOW,
}

TYPE_LABEL = {
    "request":      ">> REQUEST     ",
    "response":     "<< RESPONSE    ",
    "notification": "!! NOTIFICATION",
}

# ---- Helpers -----------------------------------------------------------------

def _enable_ansi():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleMode(
                ctypes.windll.kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass


def _col(agent_id: str) -> str:
    for k, c in AGENT_COL.items():
        if k in agent_id.lower():
            return c
    return DIM


def _divider(char="-", width=68, colour=DIM):
    print(f"{colour}{char * width}{R}")


def _format_value(key: str, value: Any, show_full: bool) -> str:
    if key in ("source_code", "original_code", "optimized_code"):
        lines = str(value).splitlines()
        if show_full:
            return "\n" + "\n".join(lines)
        return f"{DIM}<{len(lines)} lines  --  run with --full to expand>{R}"
    if key == "unified_diff":
        s = str(value)
        if show_full or len(s) <= 300:
            return "\n" + s
        return f"\n{s[:300]}\n{DIM}... (run with --full to see all){R}"
    if isinstance(value, (dict, list)):
        dumped = json.dumps(value, indent=2)
        if show_full or len(dumped) <= 300:
            return "\n" + dumped
        return f"\n{dumped[:300]}\n{DIM}... (run with --full){R}"
    return str(value)


def _print_message(seq: int, msg, show_full: bool = False):
    ts   = datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]
    sc   = _col(msg.sender_id)
    rc   = _col(msg.receiver_id)
    tc   = TYPE_COL.get(msg.message_type.value, DIM)
    lbl  = TYPE_LABEL.get(msg.message_type.value, msg.message_type.value)
    corr = f"  corr={msg.correlation_id[:8]}" if msg.correlation_id else ""

    _divider()
    print(f"{DIM}#{seq:<3} {ts}{R}  {tc}{BOLD}{lbl}{R}  "
          f"{DIM}id={msg.message_id[:8]}{corr}{R}")
    print(f"  {sc}{BOLD}{msg.sender_id:<22}{R}  -->>  "
          f"{rc}{BOLD}{msg.receiver_id}{R}")
    print()

    payload = msg.payload or {}
    if not payload:
        print(f"  {DIM}(empty payload){R}")
    else:
        for key, value in payload.items():
            val_str = _format_value(key, value, show_full)
            if "\n" in val_str:
                print(f"  {YELLOW}{key}{R}")
                for line in val_str.splitlines():
                    print(f"    {DIM}{line}{R}")
            else:
                print(f"  {YELLOW}{key:<25}{R}  {val_str}")
    print()


# ---- Watcher class -----------------------------------------------------------

class _WatchLogger:
    def __init__(self, pipeline, show_full: bool = False):
        self.pipeline  = pipeline
        self.show_full = show_full
        self._seq      = 0
        self._records  = []
        self._original = None

    def attach(self):
        watcher = self
        _orig   = self.pipeline._route

        def _hooked(sender_id, receiver_id, msg_type, payload,
                    priority=None, corr_id=None):
            from agent_framework.message_protocol import Message, MessagePriority
            p = priority or MessagePriority.HIGH
            msg = Message.create(
                sender_id=sender_id,
                receiver_id=receiver_id,
                message_type=msg_type,
                payload=payload or {},
                priority=p,
                correlation_id=corr_id,
            )
            watcher._seq += 1
            watcher._records.append(msg)
            _print_message(watcher._seq, msg, watcher.show_full)
            return msg.message_id

        self.pipeline._route = _hooked
        self._original       = _orig

    def detach(self):
        if self._original:
            self.pipeline._route = self._original

    def print_summary(self):
        _divider("=", width=68, colour=CYAN)
        print(f"{BOLD}{CYAN}  MESSAGE SUMMARY  --  {len(self._records)} messages total{R}")
        _divider("=", width=68, colour=CYAN)
        print(f"  {'#':<4} {'TYPE':<16} {'FROM':<22}  -->>  {'TO'}")
        _divider(colour=DIM)
        for i, msg in enumerate(self._records, 1):
            tc = TYPE_COL.get(msg.message_type.value, DIM)
            sc = _col(msg.sender_id)
            rc = _col(msg.receiver_id)
            corr = f"  corr={msg.correlation_id[:8]}" if msg.correlation_id else ""
            print(
                f"  {DIM}{i:<4}{R}"
                f"{tc}{msg.message_type.value:<16}{R}"
                f"{sc}{msg.sender_id:<22}{R}  -->>  "
                f"{rc}{msg.receiver_id}{R}"
                f"{DIM}{corr}{R}"
            )
        _divider("=", width=68, colour=CYAN)


# ---- Main --------------------------------------------------------------------

def main():
    _enable_ansi()

    parser = argparse.ArgumentParser(
        description="watch_agents -- stream every inter-agent message to the terminal",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Shows every REQUEST / RESPONSE / NOTIFICATION the agents exchange.

Examples:
  python watch_agents.py MicroBenchmarks/Testcases/TC11_buffer_overflow_loop.cpp
  python watch_agents.py MicroBenchmarks/Testcases/TC01_uninit_arithmetic.cpp --full
  python watch_agents.py MicroBenchmarks/Testcases/TC05_uninit_struct.cpp --no-llm
        """
    )
    parser.add_argument("file",      help="C/C++ source file to process")
    parser.add_argument("--full",    action="store_true",
                        help="Show complete payload (including full source code and diffs)")
    parser.add_argument("--no-llm", action="store_true",
                        help="Skip LLM (faster, rule-based only)")
    args = parser.parse_args()

    setup_logging(level="WARNING")   # suppress INFO noise; messages shown inline

    file_path = os.path.abspath(args.file)
    if not os.path.isfile(file_path):
        print(f"{RED}[ERROR] File not found: {file_path}{R}")
        sys.exit(1)

    print()
    _divider("=", width=68, colour=CYAN)
    print(f"{BOLD}{CYAN}  AGENT MESSAGE WATCHER{R}")
    print(f"  {DIM}File : {file_path}{R}")
    print(f"  {DIM}Mode : {'rule-based only (--no-llm)' if args.no_llm else 'full pipeline'}{R}")
    print(f"  {DIM}View : {'FULL payloads' if args.full else 'summary  (--full to expand)'}{R}")
    _divider("=", width=68, colour=CYAN)
    print()

    pipeline = CompilerOptimizationPipeline()

    if args.no_llm:
        for agent in (pipeline.analysis_agent,
                      pipeline.optimization_agent,
                      pipeline.verification_agent):
            agent.llm._available = False

    watcher = _WatchLogger(pipeline, show_full=args.full)
    watcher.attach()

    result = pipeline.run(file_path)

    watcher.detach()
    watcher.print_summary()

    status_col = {"success": GREEN, "partial": YELLOW, "rollback": RED, "failed": RED}
    c = status_col.get(result.status, "")
    print()
    print(f"  {BOLD}Pipeline result:{R}  {c}{BOLD}{result.status.upper()}{R}")
    n_find = len(result.analysis_report.get("all_findings", []))
    n_xfrm = len(result.optimization_report.get("transformations", []))
    print(f"  {DIM}Findings: {n_find}    Transformations: {n_xfrm}{R}")
    out = result.optimization_report.get("output_file", "")
    if out:
        print(f"  {GREEN}Optimised file --> {out}{R}")
    print()


if __name__ == "__main__":
    main()
