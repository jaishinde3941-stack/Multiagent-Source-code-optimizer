"""
Shared Analysis Infrastructure for Multi-Agent C/C++ Code Optimizer.
"""

from .finding_schema import Finding, deduplicate_findings
from .tool_runner import (
    ToolRunner,
    ToolStatus,
    ToolExecutionResult,
)

__all__ = [
    "Finding",
    "deduplicate_findings",
    "ToolRunner",
    "ToolStatus",
    "ToolExecutionResult",
]

