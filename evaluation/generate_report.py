"""
evaluation/generate_report.py — Phase 2 Integration Report Generator

Runs the full 4-stage pipeline (Analysis → Optimization → Verification → Security)
on a representative set of test cases and produces a Markdown report.

Usage:
    python evaluation/generate_report.py
    python evaluation/generate_report.py --no-llm
    python evaluation/generate_report.py --out custom_report.md
    python evaluation/generate_report.py --cases TC01 TC11 TC16
"""

import argparse
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.pipeline.pipeline import CompilerOptimizationPipeline, PipelineResult
from src.llm.llm_client import LLMClient
from src.logger_config import setup_logging

# ── Default test case selection ────────────────────────────────────────────────
# Covers all major vulnerability/bug categories in the benchmark dataset

DEFAULT_CASES = [
    ("TC01_uninit_arithmetic.cpp",  "Uninitialized variable — arithmetic"),
    ("TC06_div_by_zero_simple.cpp", "Division by zero — simple"),
    ("TC09_array_out_of_bounds.cpp","Array out of bounds"),
    ("TC11_buffer_overflow_loop.cpp","Buffer overflow — loop"),
    ("TC12_strcpy_overflow.cpp",    "strcpy buffer overflow"),
    ("TC14_memory_leak.cpp",        "Memory leak"),
    ("TC16_use_after_free.cpp",     "Use-after-free"),
    ("TC19_heap_overflow.cpp",      "Heap overflow"),
]

TESTCASES_DIR = os.path.join(
    os.path.dirname(__file__), "..", "MicroBenchmarks", "Testcases"
)

REPORT_DIR = os.path.join(
    os.path.dirname(__file__), "..",
    "Technical Deliverlables and Documents",
)


# ── Per-run metrics ────────────────────────────────────────────────────────────

@dataclass
class RunMetrics:
    filename: str
    description: str
    status: str               # success / partial / rollback / failed / skipped
    elapsed_s: float
    analysis_findings: int
    analysis_high: int
    optimization_applied: bool
    transformations: int
    verification_status: str  # PASS / FAIL / ROLLBACK / skipped
    diff_passed: Optional[bool]
    security_status: str      # PASS / ROLLBACK / skipped
    total_vulns: int
    new_vulns: int
    overall_risk: str
    security_sources: List[str] = field(default_factory=list)
    error: Optional[str] = None


# ── Runner ─────────────────────────────────────────────────────────────────────

def run_case(
    pipeline: CompilerOptimizationPipeline,
    tc_path: str,
    description: str,
) -> RunMetrics:
    filename = os.path.basename(tc_path)
    if not os.path.isfile(tc_path):
        return RunMetrics(
            filename=filename, description=description,
            status="skipped", elapsed_s=0.0,
            analysis_findings=0, analysis_high=0,
            optimization_applied=False, transformations=0,
            verification_status="skipped",
            diff_passed=None,
            security_status="skipped",
            total_vulns=0, new_vulns=0, overall_risk="?",
            error="File not found",
        )

    t0 = time.time()
    result: PipelineResult = pipeline.run(tc_path)
    elapsed = round(time.time() - t0, 2)

    # Analysis metrics
    a = result.analysis_report
    n_findings  = len(a.get("all_findings", []))
    n_high      = sum(1 for f in a.get("all_findings", []) if f.get("severity") == "high")

    # Optimization metrics
    o = result.optimization_report
    n_trans = len(o.get("transformations", []))
    opt_applied = bool(o.get("optimized_code") or n_trans > 0)

    # Verification metrics
    v = result.verification_report
    ver_status  = v.get("status", "skipped") if v else "skipped"
    diff_passed = v.get("diff_passed") if v else None

    # Security metrics
    s = result.security_report
    sec_status  = s.get("status", "skipped") if s else "skipped"
    total_v     = len(s.get("all_vulnerabilities", [])) if s else 0
    new_v       = len(s.get("new_vulnerabilities", [])) if s else 0
    risk        = s.get("overall_risk", "?") if s else "?"
    sources     = s.get("sources", []) if s else []

    return RunMetrics(
        filename=filename, description=description,
        status=result.status, elapsed_s=elapsed,
        analysis_findings=n_findings, analysis_high=n_high,
        optimization_applied=opt_applied, transformations=n_trans,
        verification_status=ver_status,
        diff_passed=diff_passed,
        security_status=sec_status,
        total_vulns=total_v, new_vulns=new_v, overall_risk=risk,
        security_sources=sources,
        error=result.error,
    )


# ── Markdown report builder ────────────────────────────────────────────────────

