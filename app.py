"""
app.py — Flask REST + Server-Sent Events backend for Compiler Optimization UI
==============================================================================
Run with:  python app.py
Then open: http://localhost:5173  (after running `npm run dev` in frontend/)
"""

from __future__ import annotations

import json
import logging
import os
import queue
import sys
import tempfile
import threading
import time
from datetime import datetime
from typing import Any, Dict, Optional

# ── Ensure project root is on sys.path ──────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from flask import Flask, Response, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ────────────────────────────────────────────────────────────────────────────
# Streaming infrastructure
# ────────────────────────────────────────────────────────────────────────────

class StreamQueue:
    """Thread-safe queue that feeds SSE events to the HTTP response."""

    def __init__(self) -> None:
        self._q: "queue.Queue[Optional[dict]]" = queue.Queue()

    def push(self, event_type: str, data: Any) -> None:
        self._q.put({
            "type": event_type,
            "data": data,
            "ts":   datetime.utcnow().isoformat(timespec="milliseconds"),
        })

    def close(self) -> None:
        """Send sentinel to signal end-of-stream."""
        self._q.put(None)

    def pop(self, timeout: float = 180.0) -> Optional[dict]:
        return self._q.get(timeout=timeout)


class _QueueLogHandler(logging.Handler):
    """Captures Python log records and forwards them to the StreamQueue."""

    def __init__(self, sq: StreamQueue) -> None:
        super().__init__()
        self._sq = sq

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._sq.push("log", {
                "level":   record.levelname,
                "logger":  record.name,
                "message": self.format(record),
            })
        except Exception:
            pass


class _QueueMessageLogger:
    """
    Drop-in replacement for src.message_logger.MessageLogger.

    The pipeline calls  self._msg_logger._on_message(msg)  for every
    inter-agent message.  We forward those messages as SSE events.
    """

    def __init__(self, sq: StreamQueue) -> None:
        self._sq    = sq
        self._count = 0

    def _on_message(self, message) -> None:
        self._count += 1

        # Build a safe, size-limited payload preview
        preview: Dict[str, Any] = {}
        for k, v in (message.payload or {}).items():
            if k in ("source_code", "original_code", "optimized_code"):
                preview[k] = f"<{len(str(v).splitlines())} lines>"
            elif k == "unified_diff":
                preview[k] = f"<diff {len(str(v))} chars>"
            elif isinstance(v, (dict, list)) and len(str(v)) > 200:
                preview[k] = f"<{type(v).__name__} …>"
            else:
                preview[k] = (
                    v if isinstance(v, (str, int, float, bool, type(None)))
                    else str(v)
                )

        self._sq.push("agent_message", {
            "seq":             self._count,
            "sender":          message.sender_id,
            "receiver":        message.receiver_id,
            "type":            message.message_type.value,
            "priority":        message.priority.value,
            "msg_id":          message.message_id[:8],
            "corr_id":         (message.correlation_id or "")[:8],
            "payload_keys":    list((message.payload or {}).keys()),
            "payload_preview": preview,
        })

    # pipeline may call this — keep it a no-op
    def print_summary(self) -> None:
        pass


# ────────────────────────────────────────────────────────────────────────────
# LLM factory
# ────────────────────────────────────────────────────────────────────────────

def _make_llm(use_llm: bool, backend: str = "ollama"):
    from src.llm.llm_client import make_llm_client
    client = make_llm_client(backend)
    if not use_llm:
        client._available = False
    return client


# ────────────────────────────────────────────────────────────────────────────
# Mode runners (each runs in a background thread)
# ────────────────────────────────────────────────────────────────────────────

def _run_full_pipeline(sq: StreamQueue, file_path: str, use_llm: bool) -> None:
    from src.pipeline.pipeline import CompilerOptimizationPipeline

    sq.push("status", {"phase": "pipeline_init", "message": "Initialising full 3-agent pipeline…"})
    msg_logger = _QueueMessageLogger(sq)
    llm        = _make_llm(use_llm)
    pipeline   = CompilerOptimizationPipeline(llm_client=llm, message_logger=msg_logger)

    sq.push("status", {"phase": "running", "message": "Running: Analysis -> Bounded Feedback Loop -> Security Audit"})
    result = pipeline.run(file_path)

    sq.push("analysis_result",     result.analysis_report)
    sq.push("optimization_result", result.optimization_report)
    sq.push("verification_result", result.verification_report)
    sq.push("security_result",     result.security_report)
    sq.push("pipeline_result", {
        "status": result.status,
        "error":  result.error,
        "summary": result.summary(),
        "iteration_count": result.iteration_count,
        "iteration_history": result.iteration_history,
        "initial_security_score": result.initial_security_score,
        "final_security_score": result.final_security_score,
        "score_change": result.score_change,
        "score_explanation": result.score_explanation,
    })


