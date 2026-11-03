"""
Compiler Optimization Pipeline — Hybrid Analysis, Bounded Iterative Feedback Loop, and Security Assessment.

Chains:
  Step 1: AnalysisAgent (hybrid conventional analysis + LLM reasoning + initial security scoring)
  Step 2 & 3: Bounded Optimization-Verification Feedback Loop (Max 3 iterations)
      Iteration: OptimizationAgent -> VerificationAgent -> Acceptance Evaluation
      If blocking issues remain and attempt < 3: emit feedback and retry
      If passes acceptance: terminate loop early
  Step 4: SecurityAgent (independent assessment of final candidate, score comparison, risk evaluation)

All agents share a single ContextManager instance using stable keys.
"""

import logging
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_root = os.path.join(os.path.dirname(__file__), "..", "..")
if _root not in sys.path:
    sys.path.insert(0, _root)

from agent_framework import AgentRegistry, ContextManager
from agent_framework.message_protocol import Message, MessageType, MessagePriority
from src.llm.llm_client import LLMClient
from src.agents.analysis_agent import AnalysisAgent
from src.agents.optimization_agent import OptimizationAgent
from src.agents.verification_agent import VerificationAgent
from src.agents.security_agent import SecurityAgent

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Consolidated outcome of the compiler optimization pipeline."""
    file_path: str
    status: str                         # "success" | "rollback" | "failed" | "incomplete" | "error" | "no_optimization"
    selected_code: str = ""             # The authoritative final source code (original if rolled back)
    original_code: str = ""             # Original input source code
    candidate_code: str = ""            # Candidate source generated during optimization
    was_rolled_back: bool = False       # True if candidate was rejected & original restored
    rollback_reason: Optional[str] = None
    analysis_report: Dict[str, Any] = field(default_factory=dict)
    optimization_report: Dict[str, Any] = field(default_factory=dict)
    verification_report: Dict[str, Any] = field(default_factory=dict)
    security_report: Dict[str, Any] = field(default_factory=dict)
    iteration_count: int = 1
    iteration_history: List[Dict[str, Any]] = field(default_factory=list)
    unresolved_findings: List[Dict[str, Any]] = field(default_factory=list)
    initial_security_score: Optional[int] = None
    final_security_score: Optional[int] = None
    score_change: Optional[int] = None
    score_explanation: str = ""
    error: Optional[str] = None

    @property
    def final_source_code(self) -> str:
        """Alias returning the authoritative selected source code."""
        return self.selected_code or self.original_code

    def summary(self) -> str:
        lines = [
            f"{'='*64}",
            f" Pipeline Result for: {self.file_path}",
            f" Status: {self.status.upper()} | Iterations: {self.iteration_count}/3",
            f"{'='*64}",
        ]

        if self.was_rolled_back:
            lines.append(f"\n[Rollback Notice] Candidate optimization was REJECTED and rolled back.")
            lines.append(f"  Selected Code : Original source code restored.")
            if self.rollback_reason:
                lines.append(f"  Reason        : {self.rollback_reason}")

        # Initial Analysis
        if self.analysis_report:
            n = len(self.analysis_report.get("all_findings", []))
            init_score = self.initial_security_score
            score_txt = f"{init_score}/100" if init_score is not None else "N/A"
            lines.append(f"\n[Initial Analysis]  {n} finding(s) | Security Score: {score_txt}")
            lines.append(self.analysis_report.get("summary", ""))

        # Iteration History
        if len(self.iteration_history) > 1:
            lines.append(f"\n[Optimization-Verification Loop]  Ran {len(self.iteration_history)} attempt(s)")
            for h in self.iteration_history:
                it = h.get("iteration")
                passes = "PASSED" if h.get("passes_acceptance") else "REJECTED"
                reasons = "; ".join(h.get("blocking_reasons", [])) or "None"
                lines.append(f"  Attempt {it}: {passes} — Blocking issues: {reasons}")

        # Optimization
        if self.optimization_report:
            n = len(self.optimization_report.get("transformations", []))
            opt_st = self.optimization_report.get("optimization_status", "")
            lines.append(f"\n[Final Optimization]  {n} transformation(s) | Status: {opt_st}")
            lines.append(self.optimization_report.get("summary", ""))
            out = self.optimization_report.get("output_file", "")
            if out:
                lines.append(f"  Saved to: {out}")
            diff = self.optimization_report.get("unified_diff", "")
            if diff:
                lines.append("\n[Unified Diff]")
                lines.append(diff[:1500] + ("... (truncated)" if len(diff) > 1500 else ""))

        # Verification
        if self.verification_report:
            ver_status = self.verification_report.get("status", "")
            passes = self.verification_report.get("passes_acceptance", False)
            lines.append(f"\n[Verification]  Status: {ver_status} (Acceptance: {'PASS' if passes else 'FAIL'})")
            lines.append(self.verification_report.get("summary", ""))

        # Security
        if self.security_report:
            n_all = len(self.security_report.get("all_vulnerabilities", []))
            n_new = len(self.security_report.get("new_vulnerabilities", []))
            risk = self.security_report.get("overall_risk", "?").upper()
            sec_status = self.security_report.get("status", "?")
            final_sc = self.final_security_score
            sc_str = f"{final_sc}/100" if final_sc is not None else "N/A"
            lines.append(f"\n[Security]  {n_all} vulnerability(ies), {n_new} new | Risk: {risk} | Status: {sec_status}")
            lines.append(f"  Final Score: {sc_str} | {self.score_explanation}")
            lines.append(self.security_report.get("summary", ""))

        if self.error:
            lines.append(f"\n[Error] {self.error}")

        return "\n".join(lines)


class CompilerOptimizationPipeline:
    """
    End-to-end pipeline from C/C++ source -> analysis -> bounded optimization/verification loop -> security audit.
    """

    MAX_ITERATIONS = 3

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        message_logger=None,
        enable_security: bool = True,
    ):
        self.llm = llm_client or LLMClient()
        self.context = ContextManager()
        self.registry = AgentRegistry()
        self._msg_logger = message_logger
        self.enable_security = enable_security

        # Instantiate the 4 agents sharing self.context
        self.analysis_agent = AnalysisAgent("analysis_1", self.context, self.llm)
        self.optimization_agent = OptimizationAgent("optimization_1", self.context, self.llm)
        self.verification_agent = VerificationAgent("verification_1", self.context, self.llm)
        self.security_agent = SecurityAgent("security_1", self.context, self.llm)

        # Register agents in registry
        self.registry.register(self.analysis_agent)
        self.registry.register(self.optimization_agent)
        self.registry.register(self.verification_agent)
        self.registry.register(self.security_agent)

    # ── Internal Message Helper ────────────────────────────────────────────────

    def _route(
        self,
        sender_id: str,
        receiver_id: str,
        msg_type: MessageType,
        payload: dict,
        priority: MessagePriority = MessagePriority.HIGH,
        corr_id: str = None,
    ) -> str:
        """Route message to observer logger for live UI SSE streaming."""
        msg = Message.create(
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type=msg_type,
            payload=payload,
            priority=priority,
            correlation_id=corr_id,
        )
        if self._msg_logger:
            self._msg_logger._on_message(msg)
        logger.debug(
            f"MSG {msg.message_type.value}: {sender_id} -> {receiver_id} "
            f"payload_keys={list(payload.keys())}"
        )
        return msg.message_id

    # ── Pipeline Execution ────────────────────────────────────────────────────

    def run(self, file_path: str) -> PipelineResult:
        """Run the complete pipeline on a C/C++ source file."""
        logger.info(f"Pipeline starting for: {file_path}")

        if not os.path.isfile(file_path):
            return PipelineResult(
                file_path=file_path,
                status="failed",
                error=f"File not found: {file_path}",
            )

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                source_code = f.read()
        except OSError as exc:
            return PipelineResult(
                file_path=file_path,
                status="failed",
                error=f"Cannot read file: {exc}",
            )

        # Reset shared context for this execution
        self.context.clear()
        self.context.set("original_code", source_code)
        self.context.set("source_file", file_path)

        # ── Step 1: Initial Analysis (runs ONCE on original code) ─────────────
        logger.info("Step 1/4: Initial Analysis on Original Code")
        req1_id = self._route(
            sender_id="pipeline",
            receiver_id="analysis_1",
            msg_type=MessageType.REQUEST,
            payload={
                "action": "analyse",
                "file_path": file_path,
                "source_code": source_code,
                "line_count": source_code.count("\n"),
            },
        )

        try:
            analysis_result = self.analysis_agent.process({
                "source_code": source_code,
                "file_path": file_path,
            })
        except Exception as exc:
            logger.error(f"Analysis step failed: {exc}", exc_info=True)
            return PipelineResult(
                file_path=file_path,
                status="failed",
                error=f"Analysis step failed: {exc}",
            )

        initial_score = analysis_result.get("security_score")
        self._route(
            sender_id="analysis_1",
            receiver_id="pipeline",
            msg_type=MessageType.RESPONSE,
            payload={
                "status": "ok",
                "findings": len(analysis_result.get("all_findings", [])),
                "security_score": initial_score,
                "conclusion": analysis_result.get("conclusion", ""),
            },
            corr_id=req1_id,
        )

        # ── Step 2 & 3: Bounded Optimization-Verification Feedback Loop ──────
        logger.info("Steps 2 & 3: Bounded Optimization-Verification Loop (Max 3 attempts)")
        iteration = 1
        iteration_history: List[Dict[str, Any]] = []
        feedback: Optional[Dict[str, Any]] = None
        current_candidate: str = source_code
        latest_opt_result: Dict[str, Any] = {}
        latest_ver_result: Dict[str, Any] = {}

        while iteration <= self.MAX_ITERATIONS:
            logger.info(f"--- Feedback Loop Iteration {iteration}/{self.MAX_ITERATIONS} ---")

            # Route notification & request for Optimization
            self._route(
                sender_id="pipeline",
                receiver_id="optimization_1",
                msg_type=MessageType.REQUEST,
                payload={
                    "action": "optimise",
                    "iteration": iteration,
                    "max_iterations": self.MAX_ITERATIONS,
                    "file_path": file_path,
                    "n_findings": len(analysis_result.get("all_findings", [])),
                    "has_feedback": feedback is not None,
                },
            )

            try:
                opt_result = self.optimization_agent.process({
                    "source_code": source_code,
                    "file_path": file_path,
                    "analysis_report": analysis_result,
                    "iteration": iteration,
                    "feedback": feedback,
                    "previous_attempts": iteration_history,
                })
            except Exception as exc:
                logger.error(f"Optimization attempt {iteration} failed: {exc}", exc_info=True)
                opt_result = {
                    "error": str(exc),
                    "optimized_code": current_candidate,
                    "transformations": [],
                    "optimization_status": "error",
                }

            latest_opt_result = opt_result
            current_candidate = opt_result.get("optimized_code") or source_code

            self._route(
                sender_id="optimization_1",
                receiver_id="pipeline",
                msg_type=MessageType.RESPONSE,
                payload={
                    "iteration": iteration,
                    "status": opt_result.get("optimization_status"),
                    "transformations": len(opt_result.get("transformations", [])),
                    "output_file": opt_result.get("output_file", ""),
                },
            )

            # Route notification & request for Verification
            self._route(
                sender_id="pipeline",
                receiver_id="verification_1",
                msg_type=MessageType.REQUEST,
                payload={
                    "action": "verify",
                    "iteration": iteration,
                    "file_path": file_path,
                    "candidate_len": len(current_candidate),
                },
            )

            try:
                ver_result = self.verification_agent.process({
                    "original_code": source_code,
                    "optimized_code": current_candidate,
                    "file_path": file_path,
                    "analysis_report": analysis_result,
                    "iteration": iteration,
                })
            except Exception as exc:
                logger.error(f"Verification attempt {iteration} failed: {exc}", exc_info=True)
                ver_result = {
                    "status": "FAIL",
                    "passes_acceptance": False,
                    "error": str(exc),
                    "blocking_reasons": [f"Verification exception: {exc}"],
                    "feedback_report": {
                        "iteration": iteration,
                        "failed_layers": ["exception"],
                        "diagnostics": str(exc),
                    },
                }

            latest_ver_result = ver_result
            passes_acceptance = ver_result.get("passes_acceptance", False)

            # Record iteration history
            record = {
                "iteration": iteration,
                "candidate_code": current_candidate,
                "optimization_status": opt_result.get("optimization_status"),
                "transformations": opt_result.get("transformations", []),
                "verification_status": ver_result.get("status"),
                "passes_acceptance": passes_acceptance,
                "blocking_reasons": ver_result.get("blocking_reasons", []),
                "unresolved_findings": ver_result.get("unresolved_findings", []),
                "new_findings": ver_result.get("new_findings", []),
            }
            iteration_history.append(record)

            self._route(
                sender_id="verification_1",
                receiver_id="pipeline",
                msg_type=MessageType.RESPONSE,
                payload={
                    "iteration": iteration,
                    "status": ver_result.get("status"),
                    "passes_acceptance": passes_acceptance,
                    "diff_passed": ver_result.get("diff_passed"),
                    "z3_status": ver_result.get("z3_status"),
                    "blocking_reasons": ver_result.get("blocking_reasons", []),
                },
            )

            if passes_acceptance:
                logger.info(f"Loop passed acceptance criteria on attempt {iteration}! Stopping retries.")
                self._route(
                    sender_id="pipeline",
                    receiver_id="ui",
                    msg_type=MessageType.NOTIFICATION,
                    payload={"event": "acceptance_passed", "attempt": iteration},
                )
                break
            elif iteration < self.MAX_ITERATIONS:
                feedback = ver_result.get("feedback_report")
                logger.info(f"Attempt {iteration} had blocking issues. Triggering retry {iteration+1} with feedback.")
                self._route(
                    sender_id="pipeline",
                    receiver_id="ui",
                    msg_type=MessageType.NOTIFICATION,
                    payload={"event": "retry_triggered", "next_attempt": iteration + 1, "reasons": ver_result.get("blocking_reasons", [])},
                )
                iteration += 1
            else:
                logger.warning("Max 3 optimization-verification attempts exhausted without full acceptance.")
                self._route(
                    sender_id="pipeline",
                    receiver_id="ui",
                    msg_type=MessageType.NOTIFICATION,
                    payload={"event": "attempts_exhausted", "total_attempts": self.MAX_ITERATIONS},
                )
                break

        # Save loop state in context
        self.context.set("iteration_count", min(iteration, self.MAX_ITERATIONS))
        self.context.set("iteration_history", iteration_history)
        self.context.set("current_candidate", current_candidate)
        unresolved_final = latest_ver_result.get("unresolved_findings", [])
        self.context.set("unresolved_findings", unresolved_final)

        # ── Step 4: Final Security Audit on Candidate ─────────────────────────
        logger.info("Step 4/4: Security Audit on Final Candidate")
        sec_result = {}
        if not self.enable_security or self.security_agent is None:
            logger.info("Security audit disabled by configuration (--no-security). Skipping Step 4.")
            sec_result = {
                "status": "SKIPPED",
                "overall_risk": "not_assessed",
                "security_score": None,
                "score_change": None,
                "score_explanation": "Security audit was disabled via configuration (--no-security).",
                "all_vulnerabilities": [],
                "new_vulnerabilities": [],
                "resolved_vulnerabilities": [],
                "audit_completeness": "skipped",
                "summary": "Security audit was skipped by user request (--no-security). No security verification was performed.",
                "limitations": ["Security audit disabled by configuration."],
            }
        else:
            req4_id = self._route(
                sender_id="pipeline",
                receiver_id="security_1",
                msg_type=MessageType.REQUEST,
                payload={
                    "action": "security_audit",
                    "file_path": file_path,
                    "candidate_len": len(current_candidate),
                    "has_candidate": current_candidate != source_code,
                },
            )

            try:
                sec_result = self.security_agent.process({
                    "original_code": source_code,
                    "optimized_code": current_candidate,
                    "file_path": file_path,
                    "initial_analysis_report": analysis_result,
                    "latest_verification_report": latest_ver_result,
                    "iteration_history": iteration_history,
                    "unresolved_findings": unresolved_final,
                })
            except Exception as exc:
                logger.error(f"Security audit failed with exception: {exc}", exc_info=True)
                sec_result = {
                    "status": "ERROR",
                    "overall_risk": "unknown",
                    "security_score": None,
                    "score_change": None,
                    "score_explanation": f"Security audit encountered exception: {exc}",
                    "all_vulnerabilities": [],
                    "new_vulnerabilities": [],
                    "resolved_vulnerabilities": [],
                    "audit_completeness": "incomplete",
                    "summary": f"Security audit failed due to exception: {exc}",
                    "limitations": [f"Security audit failed with exception: {exc}"],
                }

            final_score = sec_result.get("security_score")
            score_change = sec_result.get("score_change")

            self._route(
                sender_id="security_1",
                receiver_id="pipeline",
                msg_type=MessageType.RESPONSE,
                payload={
                    "status": sec_result.get("status"),
                    "overall_risk": sec_result.get("overall_risk"),
                    "security_score": final_score,
                    "score_change": score_change,
                },
                corr_id=req4_id,
            )

        final_score = sec_result.get("security_score")
        score_change = sec_result.get("score_change")
        score_explanation = sec_result.get("score_explanation", "")

        # ── Determine Overall Pipeline Status & Genuine Rollback ──────────────
        ver_status = latest_ver_result.get("status", "FAIL")
        ver_passes = latest_ver_result.get("passes_acceptance", False)
        sec_status = sec_result.get("status", "PASS")
        new_vulns = sec_result.get("new_vulnerabilities", [])
        new_crit_high = [v for v in new_vulns if v.get("severity") in ("critical", "high")]

        opt_status = str(latest_opt_result.get("optimization_status") or latest_opt_result.get("status") or "").lower()
        has_optimization = bool(
            (current_candidate and current_candidate.strip() and current_candidate != source_code)
            or (opt_status in ("optimization_generated", "success") and current_candidate.strip())
        )

        if not has_optimization:
            status = "no_optimization"
            selected_code = source_code
            was_rolled_back = False
            rollback_reason = None
        elif sec_status == "ROLLBACK" or new_crit_high:
            status = "rollback"
            selected_code = source_code  # Genuine rollback: restore original code
            was_rolled_back = True
            rollback_reason = (
                f"Security audit rejected candidate: {sec_result.get('summary', 'Critical/High vulnerabilities introduced.')}"
            )
        elif sec_status == "ERROR":
            status = "error"
            selected_code = source_code
            was_rolled_back = True
            rollback_reason = f"Security audit encountered error: {sec_result.get('summary')}"
        elif ver_passes and sec_status in ("PASS", "SKIPPED"):
            status = "success"
            selected_code = current_candidate
            was_rolled_back = False
            rollback_reason = None
        elif not ver_passes:
            status = "failed"
            selected_code = source_code  # Failed verification: never release unverified candidate
            was_rolled_back = True
            reasons = "; ".join(latest_ver_result.get("blocking_reasons", [])) or "Verification checks failed."
            rollback_reason = f"Verification acceptance failed after {min(iteration, self.MAX_ITERATIONS)} attempt(s): {reasons}"
        else:
            status = "incomplete"
            selected_code = source_code
            was_rolled_back = True
            rollback_reason = "Mandatory pipeline correctness requirements could not be confirmed."

        # Synchronize candidate and rollback state in optimization report
        if was_rolled_back:
            latest_opt_result["selected_code"] = source_code
            latest_opt_result["is_rolled_back"] = True
            latest_opt_result["rollback_reason"] = rollback_reason
            out_file = latest_opt_result.get("output_file")
            if out_file and os.path.exists(out_file):
                try:
                    with open(out_file, "w", encoding="utf-8") as f:
                        f.write(source_code)
                    logger.info(f"Replaced candidate in {out_file} with restored original code due to rollback.")
                except OSError as e:
                    logger.warning(f"Could not rewrite output file on rollback: {e}")
        else:
            latest_opt_result["selected_code"] = selected_code
            latest_opt_result["is_rolled_back"] = False
            latest_opt_result["rollback_reason"] = None

        logger.info(f"Pipeline finished for {file_path} with status: {status.upper()}")

        return PipelineResult(
            file_path=file_path,
            status=status,
            selected_code=selected_code,
            original_code=source_code,
            candidate_code=current_candidate,
            was_rolled_back=was_rolled_back,
            rollback_reason=rollback_reason,
            analysis_report=analysis_result,
            optimization_report=latest_opt_result,
            verification_report=latest_ver_result,
            security_report=sec_result,
            iteration_count=min(iteration, self.MAX_ITERATIONS),
            iteration_history=iteration_history,
            unresolved_findings=unresolved_final,
            initial_security_score=initial_score,
            final_security_score=final_score,
            score_change=score_change,
            score_explanation=score_explanation,
        )

    def run_string(self, source_code: str, label: str = "<string>") -> PipelineResult:
        """Run the pipeline on a source code string (for testing)."""
        import tempfile
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".cpp", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(source_code)
            tmp_path = tmp.name
        try:
            result = self.run(tmp_path)
            result.file_path = label
            return result
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
