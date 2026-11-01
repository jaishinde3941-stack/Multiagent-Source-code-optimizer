"""
src/message_logger.py
─────────────────────
Intercepts every message routed through AgentRegistry and logs/prints it
in a structured, colour-coded format.

Usage
-----
    from src.message_logger import MessageLogger
    msg_logger = MessageLogger(registry, show_payload=True)
    msg_logger.attach()        # monkey-patches registry.route_message
    ...run pipeline...
    msg_logger.detach()        # restores original route_message
    msg_logger.print_summary() # prints statistics at the end
"""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── ANSI colours ──────────────────────────────────────────────────────────────
_R  = "\033[0m"
_CYAN   = "\033[96m"
_GREEN  = "\033[92m"
_YELLOW = "\033[93m"
_BLUE   = "\033[94m"
_MAGENTA= "\033[95m"
_RED    = "\033[91m"
_BOLD   = "\033[1m"
_DIM    = "\033[2m"

# One colour per agent type
_AGENT_COLOURS = {
    "analysis":     _GREEN,
    "optimization": _YELLOW,
    "verification": _CYAN,
    "pipeline":     _MAGENTA,
    "unknown":      _DIM,
}

# One colour per message type
_TYPE_COLOURS = {
    "request":      _BLUE,
    "response":     _GREEN,
    "notification": _YELLOW,
}


def _enable_ansi():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleMode(
                ctypes.windll.kernel32.GetStdHandle(-11), 7
            )
        except Exception:
            pass


def _agent_colour(agent_id: str) -> str:
    for key, col in _AGENT_COLOURS.items():
        if key in agent_id.lower():
            return col
    return _DIM


def _truncate(text: str, max_len: int = 120) -> str:
    return text if len(text) <= max_len else text[:max_len] + "…"


class _MessageRecord:
    """Internal record of one intercepted message."""
    def __init__(self, msg):
        self.msg_id      = msg.message_id[:8]   # short form
        self.sender      = msg.sender_id
        self.receiver    = msg.receiver_id
        self.msg_type    = msg.message_type.value
        self.priority    = msg.priority.value
        self.corr_id     = (msg.correlation_id or "")[:8]
        self.timestamp   = datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]
        self.payload_keys = list((msg.payload or {}).keys())
        # Safe payload preview (strip large code blobs)
        preview = {}
        for k, v in (msg.payload or {}).items():
            if k in ("source_code", "original_code", "optimized_code"):
                lines = str(v).splitlines()
                preview[k] = f"<{len(lines)} lines>"
            elif k == "unified_diff":
                preview[k] = f"<diff {len(str(v))} chars>"
            elif isinstance(v, (dict, list)) and len(str(v)) > 200:
                preview[k] = f"<{type(v).__name__} …>"
            else:
                preview[k] = v
        self.payload_preview = preview


