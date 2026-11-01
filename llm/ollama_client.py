"""
Ollama Client for LLM Integration

Wraps the Ollama REST API for generating code analysis, optimization,
and security suggestions using Qwen 2.5 Coder 7B.
"""

import json
import logging
import time
from typing import Optional, Dict, Any

import requests

logger = logging.getLogger(__name__)


class OllamaClient:
    """Client for interacting with Ollama API"""

    def __init__(
        self,
        model: str = "qwen2.5-coder:7b",
        base_url: str = "http://localhost:11434",
        timeout: int = 120,
        max_retries: int = 2,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

    def is_available(self) -> bool:
        """Check if Ollama server is running and model is loaded."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if resp.status_code != 200:
                return False
            models = [m["name"] for m in resp.json().get("models", [])]
            # Check if our model (or a prefix match) is available
            return any(self.model in m for m in models)
        except requests.ConnectionError:
            return False
        except Exception as e:
            logger.error(f"Error checking Ollama availability: {e}")
            return False

    def generate(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        system: Optional[str] = None,
    ) -> str:
        """
        Generate a text completion from Ollama.

        Args:
            prompt: The prompt to send
            temperature: Sampling temperature (lower = more deterministic)
            max_tokens: Maximum tokens in response
            system: Optional system prompt

        Returns:
            Generated text response
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system:
            payload["system"] = system

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = requests.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                return resp.json().get("response", "")
            except requests.ConnectionError as e:
                last_error = e
                logger.warning(
                    f"Connection error (attempt {attempt + 1}/{self.max_retries + 1}): {e}"
                )
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
            except requests.Timeout as e:
                last_error = e
                logger.warning(f"Timeout (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries:
                    time.sleep(2)
            except requests.HTTPError as e:
                last_error = e
                logger.error(f"HTTP error: {e}")
                break

        raise ConnectionError(
            f"Failed to generate after {self.max_retries + 1} attempts: {last_error}"
        )

    def generate_json(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        system: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a JSON response from Ollama.

        Attempts to parse the response as JSON. If parsing fails,
        retries with an explicit JSON instruction appended.

        Args:
            prompt: The prompt (should request JSON output)
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            system: Optional system prompt

        Returns:
            Parsed JSON dict
        """
        raw = self.generate(prompt, temperature, max_tokens, system)
        result = self._try_parse_json(raw)
        if result is not None:
            return result

        # Retry with explicit JSON instruction
        logger.warning("JSON parse failed, retrying with explicit instruction")
        retry_prompt = (
            prompt
            + "\n\nIMPORTANT: You MUST respond with valid JSON only. "
            "No markdown, no explanation, just the JSON object."
        )
        raw = self.generate(retry_prompt, temperature, max_tokens, system)
        result = self._try_parse_json(raw)
        if result is not None:
            return result

        raise ValueError(f"Failed to parse JSON from LLM response: {raw[:500]}")

    @staticmethod
    def _try_parse_json(text: str) -> Optional[Dict[str, Any]]:
        """Try to extract and parse JSON from text."""
        text = text.strip()

        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code block
        if "```" in text:
            for block_marker in ["```json", "```"]:
                if block_marker in text:
                    start = text.index(block_marker) + len(block_marker)
                    end = text.index("```", start)
                    candidate = text[start:end].strip()
                    try:
                        return json.loads(candidate)
                    except (json.JSONDecodeError, ValueError):
                        pass

        # Try finding first { ... last }
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace > first_brace:
            candidate = text[first_brace : last_brace + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

        return None