def _run_analyze_only(sq: StreamQueue, source_code: str, file_path: str, use_llm: bool) -> None:
    from src.agents.analysis_agent import AnalysisAgent
    from agent_framework import ContextManager

    sq.push("status", {"phase": "analysis_init", "message": "Initialising Analysis Agent…"})
    llm   = _make_llm(use_llm)
    ctx   = ContextManager()
    agent = AnalysisAgent("analysis_1", ctx, llm)

    sq.push("status", {"phase": "analysis_running", "message": "Running code analysis…"})
    result = agent.process({"source_code": source_code, "file_path": file_path})
    sq.push("analysis_result", result)
    sq.push("status", {
        "phase":   "analysis_done",
        "message": f"Analysis complete — {len(result.get('all_findings', []))} finding(s) found",
    })


def _run_optimize_only(sq: StreamQueue, source_code: str, file_path: str, use_llm: bool) -> None:
    from src.agents.analysis_agent import AnalysisAgent
    from src.agents.optimization_agent import OptimizationAgent
    from agent_framework import ContextManager

    llm = _make_llm(use_llm)
    ctx = ContextManager()

    sq.push("status", {"phase": "analysis_running", "message": "Step 1/2 — Running analysis…"})
    analysis_agent  = AnalysisAgent("analysis_1", ctx, llm)
    analysis_result = analysis_agent.process({"source_code": source_code, "file_path": file_path})
    sq.push("analysis_result", analysis_result)
    sq.push("status", {
        "phase":   "optimization_init",
        "message": f"Step 2/2 — Initialising Optimization Agent…",
    })

    opt_agent  = OptimizationAgent("optimization_1", ctx, llm)
    sq.push("status", {"phase": "optimization_running", "message": "Applying optimizations…"})
    opt_result = opt_agent.process({
        "source_code":     source_code,
        "file_path":       file_path,
        "analysis_report": analysis_result,
    })
    sq.push("optimization_result", opt_result)
    sq.push("status", {
        "phase":   "optimization_done",
        "message": f"Optimization complete — {len(opt_result.get('transformations', []))} transformation(s)",
    })


def _run_verify_only(sq: StreamQueue, source_code: str, file_path: str, use_llm: bool) -> None:
    from src.agents.analysis_agent import AnalysisAgent
    from src.agents.optimization_agent import OptimizationAgent
    from src.agents.verification_agent import VerificationAgent
    from agent_framework import ContextManager

    llm = _make_llm(use_llm)
    ctx = ContextManager()

    sq.push("status", {"phase": "analysis_running", "message": "Step 1/3 — Running analysis…"})
    analysis_result = AnalysisAgent("analysis_1", ctx, llm).process(
        {"source_code": source_code, "file_path": file_path}
    )
    sq.push("analysis_result", analysis_result)

    sq.push("status", {"phase": "optimization_running", "message": "Step 2/3 — Running optimization…"})
    opt_result = OptimizationAgent("optimization_1", ctx, llm).process({
        "source_code":     source_code,
        "file_path":       file_path,
        "analysis_report": analysis_result,
    })
    sq.push("optimization_result", opt_result)

    sq.push("status", {"phase": "verification_init", "message": "Step 3/3 — Initialising Verification Agent…"})
    ver_agent = VerificationAgent("verification_1", ctx, llm)

    sq.push("status", {"phase": "verification_running", "message": "Running 4-layer verification…"})
    ver_result = ver_agent.process({
        "original_code":  source_code,
        "optimized_code": opt_result.get("optimized_code", source_code),
        "file_path":      file_path,
    })
    sq.push("verification_result", ver_result)
    sq.push("status", {
        "phase":   "verification_done",
        "message": f"Verification complete — status: {ver_result.get('status', 'UNKNOWN')}",
    })


# ────────────────────────────────────────────────────────────────────────────
# Top-level worker (runs in background thread)
# ────────────────────────────────────────────────────────────────────────────

