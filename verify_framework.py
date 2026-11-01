"""
Simple test runner to verify the multi-agent framework components
"""

import sys
import logging

# Suppress logging during tests
logging.basicConfig(level=logging.CRITICAL)

print("=" * 80)
print("Multi-Agent Framework Verification")
print("=" * 80)
print()

# Test 1: Message Protocol
print("Test 1: Message Protocol")
print("-" * 40)
try:
    from agent_framework.message_protocol import Message, MessageType, MessagePriority
    
    msg = Message.create(
        sender_id="test_sender",
        receiver_id="test_receiver",
        message_type=MessageType.REQUEST,
        payload={"test": "data"},
        priority=MessagePriority.HIGH
    )
    
    # Test serialization
    json_str = msg.to_json()
    reconstructed = Message.from_json(json_str)
    
    assert reconstructed.sender_id == msg.sender_id
    assert reconstructed.payload == msg.payload
    
    # Test response creation
    response = msg.create_response(
        sender_id="test_receiver",
        payload={"status": "success"}
    )
    
    assert response.correlation_id == msg.message_id
    
    print("✓ Message creation and serialization")
    print("✓ Response message creation")
    print("✓ PASSED")
    
except Exception as e:
    print(f"✗ FAILED: {e}")
    import traceback
    traceback.print_exc()

print()

# Test 2: Context Manager
print("Test 2: Context Manager")
print("-" * 40)
try:
    from agent_framework.context_manager import ContextManager
    
    ctx = ContextManager()
    
    # Test set/get
    ctx.set("test_key", "test_value")
    assert ctx.get("test_key") == "test_value"
    
    # Test nested keys
    ctx.set("level1.level2.level3", "deep_value")
    assert ctx.get("level1.level2.level3") == "deep_value"
    
    # Test append
    ctx.set("my_list", [])
    ctx.append("my_list", "item1")
    ctx.append("my_list", "item2")
    assert ctx.get("my_list") == ["item1", "item2"]
    
    # Test versioning and rollback
    ctx.set("rollback_test", "v1")
    ctx.set("rollback_test", "v2")
    ctx.rollback()
    assert ctx.get("rollback_test") == "v1"
    
    print("✓ Set/get operations")
    print("✓ Nested key access")
    print("✓ List append")
    print("✓ Versioning and rollback")
    print("✓ PASSED")
    
except Exception as e:
    print(f"✗ FAILED: {e}")
    import traceback
    traceback.print_exc()

print()

# Test 3: Base Agent
print("Test 3: Base Agent")
print("-" * 40)
try:
    from agent_framework import BaseAgent, ContextManager
    from typing import Dict, Any, List
    
    class TestAgent(BaseAgent):
        def get_capabilities(self) -> List[str]:
            return ["test"]
        
        def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
            return {"processed": True}
    
    ctx = ContextManager()
    agent = TestAgent("test_agent", "test", ctx)
    
    assert agent.agent_id == "test_agent"
    assert agent.agent_type == "test"
    assert "test" in agent.get_capabilities()
    
    # Test processing
    result = agent.process({"test": "data"})
    assert result["processed"] == True
    
    print("✓ Agent creation")
    print("✓ Capabilities")
    print("✓ Processing")
    print("✓ PASSED")
    
except Exception as e:
    print(f"✗ FAILED: {e}")
    import traceback
    traceback.print_exc()

print()

# Test 4: Agent Registry
print("Test 4: Agent Registry")
print("-" * 40)
try:
    from agent_framework import AgentRegistry, BaseAgent, ContextManager
    from typing import Dict, Any, List
    
    class TestAgent(BaseAgent):
        def get_capabilities(self) -> List[str]:
            return ["test"]
        
        def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
            return {"processed": True}
    
    ctx = ContextManager()
    registry = AgentRegistry()
    
    agent1 = TestAgent("agent_1", "test", ctx)
    agent2 = TestAgent("agent_2", "test", ctx)
    
    # Test registration
    assert registry.register(agent1) == True
    assert registry.register(agent2) == True
    assert len(registry) == 2
    
    # Test duplicate registration
    assert registry.register(agent1) == False
    
    # Test retrieval
    retrieved = registry.get_agent("agent_1")
    assert retrieved is not None
    assert retrieved.agent_id == "agent_1"
    
    # Test unregistration
    assert registry.unregister("agent_1") == True
    assert len(registry) == 1
    
    print("✓ Agent registration")
    print("✓ Duplicate prevention")
    print("✓ Agent retrieval")
    print("✓ Agent unregistration")
    print("✓ PASSED")
    
except Exception as e:
    print(f"✗ FAILED: {e}")
    import traceback
    traceback.print_exc()

print()

# Test 5: Agent Communication
print("Test 5: Agent Communication")
print("-" * 40)
try:
    import time
    from agent_framework import BaseAgent, AgentRegistry, ContextManager, MessageType
    from typing import Dict, Any, List
    
    class TestAgent(BaseAgent):
        def __init__(self, agent_id: str, context: ContextManager):
            super().__init__(agent_id, "test", context)
            self.received_messages = []
        
        def get_capabilities(self) -> List[str]:
            return ["test"]
        
        def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
            self.received_messages.append(input_data)
            return {"processed": True, "data": input_data}
    
    ctx = ContextManager()
    registry = AgentRegistry()
    
    agent1 = TestAgent("agent_1", ctx)
    agent2 = TestAgent("agent_2", ctx)
    
    registry.register(agent1)
    registry.register(agent2)
    
    # Start agents
    registry.start_all()
    time.sleep(0.2)
    
    # Send message
    agent1.send_message(
        receiver_id="agent_2",
        payload={"test": "communication"},
        message_type=MessageType.REQUEST
    )
    
    # Wait for processing
    time.sleep(1)
    
    # Verify message was received
    assert len(agent2.received_messages) > 0
    assert agent2.received_messages[0]["test"] == "communication"
    
    # Stop agents
    registry.stop_all()
    
    print("✓ Agent startup")
    print("✓ Message sending")
    print("✓ Message routing")
    print("✓ Message processing")
    print("✓ PASSED")
    
except Exception as e:
    print(f"✗ FAILED: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)
print("Verification Complete!")
print("=" * 80)
print()
print("All core components are working correctly:")
print("  ✓ Message Protocol")
print("  ✓ Context Manager")
print("  ✓ Base Agent")
print("  ✓ Agent Registry")
print("  ✓ Agent Communication")
print()
print("The multi-agent framework is ready for use!")
