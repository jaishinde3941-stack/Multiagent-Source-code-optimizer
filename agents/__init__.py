"""
Agents Package (Legacy)

NOTE: The root-level 'agents' package is deprecated.
The canonical multi-agent architecture resides under 'src.agents' and 'src.pipeline.pipeline'.
"""

import warnings

warnings.warn(
    "The root-level 'agents' package is deprecated and will be removed in a future release. "
    "Please migrate to canonical agents in 'src.agents' and pipeline in 'src.pipeline.pipeline'.",
    DeprecationWarning,
    stacklevel=2,
)

from src.agents.analysis_agent import AnalysisAgent
from src.agents.optimization_agent import OptimizationAgent
from src.agents.verification_agent import VerificationAgent
from src.agents.security_agent import SecurityAgent
from .orchestrator_agent import OrchestratorAgent

__all__ = [
    'AnalysisAgent',
    'OptimizationAgent',
    'VerificationAgent',
    'SecurityAgent',
    'OrchestratorAgent',
]