def build_report(
    metrics: List[RunMetrics],
    llm_mode: str,
    elapsed_total: float,
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total = len(metrics)
    ran   = [m for m in metrics if m.status != "skipped"]
    skipped = total - len(ran)

    success_count  = sum(1 for m in ran if m.status == "success")
    rollback_count = sum(1 for m in ran if m.status == "rollback")
    partial_count  = sum(1 for m in ran if m.status == "partial")
    failed_count   = sum(1 for m in ran if m.status == "failed")

    pass_rate = round(100 * success_count / len(ran), 1) if ran else 0

    avg_findings = round(
        sum(m.analysis_findings for m in ran) / len(ran), 1
    ) if ran else 0

    sec_rollbacks = sum(1 for m in ran if m.security_status == "ROLLBACK")
    new_vuln_total = sum(m.new_vulns for m in ran)

    top_bug_types: Dict[str, int] = {}
    for m in ran:
        # We only track coarse categories here from filename hints
        for kw, label in [
            ("uninit", "uninitialized_variable"),
            ("div_by_zero", "division_by_zero"),
            ("array", "array_out_of_bounds"),
            ("buffer", "buffer_overflow"),
            ("strcpy", "unsafe_strcpy"),
            ("leak", "memory_leak"),
            ("use_after_free", "use_after_free"),
            ("heap", "heap_overflow"),
        ]:
            if kw in m.filename.lower():
                top_bug_types[label] = top_bug_types.get(label, 0) + 1

    lines: List[str] = []

    # ── Title ──────────────────────────────────────────────────────────────────
    lines += [
        "# Phase 2 Integration Report",
        "",
        f"**Generated:** {now}  ",
        f"**LLM Mode:** {llm_mode}  ",
        f"**Total runtime:** {round(elapsed_total, 1)} s  ",
        "",
        "---",
        "",
    ]

    # ── Executive Summary ──────────────────────────────────────────────────────
    lines += [
        "## Executive Summary",
        "",
        f"The 4-stage pipeline (Analysis → Optimization → Verification → Security) "
        f"was run on **{total}** benchmark test cases ({skipped} skipped — file not found).",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Files run | {len(ran)} |",
        f"| Pass rate (success) | {pass_rate}% ({success_count}/{len(ran)}) |",
        f"| Rollbacks | {rollback_count} |",
        f"| Partial completions | {partial_count} |",
        f"| Failed | {failed_count} |",
        f"| Avg analysis findings per file | {avg_findings} |",
        f"| New security vulns introduced | {new_vuln_total} |",
        f"| Security rollbacks triggered | {sec_rollbacks} |",
        "",
    ]

    # ── Per-agent performance ─────────────────────────────────────────────────
    lines += [
        "## Per-Agent Performance",
        "",
        "### Analysis Agent",
        "",
        f"- Total findings across all files: "
        f"**{sum(m.analysis_findings for m in ran)}**",
        f"- High-severity findings: "
        f"**{sum(m.analysis_high for m in ran)}**",
        f"- Average findings per file: **{avg_findings}**",
    ]
    if top_bug_types:
        lines.append("- Top bug categories detected (by filename):")
        for bt, cnt in sorted(top_bug_types.items(), key=lambda x: -x[1]):
            lines.append(f"  - `{bt}`: {cnt} file(s)")
    lines.append("")

    lines += [
        "### Optimization Agent",
        "",
        f"- Files with transformations applied: "
        f"**{sum(1 for m in ran if m.optimization_applied)}** / {len(ran)}",
        f"- Total transformations: "
        f"**{sum(m.transformations for m in ran)}**",
        "",
        "### Verification Agent",
        "",
        ver_breakdown := {
            s: sum(1 for m in ran if m.verification_status == s)
            for s in ("PASS", "FAIL", "ROLLBACK", "skipped")
        },
    ]
    # Fix the walrus assignment appearing in list — rewrite cleanly
    lines.pop()
    ver_bd = {
        s: sum(1 for m in ran if m.verification_status == s)
        for s in ("PASS", "FAIL", "ROLLBACK", "skipped")
    }
    for s, cnt in ver_bd.items():
        lines.append(f"- Verification **{s}**: {cnt}")
    diff_pass = sum(1 for m in ran if m.diff_passed is True)
    lines.append(f"- Differential tests passed: **{diff_pass}** / {len(ran)}")
    lines.append("")

    lines += [
        "### Security Agent",
        "",
        f"- Total vulnerabilities found (optimized code): "
        f"**{sum(m.total_vulns for m in ran)}**",
        f"- New vulnerabilities introduced by optimization: "
        f"**{new_vuln_total}**",
        f"- Security rollbacks triggered: **{sec_rollbacks}**",
    ]
    # Risk breakdown
    risks = {}
    for m in ran:
        risks[m.overall_risk] = risks.get(m.overall_risk, 0) + 1
    for r, cnt in sorted(risks.items()):
        lines.append(f"- Overall risk **{r}**: {cnt} file(s)")
    # Detection sources
    all_sources: Dict[str, int] = {}
    for m in ran:
        for src in m.security_sources:
            all_sources[src] = all_sources.get(src, 0) + 1
    if all_sources:
        lines.append("- Detection layers used:")
        for src, cnt in sorted(all_sources.items()):
            lines.append(f"  - `{src}`: active in {cnt} run(s)")
    lines.append("")

    # ── Per-file results table ─────────────────────────────────────────────────
    lines += [
        "## Per-File Results",
        "",
        "| File | Category | Status | Findings | Opt | Ver | Sec Risk | New Vulns | Time (s) |",
        "|------|----------|--------|----------|-----|-----|----------|-----------|----------|",
    ]
    for m in metrics:
        opt_icon = "✓" if m.optimization_applied else "–"
        ver_icon = {"PASS": "✓", "FAIL": "✗", "ROLLBACK": "↩", "skipped": "–"}.get(
            m.verification_status, "?"
        )
        status_icon = {
            "success": "✓", "partial": "~", "rollback": "↩",
            "failed": "✗", "skipped": "skip",
        }.get(m.status, "?")
        lines.append(
            f"| `{m.filename}` | {m.description} | {status_icon} {m.status} "
            f"| {m.analysis_findings} (H:{m.analysis_high}) "
            f"| {opt_icon} | {ver_icon} "
            f"| {m.overall_risk} | {m.new_vulns} | {m.elapsed_s} |"
        )
    lines.append("")

    # ── Failure analysis ──────────────────────────────────────────────────────
    failures = [m for m in ran if m.status in ("failed", "rollback", "partial")]
    lines += ["## Failure Analysis", ""]
    if not failures:
        lines.append("No failures or rollbacks. All files processed successfully.")
    else:
        for m in failures:
            lines.append(f"### `{m.filename}`")
            lines.append(f"- **Status:** {m.status}")
            if m.error:
                lines.append(f"- **Error:** {m.error}")
            if m.verification_status in ("FAIL", "ROLLBACK"):
                lines.append(f"- **Verification result:** {m.verification_status}")
            if m.security_status == "ROLLBACK":
                lines.append(
                    f"- **Security rollback:** {m.new_vulns} new HIGH-severity "
                    "vulnerability(ies) introduced by optimization."
                )
            lines.append("")
    lines.append("")

    # ── Conclusion ────────────────────────────────────────────────────────────
    readiness = "READY" if pass_rate >= 70 and sec_rollbacks == 0 else "NEEDS WORK"
    lines += [
        "## Conclusion and Week 9 Readiness",
        "",
        f"**Phase 2 Status:** {readiness}",
        "",
        f"The core 4-stage pipeline is functional. "
        f"Pass rate is **{pass_rate}%** with **{rollback_count}** rollback(s). "
        f"The Security Agent detected **{new_vuln_total}** newly introduced "
        f"vulnerability(ies) across all test cases.",
        "",
        "**Ready for Week 9:** Self-refinement mechanism and Orchestrator Agent.",
        "",
        "---",
        "_Generated by evaluation/generate_report.py — "
        "AI-Driven Compiler Optimization System_",
    ]

    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    setup_logging(level="WARNING")  # suppress INFO noise during batch run

    parser = argparse.ArgumentParser(
        description="Generate Phase 2 Integration Report"
    )
    parser.add_argument(
        "--no-llm", action="store_true",
        help="Disable LLM (rule-based only, much faster)",
    )
    parser.add_argument(
        "--out", default=None,
        help="Output Markdown file path (default: Technical Deliverlables and Documents/Phase2_Integration_Report.md)",
    )
    parser.add_argument(
        "--cases", nargs="+", default=None,
        help="Filter test cases by filename prefix e.g. TC01 TC11",
    )
    args = parser.parse_args()

    # Build pipeline
    llm = LLMClient()
    if args.no_llm:
        llm._available = False
    pipeline = CompilerOptimizationPipeline(llm_client=llm)
    if args.no_llm:
        for ag in (
            pipeline.analysis_agent,
            pipeline.optimization_agent,
            pipeline.verification_agent,
            pipeline.security_agent,
        ):
            ag.llm._available = False

    # Select test cases
    cases = DEFAULT_CASES
    if args.cases:
        cases = [
            (fn, desc) for fn, desc in DEFAULT_CASES
            if any(fn.startswith(c) for c in args.cases)
        ]
        if not cases:
            print(f"No cases matched: {args.cases}")
            sys.exit(1)

    # Run all cases
    print(f"\nRunning Phase 2 Integration Report ({len(cases)} test cases) …\n")
    metrics: List[RunMetrics] = []
    t_total = time.time()

    for fn, desc in cases:
        tc_path = os.path.join(TESTCASES_DIR, fn)
        print(f"  [{cases.index((fn, desc)) + 1}/{len(cases)}] {fn} … ", end="", flush=True)
        m = run_case(pipeline, tc_path, desc)
        metrics.append(m)
        status_icon = {"success": "✓", "rollback": "↩", "partial": "~",
                       "failed": "✗", "skipped": "SKIP"}.get(m.status, "?")
        print(f"{status_icon} ({m.elapsed_s}s)")

    elapsed_total = time.time() - t_total
    llm_mode = "offline (rule-based)" if args.no_llm else "online (Qwen 2.5 Coder)"

    # Build report
    report_md = build_report(metrics, llm_mode, elapsed_total)

    # Determine output path
    if args.out:
        out_path = args.out
    else:
        os.makedirs(REPORT_DIR, exist_ok=True)
        out_path = os.path.join(REPORT_DIR, "Phase2_Integration_Report.md")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    print(f"\nReport saved to: {out_path}")
    print(f"Total time: {round(elapsed_total, 1)}s\n")


if __name__ == "__main__":
    main()
