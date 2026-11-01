"""
Prompt Templates for LLM-Powered Code Analysis

Structured prompts that enforce JSON output with chain-of-thought reasoning.
"""

ANALYSIS_PROMPT = """You are an expert C/C++ code analyzer. Analyze the following code and respond with a JSON object.

## Code to Analyze:
```cpp
{code}
```

## Instructions:
1. Identify the time and space complexity
2. Detect code patterns (e.g., nested loops, recursion, memory allocation)
3. Find potential bugs and issues (buffer overflow, memory leak, uninitialized variables, etc.)
4. Identify optimization opportunities
5. Provide a chain-of-thought reasoning for each finding

## Required JSON Output Format:
{{
    "complexity": {{
        "time": "O(...)",
        "space": "O(...)"
    }},
    "patterns": ["pattern1", "pattern2"],
    "issues": [
        {{
            "type": "bug_type",
            "severity": "high|medium|low",
            "line_hint": "description of where",
            "description": "what the issue is",
            "confidence": 0.0 to 1.0
        }}
    ],
    "optimization_opportunities": [
        {{
            "type": "optimization_type",
            "description": "what can be optimized",
            "expected_improvement": "description of improvement",
            "confidence": 0.0 to 1.0
        }}
    ],
    "reasoning_chain": [
        {{
            "step": 1,
            "observation": "what I noticed",
            "inference": "what this means",
            "conclusion": "what action to take"
        }}
    ]
}}

Respond ONLY with the JSON object. No markdown, no explanation outside JSON."""


OPTIMIZATION_PROMPT = """You are an expert C/C++ code optimizer. Given the original code and its analysis, generate an optimized version.

## Original Code:
```cpp
{code}
```

## Analysis Results:
{analysis}

## Instructions:
1. Fix all identified bugs and issues
2. Apply the suggested optimizations
3. Preserve the original functionality (same inputs must produce same outputs)
4. Provide the complete optimized code
5. Explain each transformation with reasoning

## Required JSON Output Format:
{{
    "optimized_code": "the complete optimized C++ code as a string",
    "transformations": [
        {{
            "type": "transformation_type",
            "description": "what was changed",
            "original_snippet": "relevant original code",
            "optimized_snippet": "relevant optimized code",
            "rationale": "why this change improves the code"
        }}
    ],
    "preserved_behavior": true,
    "reasoning_chain": [
        {{
            "step": 1,
            "observation": "what I noticed in the analysis",
            "action": "what transformation I applied",
            "justification": "why this is correct and better"
        }}
    ]
}}

Respond ONLY with the JSON object. No markdown, no explanation outside JSON."""


SECURITY_PROMPT = """You are an expert C/C++ security auditor. Analyze the following code for security vulnerabilities.

## Code to Audit:
```cpp
{code}
```

## Instructions:
1. Check for common vulnerabilities: buffer overflow, use-after-free, memory leaks, integer overflow, format string bugs, injection, race conditions, null pointer dereference, uninitialized variables
2. Rate each finding by severity (critical, high, medium, low)
3. Suggest specific fixes for each vulnerability
4. Provide chain-of-thought reasoning

## Required JSON Output Format:
{{
    "vulnerabilities": [
        {{
            "type": "vulnerability_type",
            "severity": "critical|high|medium|low",
            "cwe_id": "CWE-XXX if applicable",
            "line_hint": "description of where in the code",
            "description": "detailed description of the vulnerability",
            "impact": "what could happen if exploited",
            "fix_suggestion": "how to fix it",
            "confidence": 0.0 to 1.0
        }}
    ],
    "overall_risk": "critical|high|medium|low",
    "reasoning_chain": [
        {{
            "step": 1,
            "check": "what I checked",
            "finding": "what I found",
            "assessment": "severity and impact assessment"
        }}
    ],
    "summary": "brief overall security assessment"
}}

Respond ONLY with the JSON object. No markdown, no explanation outside JSON."""
