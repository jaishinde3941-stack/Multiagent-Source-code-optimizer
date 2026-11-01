"""
Agent Framework Package

Multi-agent communication framework for AI-Driven Compiler Optimization System
"""

from .message_protocol import Message, MessageType, MessagePriority, MessageValidator
from .context_manager import ContextManager
from .base_agent import BaseAgent, AgentState
from .agent_registry import AgentRegistry

__all__ = [
    'Message',
    'MessageType',
    'MessagePriority',
    'MessageValidator',
    'ContextManager',
    'BaseAgent',
    'AgentState',
    'AgentRegistry'
]

__version__ = '0.1.0'
