"""
Multi-Agent Framework Demo

Demonstrates the multi-agent communication framework with example agents.
"""

import logging
import time
from typing import Dict, Any, List

from agent_framework import (
    BaseAgent, AgentRegistry, ContextManager,
    MessageType, MessagePriority
)


class AnalysisAgent(BaseAgent):
    """Example Analysis Agent that detects code patterns"""
    
    def get_capabilities(self) -> List[str]:
        return ["code_analysis", "pattern_detection", "complexity_analysis"]
    
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze code and detect patterns"""
        code = input_data.get("code", "")
        
        self.logger.info(f"Analyzing code: {code[:50]}...")
        
        # Simulate analysis
        time.sleep(0.5)
        
        # Detect nested loops (simple pattern matching)
        has_nested_loops = "for" in code and code.count("for") > 1
        
        analysis_result = {
            "complexity": "O(n^2)" if has_nested_loops else "O(n)",
            "patterns": ["nested_loops"] if has_nested_loops else ["linear_loop"],
            "optimization_opportunities": [
                {
                    "type": "loop_optimization",
                    "description": "Nested loop detected, consider hash-based approach",
                    "confidence": 0.85
                }
            ] if has_nested_loops else []
        }
        
        # Store in context
        self.context.set("analysis_results", analysis_result)
        
        self.logger.info(f"Analysis complete: {analysis_result['complexity']}")
        
        # Notify optimization agent
        if analysis_result["optimization_opportunities"]:
            self.send_message(
                receiver_id="optimization_agent",
                payload={
                    "action": "optimize",
                    "code": code,
                    "analysis": analysis_result
                },
                message_type=MessageType.REQUEST,
                priority=MessagePriority.HIGH
            )
        
        return analysis_result


class OptimizationAgent(BaseAgent):
    """Example Optimization Agent that generates code transformations"""
    
    def get_capabilities(self) -> List[str]:
        return ["code_optimization", "transformation_generation"]
    
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate optimized code"""
        code = input_data.get("code", "")
        analysis = input_data.get("analysis", {})
        
        self.logger.info("Generating optimization suggestions...")
        
        # Simulate optimization
        time.sleep(0.5)
        
        optimization_result = {
            "original_code": code,
            "optimized_code": code.replace("for", "// Optimized for"),
            "transformations": [
                {
                    "type": "algorithm_replacement",
                    "description": "Replace nested loops with hash-based lookup",
                    "expected_improvement": "80% faster for n>1000"
                }
            ],
            "rationale": "Nested loops have O(n^2) complexity. Hash-based approach reduces to O(n)."
        }
        
        # Store in context
        self.context.append("optimization_suggestions", optimization_result)
        
        self.logger.info("Optimization suggestions generated")
        
        # Notify verification agent
        self.send_message(
            receiver_id="verification_agent",
            payload={
                "action": "verify",
                "original": code,
                "optimized": optimization_result["optimized_code"]
            },
            message_type=MessageType.REQUEST,
            priority=MessagePriority.HIGH
        )
        
        return optimization_result


