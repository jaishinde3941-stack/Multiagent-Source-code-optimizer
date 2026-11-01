"""
Performance Benchmarker — Week 7

Compiles original and optimized code with -O0, runs each N times,
and reports minimum execution time (measured inside the process via
std::chrono) and speedup percentage.

Timing is injected directly into the C++ source as a harness around
main() using std::chrono::high_resolution_clock, so process spawn,
ELF loading, and OS teardown are excluded from the measurement.

Requires g++ on PATH. Falls back gracefully if unavailable.
"""

import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

_RUNS = 10   # number of timing runs per binary

# ── Timing harness ─────────────────────────────────────────────────────────────
# Prepended to source: renames the user's main → __orig_main__ so our
# wrapper can call it while the linker still finds a symbol named main.
_TIMING_PREFIX = "#define main __orig_main__\n"

# Appended to source after the original code.
# Provides a new main() that wraps __orig_main__ with chrono timing and
# writes elapsed nanoseconds to stderr (never pollutes stdout, so
# differential testing output comparison is unaffected).
_TIMING_HARNESS = r"""
#ifdef __cplusplus
#include <chrono>
#include <cstdio>
int main(int argc, char* argv[]) {
    auto _t0 = std::chrono::high_resolution_clock::now();
    int  _r  = __orig_main__(argc, argv);
    auto _t1 = std::chrono::high_resolution_clock::now();
    long long _ns = std::chrono::duration_cast<
        std::chrono::nanoseconds>(_t1 - _t0).count();
    fprintf(stderr, "__PERF_NS__:%lld\n", _ns);
    return _r;
}
#endif
"""


@dataclass
class PerfResult:
    available: bool
    original_ms: float = 0.0
    optimized_ms: float = 0.0
    speedup_pct: float = 0.0
    error: Optional[str] = None

    def summary(self) -> str:
        if not self.available or self.error:
            return f"Perf benchmark skipped: {self.error}"
        direction = "faster" if self.speedup_pct >= 0 else "slower"
        return (
            f"Original: {self.original_ms:.3f} ms | "
            f"Optimized: {self.optimized_ms:.3f} ms | "
            f"Speedup: {abs(self.speedup_pct):.1f}% {direction}"
        )


class PerfBenchmarker:
    """
    Measures and compares runtime of original vs optimized C++ code.

    Injects a std::chrono timing harness into each source file so that
    only the code inside main() is timed — process spawn and OS overhead
    are excluded entirely.  The minimum across _RUNS executions is used
    as the representative time (noise always adds latency, never removes
    it, so the minimum is the best approximation of true runtime).

    Usage
    -----
    bench = PerfBenchmarker()
    result = bench.benchmark(original_src, optimized_src)
    print(result.summary())
    """

    def __init__(self, compiler: str = "g++", timeout: int = 15, runs: int = _RUNS):
        self.compiler = compiler
        self.timeout  = timeout
        self.runs     = runs
        self._available = self._check_compiler()

    def benchmark(self, original_src: str, optimized_src: str) -> PerfResult:
        if not self._available:
            return PerfResult(
                available=False,
                error="g++ not found; performance benchmarking skipped.",
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            orig_cpp = os.path.join(tmpdir, "original.cpp")
            opt_cpp  = os.path.join(tmpdir, "optimized.cpp")
            orig_bin = os.path.join(tmpdir, "original.exe")
            opt_bin  = os.path.join(tmpdir, "optimized.exe")

            for src, path in [(original_src, orig_cpp), (optimized_src, opt_cpp)]:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(src)

            if not self._compile_timed(orig_cpp, orig_bin):
                return PerfResult(available=True, error="Original compilation failed.")
            if not self._compile_timed(opt_cpp, opt_bin):
                return PerfResult(available=True, error="Optimized compilation failed.")

            orig_ms = self._timed_run_ms(orig_bin)
            opt_ms  = self._timed_run_ms(opt_bin)

            if orig_ms > 0:
                speedup = (orig_ms - opt_ms) / orig_ms * 100.0
            else:
                speedup = 0.0

            return PerfResult(
                available=True,
                original_ms=orig_ms,
                optimized_ms=opt_ms,
                speedup_pct=speedup,
            )

    # ── Internals ─────────────────────────────────────────────────────────────

    def _compile_timed(self, src_path: str, out_path: str) -> bool:
        """
        Wrap source with the timing harness, write it back, then compile.
        The harness renames main → __orig_main__ and provides a new main()
        that times the call and prints __PERF_NS__:<ns> to stderr.
        """
        try:
            with open(src_path, "r", encoding="utf-8") as f:
                original = f.read()
            wrapped = _TIMING_PREFIX + original + _TIMING_HARNESS
            with open(src_path, "w", encoding="utf-8") as f:
                f.write(wrapped)
            proc = subprocess.run(
                [self.compiler, src_path, "-o", out_path, "-O0", "-w"],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            return proc.returncode == 0
        except Exception as exc:
            logger.debug(f"PerfBenchmarker compile error: {exc}")
            return False

    def _timed_run_ms(self, binary: str) -> float:
        """
        Run binary self.runs times, parse __PERF_NS__ from stderr each time,
        return the minimum in milliseconds.

        Using the minimum (not mean/median) because measurement noise always
        adds latency — the minimum is the run where the OS interfered least,
        giving the closest approximation to true execution time.
        """
        times = []
        for _ in range(self.runs):
            try:
                proc = subprocess.run(
                    [binary],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    input="",          # immediate EOF for programs using scanf/cin
                )
                for line in proc.stderr.splitlines():
                    if line.startswith("__PERF_NS__:"):
                        ns = int(line.split(":")[1])
                        times.append(ns / 1_000_000)   # nanoseconds → milliseconds
                        break
            except Exception:
                pass
        return min(times) if times else 0.0

    def _check_compiler(self) -> bool:
        try:
            subprocess.run([self.compiler, "--version"], capture_output=True, timeout=5)
            return True
        except Exception:
            return False