def _worker(sq: StreamQueue, source_code: str, mode: str,
            use_llm: bool, language: str, backend: str = "ollama") -> None:
    """Runs the requested pipeline mode; pushes all events into sq."""

    # Attach a log handler so Python loggers stream to the UI
    handler = _QueueLogHandler(sq)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter("%(name)s › %(message)s"))
    _watched_loggers = [
        logging.getLogger("src.pipeline.pipeline"),
        logging.getLogger("src.agents.analysis_agent"),
        logging.getLogger("src.agents.optimization_agent"),
        logging.getLogger("src.agents.verification_agent"),
        logging.getLogger("src.agents.security_agent"),
        logging.getLogger("src.analysis.tool_runner"),
        logging.getLogger("src.llm.llm_client"),
        logging.getLogger("src.verification.diff_tester"),
        logging.getLogger("src.verification.perf_benchmarker"),
        logging.getLogger("src.verification.z3_verifier"),
    ]
    for _lg in _watched_loggers:
        _lg.addHandler(handler)

    tmp_path: Optional[str] = None
    try:
        ext_map = {
            "cpp": ".cpp", "c": ".c",
            "python": ".py", "java": ".java", "go": ".go",
        }
        ext = ext_map.get(language, ".cpp")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=ext, delete=False, encoding="utf-8", prefix="ui_"
        ) as fh:
            fh.write(source_code)
            tmp_path = fh.name

        sq.push("status", {"phase": "init", "message": "Code written to temp file — starting…"})

        # Pre-warm: send a tiny ping to Ollama so the model is loaded
        # before the real pipeline request hits (avoids cold-start timeout)
        if use_llm:
            try:
                from src.llm.llm_client import LLMClient
                _warm = LLMClient()
                if _warm.is_available():
                    sq.push("status", {"phase": "warmup", "message": "Warming up LLM model (first run may take 1–2 min)…"})
                    _warm.generate("hi", max_tokens=1)
                    sq.push("status", {"phase": "warmup_done", "message": "LLM model ready."})
            except Exception:
                pass

        if mode == "pipeline":
            _run_full_pipeline(sq, tmp_path, use_llm)
        elif mode == "analyze":
            _run_analyze_only(sq, source_code, tmp_path, use_llm)
        elif mode == "optimize":
            _run_optimize_only(sq, source_code, tmp_path, use_llm)
        elif mode == "verify":
            _run_verify_only(sq, source_code, tmp_path, use_llm)
        else:
            sq.push("error", {"message": f"Unknown mode: {mode}"})

        sq.push("complete", {"status": "success"})

    except Exception as exc:
        import traceback
        sq.push("error", {
            "message":   str(exc),
            "traceback": traceback.format_exc(),
        })
        sq.push("complete", {"status": "error"})

    finally:
        for _lg in _watched_loggers:
            _lg.removeHandler(handler)
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        sq.close()


# ────────────────────────────────────────────────────────────────────────────
# Flask routes
# ────────────────────────────────────────────────────────────────────────────

@app.route("/api/health", methods=["GET"])
def health():
    try:
        from src.llm.llm_client import LLMClient, GeminiLLMClient
        ollama_info = LLMClient().health_check()
    except Exception as exc:
        ollama_info = {"available": False, "error": str(exc)}
    try:
        gemini_info = GeminiLLMClient().health_check()
    except Exception as exc:
        gemini_info = {"available": False, "error": str(exc)}
    return jsonify({"status": "ok", "ollama": ollama_info, "gemini": gemini_info})


@app.route("/api/stream", methods=["POST"])
def stream_endpoint():
    body     = request.get_json(silent=True) or {}
    code     = body.get("code", "").strip()
    mode     = body.get("mode", "pipeline")
    use_llm  = bool(body.get("use_llm", True))
    language = body.get("language", "cpp")
    backend  = body.get("backend", "ollama")

    if not code:
        return jsonify({"error": "No code provided"}), 400

    sq = StreamQueue()
    threading.Thread(
        target=_worker,
        args=(sq, code, mode, use_llm, language, backend),
        daemon=True,
    ).start()

    def generate():
        while True:
            try:
                item = sq.pop(timeout=180)
                if item is None:
                    yield "data: " + json.dumps({"type": "done"}) + "\n\n"
                    break
                yield "data: " + json.dumps(item, default=str) + "\n\n"
            except queue.Empty:
                yield "data: " + json.dumps({"type": "timeout"}) + "\n\n"
                break

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        },
    )


# ────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    print("\n  CompilerAI Backend — http://localhost:5000\n")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
