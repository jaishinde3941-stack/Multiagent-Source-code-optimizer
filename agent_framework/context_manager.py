"""
Shared Context Manager for Multi-Agent System

This module provides thread-safe shared context storage for agents to share
analysis results, code transformations, and other data.
"""

import threading
from typing import Dict, Any, Optional, List
from datetime import datetime
from copy import deepcopy
import json


class ContextVersion:
    """Represents a version of the context for rollback capability"""
    
    def __init__(self, version_id: int, data: Dict[str, Any], timestamp: str):
        self.version_id = version_id
        self.data = deepcopy(data)
        self.timestamp = timestamp


class ContextManager:
    """
    Thread-safe shared context storage for multi-agent system
    
    Features:
    - Thread-safe read/write operations
    - Context versioning for rollback
    - Query and update APIs
    - Support for nested data structures
    """
    
    def __init__(self, max_versions: int = 10):
        """
        Initialize context manager
        
        Args:
            max_versions: Maximum number of versions to keep for rollback
        """
        self._context: Dict[str, Any] = {}
        self._lock = threading.RLock()
        self._versions: List[ContextVersion] = []
        self._current_version = 0
        self._max_versions = max_versions
        
        # Initialize with empty structure
        self._context = {
            "original_code": None,
            "source_file": None,
            "analysis_results": {},
            "optimization_suggestions": [],
            "verification_status": {},
            "security_findings": [],
            "metadata": {}
        }
        
        self._save_version()
    
    def _save_version(self):
        """Save current context as a version"""
        with self._lock:
            version = ContextVersion(
                version_id=self._current_version,
                data=self._context,
                timestamp=datetime.utcnow().isoformat() + "Z"
            )
            self._versions.append(version)
            
            # Keep only max_versions
            if len(self._versions) > self._max_versions:
                self._versions.pop(0)
            
            self._current_version += 1
    
    def set(self, key: str, value: Any, save_version: bool = True):
        """
        Set a value in the context
        
        Args:
            key: Key to set (supports dot notation for nested keys)
            value: Value to set
            save_version: Whether to save a new version after this update
        """
        with self._lock:
            keys = key.split('.')
            current = self._context
            
            # Navigate to the nested location
            for k in keys[:-1]:
                if k not in current:
                    current[k] = {}
                current = current[k]
            
            # Set the value
            current[keys[-1]] = value
            
            if save_version:
                self._save_version()
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from the context
        
        Args:
            key: Key to get (supports dot notation for nested keys)
            default: Default value if key not found
            
        Returns:
            Value at the key, or default if not found
        """
        with self._lock:
            keys = key.split('.')
            current = self._context
            
            try:
                for k in keys:
                    current = current[k]
                return deepcopy(current)
            except (KeyError, TypeError):
                return default
    
    def update(self, updates: Dict[str, Any], save_version: bool = True):
        """
        Update multiple keys at once
        
        Args:
            updates: Dictionary of key-value pairs to update
            save_version: Whether to save a new version after updates
        """
        with self._lock:
            for key, value in updates.items():
                self.set(key, value, save_version=False)
            
            if save_version:
                self._save_version()
    
    def append(self, key: str, value: Any, save_version: bool = True):
        """
        Append a value to a list in the context
        
        Args:
            key: Key of the list
            value: Value to append
            save_version: Whether to save a new version
        """
        with self._lock:
            current_list = self.get(key, [])
            if not isinstance(current_list, list):
                raise ValueError(f"Key '{key}' is not a list")
            
            current_list.append(value)
            self.set(key, current_list, save_version=save_version)
    
    def get_all(self) -> Dict[str, Any]:
        """
        Get the entire context
        
        Returns:
            Deep copy of the entire context
        """
        with self._lock:
            return deepcopy(self._context)
    
    def rollback(self, version_id: Optional[int] = None) -> bool:
        """
        Rollback to a previous version
        
        Args:
            version_id: Version to rollback to (default: previous version)
            
        Returns:
            True if rollback successful, False otherwise
        """
        with self._lock:
            if not self._versions:
                return False
            
            if version_id is None:
                # Rollback to previous version
                if len(self._versions) < 2:
                    return False
                target_version = self._versions[-2]
            else:
                # Find specific version
                target_version = None
                for v in self._versions:
                    if v.version_id == version_id:
                        target_version = v
                        break
                
                if target_version is None:
                    return False
            
            self._context = deepcopy(target_version.data)
            self._save_version()
            return True
    
    def get_version_history(self) -> List[Dict[str, Any]]:
        """
        Get version history
        
        Returns:
            List of version metadata
        """
        with self._lock:
            return [
                {
                    "version_id": v.version_id,
                    "timestamp": v.timestamp
                }
                for v in self._versions
            ]
    
    def clear(self):
        """Clear all context data"""
        with self._lock:
            self._context = {
                "original_code": None,
                "source_file": None,
                "analysis_results": {},
                "optimization_suggestions": [],
                "verification_status": {},
                "security_findings": [],
                "metadata": {}
            }
            self._versions.clear()
            self._current_version = 0
            self._save_version()
    
    def to_json(self) -> str:
        """Export context to JSON string"""
        with self._lock:
            return json.dumps(self._context, indent=2)
    
    def __str__(self) -> str:
        """String representation of context"""
        return self.to_json()


if __name__ == "__main__":
    # Example usage
    ctx = ContextManager()
    
    # Set original code
    ctx.set("original_code", "int sum = 0; for(int i=0; i<n; i++) sum += arr[i];")
    ctx.set("source_file", "example.cpp")
    
    # Add analysis results
    ctx.set("analysis_results.complexity", "O(n)")
    ctx.set("analysis_results.patterns", ["linear_loop"])
    
    # Append optimization suggestion
    ctx.append("optimization_suggestions", {
        "type": "vectorization",
        "description": "Loop can be vectorized",
        "confidence": 0.9
    })
    
    print("Context:")
    print(ctx.to_json())
    
    print("\nVersion history:")
    print(json.dumps(ctx.get_version_history(), indent=2))
    
    # Test rollback
    ctx.set("analysis_results.complexity", "O(n^2)")  # Wrong update
    print("\nAfter wrong update:", ctx.get("analysis_results.complexity"))
    
    ctx.rollback()
    print("After rollback:", ctx.get("analysis_results.complexity"))
