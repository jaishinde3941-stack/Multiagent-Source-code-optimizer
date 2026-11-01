"""
Unit Tests for Context Manager

Tests the shared context storage with versioning and rollback.
"""

import unittest
import threading
import time
from agent_framework.context_manager import ContextManager


class TestContextManager(unittest.TestCase):
    """Test ContextManager class"""
    
    def setUp(self):
        """Set up test context manager"""
        self.ctx = ContextManager()
    
    def test_set_and_get(self):
        """Test basic set and get operations"""
        self.ctx.set("test_key", "test_value")
        value = self.ctx.get("test_key")
        
        self.assertEqual(value, "test_value")
    
    def test_nested_keys(self):
        """Test nested key access with dot notation"""
        self.ctx.set("level1.level2.level3", "deep_value")
        value = self.ctx.get("level1.level2.level3")
        
        self.assertEqual(value, "deep_value")
    
    def test_get_default(self):
        """Test get with default value"""
        value = self.ctx.get("nonexistent", "default")
        
        self.assertEqual(value, "default")
    
    def test_update_multiple(self):
        """Test updating multiple keys at once"""
        self.ctx.update({
            "key1": "value1",
            "key2": "value2",
            "key3": "value3"
        })
        
        self.assertEqual(self.ctx.get("key1"), "value1")
        self.assertEqual(self.ctx.get("key2"), "value2")
        self.assertEqual(self.ctx.get("key3"), "value3")
    
    def test_append_to_list(self):
        """Test appending to a list"""
        self.ctx.set("my_list", [])
        self.ctx.append("my_list", "item1")
        self.ctx.append("my_list", "item2")
        
        result = self.ctx.get("my_list")
        
        self.assertEqual(result, ["item1", "item2"])
    
    def test_get_all(self):
        """Test getting entire context"""
        self.ctx.set("key1", "value1")
        self.ctx.set("key2", "value2")
        
        all_context = self.ctx.get_all()
        
        self.assertIn("key1", all_context)
        self.assertIn("key2", all_context)
    
    def test_versioning(self):
        """Test context versioning"""
        self.ctx.set("version_test", "v1")
        self.ctx.set("version_test", "v2")
        self.ctx.set("version_test", "v3")
        
        history = self.ctx.get_version_history()
        
        # Should have multiple versions
        self.assertGreater(len(history), 1)
    
    def test_rollback(self):
        """Test rollback to previous version"""
        self.ctx.set("rollback_test", "original")
        self.ctx.set("rollback_test", "modified")
        
        # Rollback
        success = self.ctx.rollback()
        
        self.assertTrue(success)
        self.assertEqual(self.ctx.get("rollback_test"), "original")
    
    def test_rollback_to_specific_version(self):
        """Test rollback to specific version ID"""
        self.ctx.set("test", "v1")
        history = self.ctx.get_version_history()
        version_id = history[-1]['version_id']
        
        self.ctx.set("test", "v2")
        self.ctx.set("test", "v3")
        
        # Rollback to specific version
        success = self.ctx.rollback(version_id)
        
        self.assertTrue(success)
        self.assertEqual(self.ctx.get("test"), "v1")
    
    def test_clear(self):
        """Test clearing context"""
        self.ctx.set("key1", "value1")
        self.ctx.set("key2", "value2")
        
        self.ctx.clear()
        
        self.assertIsNone(self.ctx.get("key1"))
        self.assertIsNone(self.ctx.get("key2"))
    
    def test_thread_safety(self):
        """Test thread-safe operations"""
        results = []
        
        def worker(thread_id):
            for i in range(10):
                self.ctx.set(f"thread_{thread_id}_key_{i}", f"value_{i}")
                value = self.ctx.get(f"thread_{thread_id}_key_{i}")
                results.append(value == f"value_{i}")
        
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        # All operations should have succeeded
        self.assertTrue(all(results))
    
    def test_to_json(self):
        """Test JSON export"""
        self.ctx.set("test_key", "test_value")
        json_str = self.ctx.to_json()
        
        self.assertIn("test_key", json_str)
        self.assertIn("test_value", json_str)


if __name__ == '__main__':
    unittest.main()
