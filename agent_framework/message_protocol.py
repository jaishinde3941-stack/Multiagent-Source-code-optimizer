"""
Message Protocol for Multi-Agent Communication

This module defines the message schema and handling for inter-agent communication.
Messages are JSON-based and support request/response/notification patterns.
"""

import json
import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict


class MessageType(Enum):
    """Types of messages that can be sent between agents"""
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"


class MessagePriority(Enum):
    """Priority levels for message processing"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Message:
    """
    Message structure for inter-agent communication
    
    Attributes:
        message_id: Unique identifier for the message
        sender_id: ID of the sending agent
        receiver_id: ID of the receiving agent
        timestamp: ISO-8601 formatted timestamp
        message_type: Type of message (request/response/notification)
        payload: Message content (arbitrary JSON-serializable data)
        priority: Message priority level
        correlation_id: Optional ID linking responses to requests
    """
    message_id: str
    sender_id: str
    receiver_id: str
    timestamp: str
    message_type: MessageType
    payload: Dict[str, Any]
    priority: MessagePriority
    correlation_id: Optional[str] = None
    
    def __lt__(self, other: 'Message') -> bool:
        """Support ordering in PriorityQueue when priorities are equal."""
        if not isinstance(other, Message):
            return NotImplemented
        return (self.timestamp, self.message_id) < (other.timestamp, other.message_id)
    
    @staticmethod
    def create(sender_id: str, 
               receiver_id: str, 
               message_type: MessageType,
               payload: Dict[str, Any],
               priority: MessagePriority = MessagePriority.MEDIUM,
               correlation_id: Optional[str] = None) -> 'Message':
        """
        Factory method to create a new message
        
        Args:
            sender_id: ID of the sending agent
            receiver_id: ID of the receiving agent
            message_type: Type of message
            payload: Message content
            priority: Message priority (default: MEDIUM)
            correlation_id: Optional correlation ID for request/response pairing
            
        Returns:
            New Message instance
        """
        return Message(
            message_id=str(uuid.uuid4()),
            sender_id=sender_id,
            receiver_id=receiver_id,
            timestamp=datetime.utcnow().isoformat() + "Z",
            message_type=message_type,
            payload=payload,
            priority=priority,
            correlation_id=correlation_id
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary for serialization"""
        data = asdict(self)
        data['message_type'] = self.message_type.value
        data['priority'] = self.priority.value
        return data
    
    def to_json(self) -> str:
        """Convert message to JSON string"""
        return json.dumps(self.to_dict(), indent=2)
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'Message':
        """Create message from dictionary"""
        return Message(
            message_id=data['message_id'],
            sender_id=data['sender_id'],
            receiver_id=data['receiver_id'],
            timestamp=data['timestamp'],
            message_type=MessageType(data['message_type']),
            payload=data['payload'],
            priority=MessagePriority(data['priority']),
            correlation_id=data.get('correlation_id')
        )
    
    @staticmethod
    def from_json(json_str: str) -> 'Message':
        """Create message from JSON string"""
        data = json.loads(json_str)
        return Message.from_dict(data)
    
    def create_response(self, sender_id: str, payload: Dict[str, Any]) -> 'Message':
        """
        Create a response message to this message
        
        Args:
            sender_id: ID of the agent sending the response
            payload: Response payload
            
        Returns:
            New response message with correlation_id set
        """
        return Message.create(
            sender_id=sender_id,
            receiver_id=self.sender_id,
            message_type=MessageType.RESPONSE,
            payload=payload,
            priority=self.priority,
            correlation_id=self.message_id
        )


class MessageValidator:
    """Validates message structure and content"""
    
    @staticmethod
    def validate(message: Message) -> tuple[bool, Optional[str]]:
        """
        Validate a message
        
        Args:
            message: Message to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check required fields
        if not message.message_id:
            return False, "message_id is required"
        
        if not message.sender_id:
            return False, "sender_id is required"
        
        if not message.receiver_id:
            return False, "receiver_id is required"
        
        if not message.timestamp:
            return False, "timestamp is required"
        
        if message.payload is None:
            return False, "payload is required"
        
        # Check message type specific requirements
        if message.message_type == MessageType.RESPONSE:
            if not message.correlation_id:
                return False, "correlation_id is required for RESPONSE messages"
        
        return True, None


if __name__ == "__main__":
    # Example usage
    msg = Message.create(
        sender_id="analysis_agent",
        receiver_id="optimization_agent",
        message_type=MessageType.REQUEST,
        payload={
            "action": "analyze_code",
            "code": "for(int i=0; i<n; i++) { for(int j=0; j<n; j++) { sum += arr[i][j]; } }"
        },
        priority=MessagePriority.HIGH
    )
    
    print("Created message:")
    print(msg.to_json())
    
    # Create response
    response = msg.create_response(
        sender_id="optimization_agent",
        payload={
            "status": "success",
            "analysis": "O(n^2) nested loop detected"
        }
    )
    
    print("\nResponse message:")
    print(response.to_json())
