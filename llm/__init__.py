"""
LLM Integration Package

Provides Ollama client and prompt templates for AI-powered code analysis.
"""

from .ollama_client import OllamaClient
from .prompts import ANALYSIS_PROMPT, OPTIMIZATION_PROMPT, SECURITY_PROMPT

__all__ = [
    'OllamaClient',
    'ANALYSIS_PROMPT',
    'OPTIMIZATION_PROMPT',
    'SECURITY_PROMPT',
]
