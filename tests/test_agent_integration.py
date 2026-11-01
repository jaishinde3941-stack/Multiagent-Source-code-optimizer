"""
Integration Tests for Multi-Agent Communication

Tests the complete agent communication workflow.
"""

import unittest
import time
import logging
from typing import Dict, Any, List

from agent_framework import (
    BaseAgent, AgentRegistry, ContextManager,
    MessageType, MessagePriority
)


class TestAgent(BaseAgent):
    """Test agent implementation"""
    
    def __init__(self, agent_id: str, context: ContextManager):
        super().__init__(agent_id, "test", context)
        self.processed_messages = []
    
    def get_capabilities(self) -> List[str]:
        return ["test_processing"]
    
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process input and return result"""
        self.processed_messages.append(input_data)
        return {
            "status": "processed",
            "input": input_data,
            "agent_id": self.agent_id
        }

    def _handle_notification(self, message):
        self.processed_messages.append(message.payload)
        super()._handle_notification(message)


class TestAgentCommunication(unittest.TestCase):
    """Test agent communication"""
    
    def setUp(self):
        """Set up test environment"""
        logging.basicConfig(level=logging.WARNING)
        self.ctx = ContextManager()
        self.registry = AgentRegistry()
    
    def tearDown(self):
        """Clean up"""
        self.registry.stop_all()
    
    def test_agent_registration(self):
        """Test agent registration"""
        agent = TestAgent("test_agent_1", self.ctx)
        
        success = self.registry.register(agent)
        
        self.assertTrue(success)
        self.assertEqual(len(self.registry), 1)
    
    def test_duplicate_registration(self):
        """Test that duplicate registration fails"""
        agent1 = TestAgent("test_agent_1", self.ctx)
        agent2 = TestAgent("test_agent_1", self.ctx)
        
        self.registry.register(agent1)
        success = self.registry.register(agent2)
        
        self.assertFalse(success)
    
    def test_agent_unregistration(self):
        """Test agent unregistration"""
        agent = TestAgent("test_agent_1", self.ctx)
        self.registry.register(agent)
        
        success = self.registry.unregister("test_agent_1")
        
        self.assertTrue(success)
        self.assertEqual(len(self.registry), 0)
    
    def test_get_agent(self):
        """Test retrieving agent by ID"""
        agent = TestAgent("test_agent_1", self.ctx)
        self.registry.register(agent)
        
        retrieved = self.registry.get_agent("test_agent_1")
        
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.agent_id, "test_agent_1")
    
    def test_message_routing(self):
        """Test message routing between agents"""
        agent1 = TestAgent("agent_1", self.ctx)
        agent2 = TestAgent("agent_2", self.ctx)
        
        self.registry.register(agent1)
        self.registry.register(agent2)
        
        # Start agents
        self.registry.start_all()
        time.sleep(0.1)  # Let agents start
        
        # Send message from agent1 to agent2
        agent1.send_message(
            receiver_id="agent_2",
            payload={"action": "test", "data": "hello"},
            message_type=MessageType.REQUEST,
            priority=MessagePriority.HIGH
        )
        
        # Wait for processing
        time.sleep(0.5)
        
        # Check that agent2 received and processed the message
        self.assertGreater(len(agent2.processed_messages), 0)
        self.assertEqual(agent2.processed_messages[0]['action'], "test")
    
    def test_request_response_pattern(self):
        """Test request-response message pattern"""
        agent1 = TestAgent("agent_1", self.ctx)
        agent2 = TestAgent("agent_2", self.ctx)
        
        self.registry.register(agent1)
        self.registry.register(agent2)
        
        self.registry.start_all()
        time.sleep(0.1)
        
        # Send request
        request_msg = agent1.send_message(
            receiver_id="agent_2",
            payload={"action": "process", "value": 42},
            message_type=MessageType.REQUEST
        )
        
        # Wait for processing
        time.sleep(0.5)
        
        # Verify message was processed
        self.assertGreater(len(agent2.processed_messages), 0)
    
    def test_multiple_agents_communication(self):
        """Test communication between multiple agents"""
        agents = [TestAgent(f"agent_{i}", self.ctx) for i in range(5)]
        
        for agent in agents:
            self.registry.register(agent)
        
        self.registry.start_all()
        time.sleep(0.1)
        
        # Each agent sends message to next agent
        for i in range(4):
            agents[i].send_message(
                receiver_id=f"agent_{i+1}",
                payload={"from": f"agent_{i}", "data": f"message_{i}"},
                message_type=MessageType.NOTIFICATION
            )
        
        # Wait for processing
        time.sleep(0.5)
        
        # Check that messages were received
        for i in range(1, 5):
            self.assertGreater(len(agents[i].processed_messages), 0)
    
    def test_registry_statistics(self):
        """Test registry statistics tracking"""
        agent1 = TestAgent("agent_1", self.ctx)
        agent2 = TestAgent("agent_2", self.ctx)
        
        self.registry.register(agent1)
        self.registry.register(agent2)
        
        self.registry.start_all()
        time.sleep(0.1)
        
        # Send some messages
        for i in range(3):
            agent1.send_message(
                receiver_id="agent_2",
                payload={"test": i},
                message_type=MessageType.NOTIFICATION
            )
        
        time.sleep(0.5)
        
        stats = self.registry.get_statistics()
        
        self.assertEqual(stats['total_agents'], 2)
        self.assertGreater(stats['total_messages'], 0)
    
    def test_agent_lifecycle(self):
        """Test agent start/stop lifecycle"""
        agent = TestAgent("test_agent", self.ctx)
        self.registry.register(agent)
        
        # Start agent
        agent.start()
        time.sleep(0.1)
        self.assertEqual(agent.get_state(), "running")
        
        # Stop agent
        agent.stop()
        time.sleep(0.1)
        self.assertEqual(agent.get_state(), "stopped")


if __name__ == '__main__':
    unittest.main()
