"""
C/C++ Code Parser — Week 5 (regex-based, no external dependencies)

Extracts structural features from C/C++ source code to feed the
Analysis Agent.  Uses only the Python standard library.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Data structures ────────────────────────────────────────────────────────


@dataclass
class FunctionInfo:
    name: str
    return_type: str
    params: List[str]
    start_line: int
    end_line: int
    body: str


@dataclass
class LoopInfo:
    loop_type: str          # "for" | "while" | "do_while"
    line: int
    is_nested: bool
    depth: int


@dataclass
class ParseResult:
    """All extracted structural information from a C/C++ file."""
    file_path: str = ""
    source_code: str = ""
    line_count: int = 0
    functions: List[FunctionInfo] = field(default_factory=list)
    loops: List[LoopInfo] = field(default_factory=list)
    includes: List[str] = field(default_factory=list)
    global_vars: List[str] = field(default_factory=list)
    # potential bug patterns (heuristic, not definitive)
    uninitialized_vars: List[Dict] = field(default_factory=list)
    array_accesses: List[Dict] = field(default_factory=list)
    malloc_calls: List[int] = field(default_factory=list)
    free_calls: List[int] = field(default_factory=list)
    pointer_ops: List[Dict] = field(default_factory=list)
    max_loop_depth: int = 0
    has_nested_loops: bool = False

    def to_summary(self) -> str:
        """Return a human-readable text summary for use in prompts."""
        lines = [
            f"File: {self.file_path}",
            f"Lines: {self.line_count}",
            f"Functions: {[f.name for f in self.functions]}",
            f"Loop types: {list({l.loop_type for l in self.loops})}",
            f"Max loop depth: {self.max_loop_depth}",
            f"Has nested loops: {self.has_nested_loops}",
            f"Includes: {self.includes}",
        ]
        if self.uninitialized_vars:
            lines.append(f"Possible uninitialized vars: {self.uninitialized_vars}")
        if self.malloc_calls:
            lines.append(f"malloc calls at lines: {self.malloc_calls}")
        if self.free_calls:
            lines.append(f"free calls at lines: {self.free_calls}")
        if self.array_accesses:
            lines.append(f"Array accesses: {len(self.array_accesses)} found")
        return "\n".join(lines)


# ── Parser ────────────────────────────────────────────────────────────────


class CodeParser:
    """
    Pure-regex C/C++ feature extractor.

    Not a full AST parser — it extracts "good-enough" heuristics
    to seed the LLM analysis prompt.
    """

    # ── compiled patterns ─────────────────────────────────────────────────

    _RE_INCLUDE     = re.compile(r'^\s*#include\s*[<"]([^>"]+)[>"]', re.MULTILINE)
    _RE_FUNC_DECL   = re.compile(
        r'^\s*([\w:*&<>\s]+?)\s+(\w+)\s*\(([^)]*)\)\s*(?:const\s*)?\{',
        re.MULTILINE,
    )
    _RE_FOR         = re.compile(r'\bfor\s*\(', re.MULTILINE)
    _RE_WHILE       = re.compile(r'\bwhile\s*\(', re.MULTILINE)
    _RE_DO          = re.compile(r'\bdo\s*\{', re.MULTILINE)
    _RE_ARRAY_DECL  = re.compile(r'\b(\w+)\s+(\w+)\[(\d+)\]', re.MULTILINE)
    _RE_ARRAY_ACC   = re.compile(r'\b(\w+)\[([^\]]+)\]', re.MULTILINE)
    _RE_MALLOC      = re.compile(r'\bmalloc\s*\(', re.MULTILINE)
    _RE_FREE        = re.compile(r'\bfree\s*\(', re.MULTILINE)
    _RE_DEREF       = re.compile(r'\*\s*(\w+)', re.MULTILINE)
    _RE_VAR_DECL    = re.compile(
        r'^\s*(?:int|float|double|char|long|short|unsigned|bool)\s+(\w+)\s*;',
        re.MULTILINE,
    )
    _RE_GLOBAL_VAR  = re.compile(
        r'^(?:int|float|double|char|long|short|unsigned|bool)\s+(\w+)\s*[=;]',
        re.MULTILINE,
    )

    def parse_file(self, file_path: str) -> ParseResult:
        """Parse a C/C++ file by path."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
                source = fh.read()
        except OSError as exc:
            logger.error(f"Cannot read {file_path}: {exc}")
            return ParseResult(file_path=file_path)
        return self.parse_string(source, file_path=file_path)

    def parse_string(self, source_code: str, file_path: str = "<string>") -> ParseResult:
        """Parse C/C++ source from a string."""
        result = ParseResult(
            file_path=file_path,
            source_code=source_code,
            line_count=source_code.count("\n") + 1,
        )

        lines = source_code.splitlines()

        result.includes   = self._RE_INCLUDE.findall(source_code)
        result.functions  = self._extract_functions(source_code, lines)
        result.loops, result.max_loop_depth, result.has_nested_loops = \
            self._extract_loops(source_code, lines)
        result.array_accesses = self._extract_array_accesses(source_code, lines)
        result.uninitialized_vars = self._find_uninitialized(source_code, lines)
        result.malloc_calls = self._line_numbers_of(self._RE_MALLOC, lines)
        result.free_calls   = self._line_numbers_of(self._RE_FREE, lines)
        result.pointer_ops  = self._extract_pointer_ops(source_code, lines)
        result.global_vars  = self._RE_GLOBAL_VAR.findall(source_code)

        logger.debug(f"Parsed {file_path}: {result.line_count} lines, "
                     f"{len(result.functions)} functions, {len(result.loops)} loops")
        return result

    # ── Helpers ───────────────────────────────────────────────────────────

    _CPP_KEYWORDS = frozenset({
        'if', 'else', 'for', 'while', 'do', 'switch', 'case',
        'return', 'break', 'continue', 'goto', 'try', 'catch',
        'namespace', 'class', 'struct', 'enum', 'template', 'typedef',
    })

    def _extract_functions(self, src: str, lines: List[str]) -> List[FunctionInfo]:
        funcs = []
        for m in self._RE_FUNC_DECL.finditer(src):
            ret_type = m.group(1).strip()
            fname    = m.group(2).strip()
            params   = [p.strip() for p in m.group(3).split(",") if p.strip()]
            start_ln = src[:m.start()].count("\n") + 1
            # find matching closing brace
            end_ln   = self._find_block_end(src, m.start(), lines)
            body_start = m.start()
            body = src[body_start:body_start + 500]  # first 500 chars
            # skip obvious non-function matches
            if ret_type.startswith("//") or ret_type.startswith("*"):
                continue
            # skip control-flow keywords mistaken for function names
            if fname in self._CPP_KEYWORDS or ret_type in self._CPP_KEYWORDS:
                continue
            funcs.append(FunctionInfo(
                name=fname,
                return_type=ret_type,
                params=params,
                start_line=start_ln,
                end_line=end_ln,
                body=body,
            ))
        return funcs

    def _find_block_end(self, src: str, start: int, lines: List[str]) -> int:
        """Find the line number of the matching closing brace."""
        depth = 0
        for i, ch in enumerate(src[start:], start=start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return src[:i].count("\n") + 1
        return len(lines)

    def _extract_loops(
        self, src: str, lines: List[str]
    ) -> Tuple[List[LoopInfo], int, bool]:
        pattern_map = [
            (self._RE_FOR,   "for"),
            (self._RE_WHILE, "while"),
            (self._RE_DO,    "do_while"),
        ]

        # --- Pass 1: collect (LoopInfo, char_offset) pairs ---
        raw: List[Tuple[LoopInfo, int]] = []
        for pat, ltype in pattern_map:
            for m in pat.finditer(src):
                ln = src[:m.start()].count("\n") + 1
                raw.append((
                    LoopInfo(loop_type=ltype, line=ln, is_nested=False, depth=1),
                    m.start(),
                ))

        # Sort by line, keeping offset aligned with its LoopInfo
        raw.sort(key=lambda x: x[0].line)
        loop_infos   = [x[0] for x in raw]
        match_starts = [x[1] for x in raw]

        # Build all_loop_lines for callers that use it
        all_loop_lines = sorted(info.line for info in loop_infos)

        # --- Pass 2: compute block-end lines via brace counting ---
        loop_end_lines = [
            self._find_block_end(src, ms, lines) for ms in match_starts
        ]

        # --- Pass 3: structural nesting check ---
        max_depth = 1
        for i, info in enumerate(loop_infos):
            for j in range(len(loop_infos)):
                if i == j:
                    continue
                outer_start = loop_infos[j].line
                outer_end   = loop_end_lines[j]
                # info is nested inside j if info's start is strictly inside j's span
                if outer_start < info.line <= outer_end:
                    info.is_nested = True
                    max_depth = max(max_depth, 2)

        has_nested = any(l.is_nested for l in loop_infos)
        return loop_infos, max_depth, has_nested

    def _extract_array_accesses(
        self, src: str, lines: List[str]
    ) -> List[Dict]:
        accesses = []
        for m in self._RE_ARRAY_ACC.finditer(src):
            ln = src[:m.start()].count("\n") + 1
            idx_expr = m.group(2).strip()
            accesses.append({
                "array":   m.group(1),
                "index":   idx_expr,
                "line":    ln,
                "is_var_index": bool(re.search(r'[a-zA-Z]', idx_expr)),
            })
        return accesses

    def _find_uninitialized(self, src: str, lines: List[str]) -> List[Dict]:
        """
        Heuristic: look for declarations without initializers where the
        next non-empty statement does NOT assign to that variable.
        """
        results = []
        for m in self._RE_VAR_DECL.finditer(src):
            varname = m.group(1)
            ln      = src[:m.start()].count("\n") + 1
            # check if the rest of the file assigns the var before first use
            after   = src[m.end():]
            assign_pattern = re.compile(
                r'\b' + re.escape(varname) + r'\s*=[^=]'
            )
            use_pattern = re.compile(
                r'\b' + re.escape(varname) + r'\b'
            )
            use_m    = use_pattern.search(after)
            assign_m = assign_pattern.search(after)
            if use_m and (assign_m is None or use_m.start() < assign_m.start()):
                results.append({
                    "variable": varname,
                    "declared_line": ln,
                    "first_use_offset": use_m.start(),
                })
        return results

    def _extract_pointer_ops(self, src: str, lines: List[str]) -> List[Dict]:
        ops = []
        for m in self._RE_DEREF.finditer(src):
            ln = src[:m.start()].count("\n") + 1
            ops.append({"pointer": m.group(1), "line": ln, "op": "dereference"})
        return ops

    def _line_numbers_of(self, pattern: re.Pattern, lines: List[str]) -> List[int]:
        nums = []
        for i, ln in enumerate(lines, start=1):
            if pattern.search(ln):
                nums.append(i)
        return nums
