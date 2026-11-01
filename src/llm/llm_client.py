"""
LLM Client for AI-Driven Compiler Optimization System

Two backends are provided:
  • OllamaLLMClient (default, class alias LLMClient)
      Connects to Qwen 2.5 Coder 7B via Ollama's HTTP API.
      Falls back to a stub response when Ollama is not running so the rest
      of the system can always be tested/used offline.
  • GeminiLLMClient
      Uses the Google Gemini API (requires `pip install google-generativeai` and
      GEMINI_API_KEY set in the environment).

Use make_llm_client(backend) to get the right instance.
"""

import json
import logging
import os
import time
from typing import Optional, Dict, Any, Tuple

# Load .env from project root (silently skipped if python-dotenv not installed)
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
except ImportError:
    pass

logger = logging.getLogger(__name__)

# ── Ollama configuration ────────────────────────────────────────────────────
OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL   = "qwen2.5-coder:7b"


def _try_import_requests():
    try:
        import requests  # type: ignore
        return requests
    except ImportError:
        return None


class LLMClient:
    """
    Client for Qwen 2.5 Coder 7B via Ollama.

    Usage
    -----
    client = LLMClient()
    response = client.generate("Explain this code: ...")
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        base_url: str = OLLAMA_BASE_URL,
        timeout: int = 360,
        max_retries: int = 2,
    ):
        self.model      = model
        self.base_url   = base_url.rstrip("/")
        self.timeout    = timeout
        self.max_retries = max_retries
        self._requests  = _try_import_requests()
        self._available = self._check_ollama()
        self.last_status: str = "init"
        self.last_error: Optional[str] = None

    # ── Public API ────────────────────────────────────────────────────────────

    @staticmethod
    def is_stub(text: str) -> bool:
        """Check whether a response string originates from a synthetic offline stub."""
        if not text:
            return False
        return "(LLM offline stub)" in text or "offline stub" in text

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 2048,
        temperature: float = 0.1,
    ) -> str:
        """
        Generate a completion.

        Returns the raw text response. On any failure the stub is returned so
        callers always receive a parseable string, while updating last_status.
        """
        text, _ = self.generate_with_meta(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return text

    def generate_with_meta(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 2048,
        temperature: float = 0.1,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Generate completion and return both text and truthful execution metadata.
        Distinguishes genuine responses, unavailable services, timeouts, and stubs.
        """
        if not self._available:
            self.last_status = "unavailable"
            self.last_error = "Ollama service unavailable"
            logger.warning("Ollama not available – returning stub response")
            stub = self._stub_response(prompt)
            return stub, {"status": "unavailable", "is_genuine": False, "error": self.last_error}

        payload: Dict[str, Any] = {
            "model":  self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system_prompt:
            payload["system"] = system_prompt

        last_err = None
        for attempt in range(1, self.max_retries + 2):
            try:
                resp = self._requests.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                self.last_status = "genuine"
                self.last_error = None
                return data.get("response", ""), {"status": "genuine", "is_genuine": True, "error": None}
            except Exception as exc:
                last_err = exc
                logger.warning(f"LLM attempt {attempt} failed: {exc}")
                if attempt <= self.max_retries:
                    time.sleep(1)

        err_str = str(last_err)
        if "timed out" in err_str.lower() or "timeout" in err_str.lower():
            self.last_status = "timeout"
        else:
            self.last_status = "error"
        self.last_error = err_str

        logger.error(f"All LLM attempts failed ({self.last_status}) – returning stub response")
        stub = self._stub_response(prompt)
        return stub, {"status": self.last_status, "is_genuine": False, "error": err_str}

    def is_available(self) -> bool:
        """Return True if Ollama is reachable."""
        return self._available

    def health_check(self) -> Dict[str, Any]:
        """Return a dict describing connectivity status."""
        available = self._check_ollama()
        self._available = available
        return {
            "available":  available,
            "model":      self.model,
            "base_url":   self.base_url,
        }

    # ── Internals ─────────────────────────────────────────────────────────────

    def _check_ollama(self) -> bool:
        if self._requests is None:
            logger.warning("'requests' not installed – Ollama unavailable")
            return False
        try:
            resp = self._requests.get(f"{self.base_url}/api/tags", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False

    # ── Stub (offline / fallback) ─────────────────────────────────────────────
    # (shared by both OllamaLLMClient and ClaudeLLMClient via inheritance)

    def _stub_response(self, prompt: str) -> str:
        """
        Return a minimal well-formed CoT JSON string so that upstream parsers
        always receive valid input even when the LLM is offline.
        """
        hint = ""
        p = prompt.lower()
        if "analyz" in p or "detect" in p:
            hint = "Rule-based analysis completed (LLM offline stub)."
        elif "optim" in p or "fix" in p or "transform" in p:
            hint = "Optimization suggestions generated (LLM offline stub)."
        elif "verif" in p:
            hint = "Verification reasoning completed (LLM offline stub)."
        else:
            hint = "Task processed (LLM offline stub)."

        stub = {
            "reasoning_steps": [
                "Step 1: Parsed the input code.",
                "Step 2: Applied rule-based heuristics.",
                "Step 3: " + hint,
            ],
            "findings": [],
            "conclusion": hint,
            "confidence": 0.5,
        }
        return "```json\n" + json.dumps(stub, indent=2) + "\n```"


# ── Gemini API backend ────────────────────────────────────────────────────────

class GeminiLLMClient(LLMClient):
    """
    LLM backend that uses the Google Gemini API.

    Requirements
    ------------
    • pip install google-generativeai
    • GEMINI_API_KEY environment variable set

    Falls back to the same stub response as LLMClient when the SDK is
    unavailable or the API key is missing.
    """

    DEFAULT_MODEL = "gemini-1.5-flash"

    def __init__(self, model: str = DEFAULT_MODEL):
        # Do NOT call super().__init__() — we don't need Ollama at all.
        self.model      = model
        self._requests  = None   # unused; kept for _stub_response compat
        self._genai     = None   # google.generativeai module reference
        self._available = self._check_gemini()

    # ── Public API ────────────────────────────────────────────────────────────

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 2048,
        temperature: float = 0.1,
    ) -> str:
        if not self._available:
            logger.warning("Gemini API not available – returning stub response")
            return self._stub_response(prompt)
        try:
            sys_inst = system_prompt or (
                "You are an expert C/C++ compiler optimisation agent. "
                "Respond only with structured JSON as instructed."
            )
            gemini_model = self._genai.GenerativeModel(
                model_name=self.model,
                system_instruction=sys_inst,
            )
            gen_cfg = self._genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
            response = gemini_model.generate_content(prompt, generation_config=gen_cfg)
            return response.text
        except Exception as exc:
            logger.warning(f"Gemini API call failed: {exc}")
            return self._stub_response(prompt)

    def is_available(self) -> bool:
        return self._available

    def health_check(self) -> Dict[str, Any]:
        available = self._check_gemini()
        self._available = available
        return {
            "available": available,
            "model":     self.model,
            "backend":   "gemini",
        }

    # ── Internals ─────────────────────────────────────────────────────────────

    def _check_gemini(self) -> bool:
        try:
            import google.generativeai as genai  # type: ignore
            api_key = os.environ.get("GEMINI_API_KEY", "")
            if not api_key:
                logger.warning(
                    "GEMINI_API_KEY not set — Gemini backend unavailable."
                )
                return False
            genai.configure(api_key=api_key)
            self._genai = genai
            return True
        except ImportError:
            logger.warning(
                "'google-generativeai' package not installed — Gemini backend unavailable. "
                "Run: pip install google-generativeai"
            )
            return False
        except Exception as exc:
            logger.warning(f"Gemini API init failed: {exc}")
            return False


# ── Backend factory ───────────────────────────────────────────────────────────

def make_llm_client(backend: str = "ollama") -> LLMClient:
    """
    Return the appropriate LLM client for the requested backend.

    Parameters
    ----------
    backend : str
        "ollama"  — Qwen 2.5 Coder 7B via Ollama (default, offline-capable)
        "gemini"  — Google Gemini API (requires GEMINI_API_KEY)

    Returns
    -------
    LLMClient or GeminiLLMClient instance
    """
    if backend == "gemini":
        logger.info("LLM backend: Google Gemini API (%s)", GeminiLLMClient.DEFAULT_MODEL)
        return GeminiLLMClient()
    logger.info("LLM backend: Ollama / Qwen 2.5 Coder (%s)", DEFAULT_MODEL)
    return LLMClient()
