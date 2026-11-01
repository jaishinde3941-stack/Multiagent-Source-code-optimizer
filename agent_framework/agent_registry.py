"""
Agent Registry for Multi-Agent System

This module provides agent registration, discovery, and message routing.
"""

import threading
from typing import Dict, Optional, List
import logging

from .base_agent import BaseAgent
from .message_protocol import Message


class AgentRegistry:
    """
    Central registry for agent management and message routing
    
    Features:
    - Agent registration and discovery
    - Message routing between agents
    - Agent lifecycle management
    """
    
    def __init__(self):
        """Initialize agent registry"""
        self._agents: Dict[str, BaseAgent] = {}
        self._lock = threading.RLock()
        self.logger = logging.getLogger("AgentRegistry")
        self.logger.setLevel(logging.INFO)
        
        # Message statistics
        self._message_count = 0
        self._message_stats: Dict[str, int] = {}
    
    def register(self, agent: BaseAgent) -> bool:
        """
        Register an agent
        
        Args:
            agent: Agent to register
            
        Returns:
            True if registration successful, False if agent_id already exists
        """
        with self._lock:
            if agent.agent_id in self._agents:
                self.logger.warning(f"Agent {agent.agent_id} already registered")
                return False
            
            self._agents[agent.agent_id] = agent
            agent.set_registry(self)
            
            self.logger.info(f"Registered agent: {agent.agent_id} ({agent.agent_type})")
            return True
    
    def unregister(self, agent_id: str) -> bool:
        """
        Unregister an agent
        
        Args:
            agent_id: ID of agent to unregister
            
        Returns:
            True if unregistration successful, False if agent not found
        """
        with self._lock:
            if agent_id not in self._agents:
                self.logger.warning(f"Agent {agent_id} not found")
                return False
            
            agent = self._agents[agent_id]
            agent.stop()
            del self._agents[agent_id]
            
            self.logger.info(f"Unregistered agent: {agent_id}")
            return True
    
    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        """
        Get an agent by ID
        
        Args:
            agent_id: ID of agent to retrieve
            
        Returns:
            Agent instance or None if not found
        """
        with self._lock:
            return self._agents.get(agent_id)
    
    def get_agents_by_type(self, agent_type: str) -> List[BaseAgent]:
        """
        Get all agents of a specific type
        
        Args:
            agent_type: Type of agents to retrieve
            
        Returns:
            List of agents matching the type
        """
        with self._lock:
            return [
                agent for agent in self._agents.values()
                if agent.agent_type == agent_type
            ]
    
    def get_all_agents(self) -> List[BaseAgent]:
        """
        Get all registered agents
        
        Returns:
            List of all agents
        """
        with self._lock:
            return list(self._agents.values())
    
    def route_message(self, message: Message) -> bool:
        """
        Route a message to the appropriate agent
        
        Args:
            message: Message to route
            
        Returns:
            True if message delivered, False if receiver not found
        """
        with self._lock:
            receiver = self._agents.get(message.receiver_id)
            
            if receiver is None:
                self.logger.error(f"Receiver {message.receiver_id} not found for message {message.message_id}")
                return False
            
            receiver.receive_message(message)
            
            # Update statistics
            self._message_count += 1
            route_key = f"{message.sender_id}->{message.receiver_id}"
            self._message_stats[route_key] = self._message_stats.get(route_key, 0) + 1
            
            self.logger.debug(f"Routed message {message.message_id} from {message.sender_id} to {message.receiver_id}")
            return True
    
    def start_all(self):
        """Start all registered agents"""
        with self._lock:
            for agent in self._agents.values():
                agent.start()
            self.logger.info(f"Started {len(self._agents)} agents")
    
    def stop_all(self, timeout: float = 5.0):
        """
        Stop all registered agents
        
        Args:
            timeout: Maximum time to wait for each agent to stop
        """
        with self._lock:
            for agent in self._agents.values():
                agent.stop(timeout=timeout)
            self.logger.info(f"Stopped {len(self._agents)} agents")
    
    def get_statistics(self) -> Dict[str, any]:
        """
        Get registry statistics
        
        Returns:
            Dictionary with statistics
        """
        with self._lock:
            return {
                "total_agents": len(self._agents),
                "agents_by_type": self._get_agent_type_counts(),
                "total_messages": self._message_count,
                "message_routes": dict(self._message_stats)
            }
    
    def _get_agent_type_counts(self) -> Dict[str, int]:
        """Get count of agents by type"""
        counts = {}
        for agent in self._agents.values():
            counts[agent.agent_type] = counts.get(agent.agent_type, 0) + 1
        return counts
    
    def list_agents(self) -> List[Dict[str, str]]:
        """
        List all agents with their metadata
        
        Returns:
            List of agent information dictionaries
        """
        with self._lock:
            return [
                {
                    "agent_id": agent.agent_id,
                    "agent_type": agent.agent_type,
                    "state": agent.get_state(),
                    "capabilities": agent.get_capabilities()
                }
                for agent in self._agents.values()
            ]
    
    def __len__(self) -> int:
        """Return number of registered agents"""
        with self._lock:
            return len(self._agents)
    
    def __repr__(self) -> str:
        return f"<AgentRegistry agents={len(self._agents)} messages={self._message_count}>"


if __name__ == "__main__":
    # Example usage
    from .context_manager import ContextManager
    
    # Example agent
    class TestAgent(BaseAgent):
        def get_capabilities(self) -> List[str]:
            return ["test"]
        
        def process(self, input_data: Dict) -> Dict:
            return {"result": "processed"}
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    # Create registry and context
    registry = AgentRegistry()
    ctx = ContextManager()
    
    # Create and register agents
    agent1 = TestAgent("agent_1", "test", ctx)
    agent2 = TestAgent("agent_2", "test", ctx)
    
    registry.register(agent1)
    registry.register(agent2)
    
    print(registry)
    print("\nAgent list:")
    for agent_info in registry.list_agents():
        print(f"  - {agent_info}")
    
    print("\nStatistics:")
    import json
    print(json.dumps(registry.get_statistics(), indent=2))
