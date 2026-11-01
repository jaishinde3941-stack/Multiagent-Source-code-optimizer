# Multi-Agent Framework

A flexible, thread-safe multi-agent communication framework for the AI-Driven Compiler Optimization System.

## Features

- **Message-Based Communication**: JSON-based message protocol with request/response/notification patterns
- **Thread-Safe Context**: Shared context storage with versioning and rollback capability
- **Agent Lifecycle Management**: Start, stop, and manage agent lifecycles
- **Agent Registry**: Central registry for agent discovery and message routing
- **Priority-Based Message Queue**: High/medium/low priority message handling
- **Extensible Architecture**: Easy to create new agents by extending `BaseAgent`

## Project Structure

```
agent_framework/
├── __init__.py              # Package exports
├── message_protocol.py      # Message definitions and validation
├── context_manager.py       # Shared context with versioning
├── base_agent.py           # Abstract base agent class
└── agent_registry.py       # Agent registration and routing

tests/
├── __init__.py
├── test_message_protocol.py    # Message protocol tests
├── test_context_manager.py     # Context manager tests
└── test_agent_integration.py   # Integration tests

demo_multiagent.py          # Complete demo with example agents
```

## Quick Start

### 1. Run the Demo

```bash
python demo_multiagent.py
```

This demonstrates a complete Analysis → Optimization → Verification pipeline with three agents communicating.

### 2. Run Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_message_protocol.py -v

# Run with coverage
python -m pytest tests/ --cov=agent_framework --cov-report=html
```

### 3. Create Your Own Agent

```python
from agent_framework import BaseAgent, AgentRegistry, ContextManager
from typing import Dict, Any, List

class MyAgent(BaseAgent):
    """Custom agent implementation"""
    
    def get_capabilities(self) -> List[str]:
        return ["my_capability"]
    
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        # Your processing logic here
        result = {"status": "success"}
        return result

# Create context and registry
context = ContextManager()
registry = AgentRegistry()

# Create and register agent
my_agent = MyAgent("my_agent_1", "custom", context)
registry.register(my_agent)

# Start agent
my_agent.start()

# Send message
my_agent.send_message(
    receiver_id="another_agent",
    payload={"action": "process", "data": "test"}
)
```

## Core Components

### Message Protocol

Messages are the primary communication mechanism between agents:

```python
from agent_framework import Message, MessageType, MessagePriority

# Create a message
msg = Message.create(
    sender_id="agent_1",
    receiver_id="agent_2",
    message_type=MessageType.REQUEST,
    payload={"action": "analyze", "code": "..."},
    priority=MessagePriority.HIGH
)

# Create a response
response = msg.create_response(
    sender_id="agent_2",
    payload={"status": "success", "result": {...}}
)
```

### Context Manager

Thread-safe shared storage with versioning:

```python
from agent_framework import ContextManager

ctx = ContextManager()

# Set values (supports nested keys)
ctx.set("analysis_results.complexity", "O(n^2)")
ctx.append("optimization_suggestions", {...})

# Get values
complexity = ctx.get("analysis_results.complexity")

# Rollback to previous version
ctx.rollback()

# Get version history
history = ctx.get_version_history()
```

### Agent Registry

Central registry for agent management:

```python
from agent_framework import AgentRegistry

registry = AgentRegistry()

# Register agents
registry.register(agent1)
registry.register(agent2)

# Start all agents
registry.start_all()

# Get statistics
stats = registry.get_statistics()

# Stop all agents
registry.stop_all()
```

## Architecture

### Message Flow

```
Agent A                     Registry                    Agent B
   |                           |                           |
   |-- send_message() -------->|                           |
   |                           |-- route_message() ------->|
   |                           |                           |-- receive_message()
   |                           |                           |-- process()
   |                           |<----- send_message() -----|
   |<----- route_message() ----|                           |
   |-- receive_message()       |                           |
```

### Agent Lifecycle

```
INITIALIZED --> start() --> RUNNING --> stop() --> STOPPED
                              |
                              |--> reset() --> INITIALIZED
```

## Testing

The framework includes comprehensive tests:

- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test agent communication and message routing
- **Thread Safety Tests**: Verify concurrent operations

Run tests with:
```bash
python -m pytest tests/ -v --cov=agent_framework
```

## Example: Analysis Pipeline

See `demo_multiagent.py` for a complete example showing:

1. **Analysis Agent**: Detects code patterns and complexity
2. **Optimization Agent**: Generates code transformations
3. **Verification Agent**: Verifies correctness

The agents communicate via messages and share results through the context manager.

## Next Steps

- Integrate with LLM (Qwen 2.5 Coder) for semantic analysis
- Add more specialized agents (Security, Refinement, Orchestrator)
- Implement verification framework with Z3
- Add performance benchmarking

## License

Part of the AI-Driven Compiler Optimization System project.
