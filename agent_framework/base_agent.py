"""
Base Agent Class for Multi-Agent System

This module provides the abstract base class that all agents inherit from.
It handles message passing, state management, and lifecycle operations.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import queue
import threading
import logging
from datetime import datetime

from .message_protocol import Message, MessageType, MessagePriority
from .context_manager import ContextManager


class AgentState:
    """Agent state enumeration"""
    INITIALIZED = "initialized"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the multi-agent system
    
    Features:
    - Message-based communication
    - State management
    - Lifecycle hooks
    - Logging and monitoring
    """
    
    def __init__(self, 
                 agent_id: str, 
                 agent_type: str,
                 context_manager: ContextManager,
                 max_queue_size: int = 100):
        """
        Initialize base agent
        
        Args:
            agent_id: Unique identifier for this agent
            agent_type: Type of agent (e.g., "analysis", "optimization")
            context_manager: Shared context manager
            max_queue_size: Maximum size of message queue
        """
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.context = context_manager
        
        # Message queue for incoming messages
        self._message_queue = queue.PriorityQueue(maxsize=max_queue_size)
        
        # State management
        self._state = AgentState.INITIALIZED
        self._state_lock = threading.Lock()
        
        # Message processing thread
        self._processing_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Agent registry reference (set by registry)
        self._registry = None
        
        # Logging
        self.logger = logging.getLogger(f"Agent.{agent_id}")
        self.logger.setLevel(logging.INFO)
        
        # Metadata
        self.metadata = {
            "agent_id": agent_id,
            "agent_type": agent_type,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "capabilities": self.get_capabilities()
        }
        
        self.logger.info(f"Agent {agent_id} ({agent_type}) initialized")
    
    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """
        Return list of capabilities this agent provides
        
        Returns:
            List of capability names
        """
        pass
    
    @abstractmethod
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main processing method - must be implemented by subclasses
        
        Args:
            input_data: Input data to process
            
        Returns:
            Processing results
        """
        pass
    
    def send_message(self, 
                     receiver_id: str, 
                     payload: Dict[str, Any],
                     message_type: MessageType = MessageType.REQUEST,
                     priority: MessagePriority = MessagePriority.MEDIUM,
                     correlation_id: Optional[str] = None) -> Message:
        """
        Send a message to another agent
        
        Args:
            receiver_id: ID of the receiving agent
            payload: Message payload
            message_type: Type of message
            priority: Message priority
            correlation_id: Optional correlation ID
            
        Returns:
            The sent message
        """
        message = Message.create(
            sender_id=self.agent_id,
            receiver_id=receiver_id,
            message_type=message_type,
            payload=payload,
            priority=priority,
            correlation_id=correlation_id
        )
        
        self.logger.debug(f"Sending {message_type.value} to {receiver_id}")
        
        # Send via registry if available
        if self._registry:
            self._registry.route_message(message)
        else:
            self.logger.warning("No registry available, message not sent")
        
        return message
    
    def receive_message(self, message: Message):
        """
        Receive a message (called by registry)
        
        Args:
            message: Message to receive
        """
        # Priority: HIGH=0, MEDIUM=1, LOW=2 (lower number = higher priority)
        priority_map = {
            MessagePriority.HIGH: 0,
            MessagePriority.MEDIUM: 1,
            MessagePriority.LOW: 2
        }
        
        try:
            self._message_queue.put(
                (priority_map[message.priority], message),
                block=False
            )
            self.logger.debug(f"Received {message.message_type.value} from {message.sender_id}")
        except queue.Full:
            self.logger.error(f"Message queue full, dropping message {message.message_id}")
    
    def _process_messages(self):
        """Internal method to process messages from queue"""
        while not self._stop_event.is_set():
            try:
                # Wait for message with timeout
                priority, message = self._message_queue.get(timeout=0.1)
                
                self.logger.info(f"Processing message {message.message_id} from {message.sender_id}")
                
                # Handle message based on type
                if message.message_type == MessageType.REQUEST:
                    self._handle_request(message)
                elif message.message_type == MessageType.RESPONSE:
                    self._handle_response(message)
                elif message.message_type == MessageType.NOTIFICATION:
                    self._handle_notification(message)
                
                self._message_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Error processing message: {e}", exc_info=True)
    
    def _handle_request(self, message: Message):
        """Handle incoming request message"""
        try:
            # Process the request
            result = self.process(message.payload)
            
            # Send response
            self.send_message(
                receiver_id=message.sender_id,
                payload={"status": "success", "result": result},
                message_type=MessageType.RESPONSE,
                priority=message.priority,
                correlation_id=message.message_id
            )
        except Exception as e:
            self.logger.error(f"Error handling request: {e}", exc_info=True)
            # Send error response
            self.send_message(
                receiver_id=message.sender_id,
                payload={"status": "error", "error": str(e)},
                message_type=MessageType.RESPONSE,
                priority=message.priority,
                correlation_id=message.message_id
            )
    
    def _handle_response(self, message: Message):
        """Handle incoming response message - can be overridden"""
        self.logger.info(f"Received response: {message.payload.get('status')}")
    
    def _handle_notification(self, message: Message):
        """Handle incoming notification - can be overridden"""
        self.logger.info(f"Received notification: {message.payload}")
    
    def start(self):
        """Start the agent (begin processing messages)"""
        with self._state_lock:
            if self._state == AgentState.RUNNING:
                self.logger.warning("Agent already running")
                return
            
            self._stop_event.clear()
            self._processing_thread = threading.Thread(
                target=self._process_messages,
                name=f"{self.agent_id}_processor",
                daemon=True
            )
            self._processing_thread.start()
            self._state = AgentState.RUNNING
            
            self.logger.info(f"Agent {self.agent_id} started")
    
    def stop(self, timeout: float = 5.0):
        """
        Stop the agent
        
        Args:
            timeout: Maximum time to wait for graceful shutdown
        """
        with self._state_lock:
            if self._state != AgentState.RUNNING:
                return
            
            self.logger.info(f"Stopping agent {self.agent_id}")
            self._stop_event.set()
            
            if self._processing_thread:
                self._processing_thread.join(timeout=timeout)
            
            self._state = AgentState.STOPPED
            self.logger.info(f"Agent {self.agent_id} stopped")
    
    def get_state(self) -> str:
        """Get current agent state"""
        with self._state_lock:
            return self._state
    
    def reset(self):
        """Reset agent state"""
        with self._state_lock:
            if self._state == AgentState.RUNNING:
                self.stop()
            
            # Clear message queue
            while not self._message_queue.empty():
                try:
                    self._message_queue.get_nowait()
                except queue.Empty:
                    break
            
            self._state = AgentState.INITIALIZED
            self.logger.info(f"Agent {self.agent_id} reset")
    
    def set_registry(self, registry):
        """Set the agent registry (called by registry)"""
        self._registry = registry
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.agent_id} type={self.agent_type} state={self._state}>"


if __name__ == "__main__":
    # Example concrete agent implementation
    class ExampleAgent(BaseAgent):
        def get_capabilities(self) -> List[str]:
            return ["example_processing"]
        
        def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
            return {"processed": True, "input": input_data}
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    # Create context and agent
    ctx = ContextManager()
    agent = ExampleAgent("example_1", "example", ctx)
    
    print(agent)
    print(f"Capabilities: {agent.get_capabilities()}")
    print(f"State: {agent.get_state()}")