class MessageLogger:
    """
    Intercepts and logs all messages routed through an AgentRegistry.

    Parameters
    ----------
    registry     : AgentRegistry instance to patch
    show_payload : If True, print message payload keys + preview values
    output_file  : Optional path to write structured JSON message log
    """

    def __init__(self, registry, show_payload: bool = True,
                 output_file: Optional[str] = None):
        _enable_ansi()
        self.registry     = registry
        self.show_payload = show_payload
        self.output_file  = output_file
        self._records: List[_MessageRecord] = []
        self._original_route = None
        self._msg_count = 0

        # Open JSON log file if requested
        self._json_fh = None
        if output_file:
            os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
            self._json_fh = open(output_file, "w", encoding="utf-8")
            self._json_fh.write("[\n")

    # ── Attach / detach ────────────────────────────────────────────────────────

    def attach(self):
        """Monkey-patch registry.route_message to intercept every message."""
        self._original_route = self.registry.route_message

        def _intercepted_route(message):
            self._on_message(message)
            return self._original_route(message)

        self.registry.route_message = _intercepted_route
        logger.info("MessageLogger attached to AgentRegistry")
        print(f"\n{_DIM}{'─'*70}{_R}")
        print(f"{_BOLD}{_CYAN}  📡  Inter-Agent Message Bus — live feed{_R}")
        print(f"{_DIM}{'─'*70}{_R}\n")

    def detach(self):
        """Restore original route_message."""
        if self._original_route:
            self.registry.route_message = self._original_route
            self._original_route = None
        if self._json_fh:
            self._json_fh.write("\n]\n")
            self._json_fh.close()
            self._json_fh = None

    # ── Intercept ──────────────────────────────────────────────────────────────

    def _on_message(self, message):
        self._msg_count += 1
        rec = _MessageRecord(message)
        self._records.append(rec)

        # ── Console output ────────────────────────────────────────────────────
        sc = _agent_colour(rec.sender)
        rc = _agent_colour(rec.receiver)
        tc = _TYPE_COLOURS.get(rec.msg_type, _DIM)

        print(
            f"  {_DIM}#{self._msg_count:>3}  {rec.timestamp}{_R}  "
            f"{sc}{_BOLD}{rec.sender:<22}{_R}  "
            f"──{tc}[{rec.msg_type.upper():<12}]{_R}──▶  "
            f"{rc}{_BOLD}{rec.receiver:<22}{_R}  "
            f"{_DIM}id={rec.msg_id}{_R}"
            + (f"  {_DIM}corr={rec.corr_id}{_R}" if rec.corr_id else "")
        )

        if self.show_payload and rec.payload_preview:
            for k, v in rec.payload_preview.items():
                val_str = _truncate(str(v))
                print(f"         {_DIM}│  {_YELLOW}{k:<25}{_R}{_DIM}{val_str}{_R}")
            print()

        # ── Log to file ───────────────────────────────────────────────────────
        if self._json_fh:
            entry = {
                "seq":       self._msg_count,
                "timestamp": rec.timestamp,
                "sender":    rec.sender,
                "receiver":  rec.receiver,
                "type":      rec.msg_type,
                "priority":  rec.priority,
                "msg_id":    rec.msg_id,
                "corr_id":   rec.corr_id,
                "payload_keys": rec.payload_keys,
                "payload_preview": {
                    k: str(v) for k, v in rec.payload_preview.items()
                },
            }
            if self._msg_count > 1:
                self._json_fh.write(",\n")
            self._json_fh.write(json.dumps(entry, indent=2))
            self._json_fh.flush()

        logger.debug(
            f"MSG #{self._msg_count}: {rec.sender} → {rec.receiver} "
            f"[{rec.msg_type}] payload_keys={rec.payload_keys}"
        )

    # ── Summary ────────────────────────────────────────────────────────────────

    def print_summary(self):
        """Print a table of all messages exchanged after the run."""
        if not self._records:
            print(f"\n{_DIM}  No messages were exchanged.{_R}\n")
            return

        print(f"\n{_DIM}{'─'*70}{_R}")
        print(f"{_BOLD}{_CYAN}  Message Bus Summary  ({len(self._records)} messages){_R}")
        print(f"{_DIM}{'─'*70}{_R}")
        print(f"  {'#':<4} {'FROM':<22} {'TYPE':<14} {'TO':<22} {'PAYLOAD KEYS'}")
        print(f"  {_DIM}{'─'*4} {'─'*22} {'─'*14} {'─'*22} {'─'*20}{_R}")
        for i, r in enumerate(self._records, 1):
            tc = _TYPE_COLOURS.get(r.msg_type, _DIM)
            keys = ", ".join(r.payload_keys)[:30]
            print(
                f"  {_DIM}{i:<4}{_R} "
                f"{_agent_colour(r.sender)}{r.sender:<22}{_R} "
                f"{tc}{r.msg_type:<14}{_R} "
                f"{_agent_colour(r.receiver)}{r.receiver:<22}{_R} "
                f"{_DIM}{keys}{_R}"
            )
        print(f"\n  {_BOLD}Total messages:{_R} {len(self._records)}")

        # Route counts
        routes: Dict[str, int] = {}
        for r in self._records:
            key = f"{r.sender} → {r.receiver}"
            routes[key] = routes.get(key, 0) + 1
        print(f"  {_BOLD}Routes:{_R}")
        for route, count in sorted(routes.items(), key=lambda x: -x[1]):
            print(f"    {_DIM}{route:<45}{_R}  ×{count}")

        if self.output_file:
            print(f"\n  {_DIM}Full message log: {self.output_file}{_R}")
        print(f"{_DIM}{'─'*70}{_R}\n")
