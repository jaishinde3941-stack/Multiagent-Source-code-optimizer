"""
src/logger_config.py
────────────────────
Call setup_logging() once at program start (from run_pipeline.py or tests).
Every module then does:
    import logging
    logger = logging.getLogger(__name__)
and logging flows through automatically.

Log levels
──────────
  DEBUG   – very fine detail (LLM raw responses, regex matches, Z3 model)
  INFO    – one line per major step (default for normal use)
  WARNING – recoverable problems (LLM unavailable, Z3 skipped)
  ERROR   – step failures
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime

# ── Colour codes (work on Windows 10+ / ANSI terminals) ─────────────────────
_COLOURS = {
    "DEBUG":    "\033[94m",   # bright blue
    "INFO":     "\033[92m",   # bright green
    "WARNING":  "\033[93m",   # yellow
    "ERROR":    "\033[91m",   # red
    "CRITICAL": "\033[95m",   # magenta
    "RESET":    "\033[0m",
}


class _ColouredFormatter(logging.Formatter):
    """Console formatter: coloured level + clean message."""

    FMT = "{colour}[{level:<7}]{reset} {dim}{name:<35}{reset}  {msg}"

    def format(self, record: logging.LogRecord) -> str:
        colour = _COLOURS.get(record.levelname, "")
        reset  = _COLOURS["RESET"]
        dim    = "\033[2m"   # dim for the module name

        # Shorten module path: src.agents.analysis_agent → analysis_agent
        short_name = record.name.split(".")[-1] if "." in record.name else record.name

        ts = datetime.fromtimestamp(record.created).strftime("%H:%M:%S.%f")[:-3]

        base = (
            f"{dim}{ts}{reset}  "
            f"{colour}[{record.levelname:<7}]{reset}  "
            f"{dim}{short_name:<28}{reset}  "
            f"{record.getMessage()}"
        )

        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


class _FileFormatter(logging.Formatter):
    """Plain formatter for the log file (no colour codes)."""

    FMT = "%(asctime)s  %(levelname)-8s  %(name)-40s  %(message)s"
    DATEFMT = "%Y-%m-%d %H:%M:%S"

    def __init__(self):
        super().__init__(fmt=self.FMT, datefmt=self.DATEFMT)


# ── Public API ────────────────────────────────────────────────────────────────

def setup_logging(
    level: str = "INFO",
    log_file: str = "pipeline.log",
    log_dir: str = None,
) -> str:
    """
    Configure root logger: console (coloured) + rotating file.

    Parameters
    ----------
    level    : "DEBUG" | "INFO" | "WARNING" | "ERROR"
    log_file : filename for the log file
    log_dir  : directory to write the log file (default: project root / logs/)

    Returns
    -------
    Absolute path to the log file.
    """
    # Enable ANSI on Windows
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleMode(
                ctypes.windll.kernel32.GetStdHandle(-11), 7
            )
        except Exception:
            pass

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Resolve log file path
    if log_dir is None:
        log_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "logs",
        )
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, log_file)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)  # always capture everything at root; handlers filter

    # Remove any handlers already attached (idempotent)
    root.handlers.clear()

    # ── Console handler ───────────────────────────────────────────────────────
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(numeric_level)
    console.setFormatter(_ColouredFormatter())
    root.addHandler(console)

    # ── File handler (rotating, max 5 MB × 3 backups) ────────────────────────
    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)   # always log everything to file
    file_handler.setFormatter(_FileFormatter())
    root.addHandler(file_handler)

    # Suppress overly chatty third-party modules
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        f"Logging ready  [console={level}]  [file={log_path}]"
    )
    return log_path
