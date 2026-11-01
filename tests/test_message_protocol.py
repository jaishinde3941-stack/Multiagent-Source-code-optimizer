"""
Unit Tests for Message Protocol

Tests the message creation, serialization, and validation.
"""

import unittest
import json
from agent_framework.message_protocol import (
    Message, MessageType, MessagePriority, MessageValidator
)


class TestMessage(unittest.TestCase):
    """Test Message class"""
    
    def test_create_message(self):
        """Test message creation"""
        msg = Message.create(
            sender_id="agent_1",
            receiver_id="agent_2",
            message_type=MessageType.REQUEST,
            payload={"action": "test"},
            priority=MessagePriority.HIGH
        )
        
        self.assertEqual(msg.sender_id, "agent_1")
        self.assertEqual(msg.receiver_id, "agent_2")
        self.assertEqual(msg.message_type, MessageType.REQUEST)
        self.assertEqual(msg.priority, MessagePriority.HIGH)
        self.assertIsNotNone(msg.message_id)
        self.assertIsNotNone(msg.timestamp)
    
    def test_message_to_dict(self):
        """Test message serialization to dict"""
        msg = Message.create(
            sender_id="agent_1",
            receiver_id="agent_2",
            message_type=MessageType.NOTIFICATION,
            payload={"data": "test"}
        )
        
        msg_dict = msg.to_dict()
        
        self.assertEqual(msg_dict['sender_id'], "agent_1")
        self.assertEqual(msg_dict['receiver_id'], "agent_2")
        self.assertEqual(msg_dict['message_type'], "notification")
        self.assertEqual(msg_dict['priority'], "medium")
    
    def test_message_to_json(self):
        """Test message serialization to JSON"""
        msg = Message.create(
            sender_id="agent_1",
            receiver_id="agent_2",
            message_type=MessageType.REQUEST,
            payload={"action": "analyze"}
        )
        
        json_str = msg.to_json()
        parsed = json.loads(json_str)
        
        self.assertEqual(parsed['sender_id'], "agent_1")
        self.assertEqual(parsed['payload']['action'], "analyze")
    
    def test_message_from_dict(self):
        """Test message deserialization from dict"""
        msg = Message.create(
            sender_id="agent_1",
            receiver_id="agent_2",
            message_type=MessageType.RESPONSE,
            payload={"result": "success"}
        )
        
        msg_dict = msg.to_dict()
        reconstructed = Message.from_dict(msg_dict)
        
        self.assertEqual(reconstructed.sender_id, msg.sender_id)
        self.assertEqual(reconstructed.message_id, msg.message_id)
        self.assertEqual(reconstructed.message_type, msg.message_type)
    
    def test_message_from_json(self):
        """Test message deserialization from JSON"""
        msg = Message.create(
            sender_id="agent_1",
            receiver_id="agent_2",
            message_type=MessageType.REQUEST,
            payload={"test": "data"}
        )
        
        json_str = msg.to_json()
        reconstructed = Message.from_json(json_str)
        
        self.assertEqual(reconstructed.sender_id, msg.sender_id)
        self.assertEqual(reconstructed.payload, msg.payload)
    
    def test_create_response(self):
        """Test creating response to a message"""
        request = Message.create(
            sender_id="agent_1",
            receiver_id="agent_2",
            message_type=MessageType.REQUEST,
            payload={"action": "test"}
        )
        
        response = request.create_response(
            sender_id="agent_2",
            payload={"status": "success"}
        )
        
        self.assertEqual(response.sender_id, "agent_2")
        self.assertEqual(response.receiver_id, "agent_1")
        self.assertEqual(response.message_type, MessageType.RESPONSE)
        self.assertEqual(response.correlation_id, request.message_id)


class TestMessageValidator(unittest.TestCase):
    """Test MessageValidator class"""
    
    def test_validate_valid_message(self):
        """Test validation of valid message"""
        msg = Message.create(
            sender_id="agent_1",
            receiver_id="agent_2",
            message_type=MessageType.REQUEST,
            payload={"test": "data"}
        )
        
        is_valid, error = MessageValidator.validate(msg)
        
        self.assertTrue(is_valid)
        self.assertIsNone(error)
    
    def test_validate_response_needs_correlation_id(self):
        """Test that RESPONSE messages require correlation_id"""
        msg = Message.create(
            sender_id="agent_1",
            receiver_id="agent_2",
            message_type=MessageType.RESPONSE,
            payload={"result": "data"}
        )
        
        is_valid, error = MessageValidator.validate(msg)
        
        self.assertFalse(is_valid)
        self.assertIn("correlation_id", error)


if __name__ == '__main__':
    unittest.main()