class VerificationAgent(BaseAgent):
    """Example Verification Agent that checks correctness"""
    
    def get_capabilities(self) -> List[str]:
        return ["correctness_verification", "differential_testing"]
    
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Verify optimized code correctness"""
        original = input_data.get("original", "")
        optimized = input_data.get("optimized", "")
        
        self.logger.info("Verifying code correctness...")
        
        # Simulate verification
        time.sleep(0.5)
        
        verification_result = {
            "status": "passed",
            "correctness": True,
            "tests_passed": 10,
            "tests_failed": 0,
            "verification_methods": ["differential_testing", "symbolic_execution"]
        }
        
        # Store in context
        self.context.set("verification_status", verification_result)
        
        self.logger.info(f"Verification complete: {verification_result['status']}")
        
        return verification_result


def main():
    """Run the multi-agent framework demo"""
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 80)
    print("Multi-Agent Framework Demo")
    print("=" * 80)
    print()
    
    # Create shared context
    print("Creating shared context...")
    context = ContextManager()
    
    # Create agent registry
    print("Creating agent registry...")
    registry = AgentRegistry()
    
    # Create agents
    print("Creating agents...")
    analysis_agent = AnalysisAgent("analysis_agent", "analysis", context)
    optimization_agent = OptimizationAgent("optimization_agent", "optimization", context)
    verification_agent = VerificationAgent("verification_agent", "verification", context)
    
    # Register agents
    print("Registering agents...")
    registry.register(analysis_agent)
    registry.register(optimization_agent)
    registry.register(verification_agent)
    
    # Start all agents
    print("Starting agents...")
    registry.start_all()
    time.sleep(0.2)  # Let agents start
    
    print()
    print("Agents registered and started:")
    for agent_info in registry.list_agents():
        print(f"  - {agent_info['agent_id']} ({agent_info['agent_type']})")
        print(f"    Capabilities: {', '.join(agent_info['capabilities'])}")
        print(f"    State: {agent_info['state']}")
    
    print()
    print("=" * 80)
    print("Running Analysis → Optimization → Verification Pipeline")
    print("=" * 80)
    print()
    
    # Set test code in context
    test_code = """
    int sum = 0;
    for(int i = 0; i < n; i++) {
        for(int j = 0; j < n; j++) {
            sum += arr[i][j];
        }
    }
    """
    
    context.set("original_code", test_code)
    
    print("Test Code:")
    print(test_code)
    print()
    
    # Trigger analysis
    print("Sending analysis request...")
    analysis_agent.send_message(
        receiver_id="analysis_agent",  # Send to self to trigger processing
        payload={"action": "analyze", "code": test_code},
        message_type=MessageType.REQUEST
    )
    
    # Wait for pipeline to complete
    print("Processing...")
    time.sleep(3)
    
    print()
    print("=" * 80)
    print("Pipeline Results")
    print("=" * 80)
    print()
    
    # Display results from context
    analysis_results = context.get("analysis_results")
    if analysis_results:
        print("Analysis Results:")
        print(f"  Complexity: {analysis_results.get('complexity')}")
        print(f"  Patterns: {', '.join(analysis_results.get('patterns', []))}")
        print(f"  Optimization Opportunities: {len(analysis_results.get('optimization_opportunities', []))}")
        print()
    
    optimization_suggestions = context.get("optimization_suggestions", [])
    if optimization_suggestions:
        print("Optimization Suggestions:")
        for i, opt in enumerate(optimization_suggestions, 1):
            print(f"  {i}. {opt.get('transformations', [{}])[0].get('description', 'N/A')}")
            print(f"     Rationale: {opt.get('rationale', 'N/A')}")
        print()
    
    verification_status = context.get("verification_status")
    if verification_status:
        print("Verification Status:")
        print(f"  Status: {verification_status.get('status')}")
        print(f"  Correctness: {verification_status.get('correctness')}")
        print(f"  Tests Passed: {verification_status.get('tests_passed')}")
        print()
    
    # Display statistics
    print("=" * 80)
    print("Registry Statistics")
    print("=" * 80)
    print()
    
    stats = registry.get_statistics()
    print(f"Total Agents: {stats['total_agents']}")
    print(f"Total Messages: {stats['total_messages']}")
    print(f"Message Routes:")
    for route, count in stats['message_routes'].items():
        print(f"  {route}: {count} messages")
    
    print()
    print("=" * 80)
    print("Context Version History")
    print("=" * 80)
    print()
    
    history = context.get_version_history()
    print(f"Total Versions: {len(history)}")
    for version in history[-5:]:  # Show last 5 versions
        print(f"  Version {version['version_id']}: {version['timestamp']}")
    
    # Stop all agents
    print()
    print("Stopping agents...")
    registry.stop_all()
    
    print()
    print("=" * 80)
    print("Demo Complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
