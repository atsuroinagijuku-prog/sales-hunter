import time
import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)


class BaseLLMClient(ABC):
    @abstractmethod
    def complete(self, prompt: str, system: str = "", **kwargs) -> str:
        ...


class GeminiClient(BaseLLMClient):
    def __init__(self, model: str = "gemini-2.5-flash", api_key: Optional[str] = None):
        from google import genai

        self.client = genai.Client(api_key=api_key)
        self.model = model

    def complete(self, prompt: str, system: str = "", **kwargs) -> str:
        full_prompt = f"{system}\n\n{prompt}" if system else prompt

        last_error = None
        for attempt in range(3):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=full_prompt,
                )
                return response.text or ""
            except Exception as e:
                last_error = e
                wait = 2 ** attempt
                logger.warning(
                    f"LLM request failed (attempt {attempt + 1}/3): {e}. "
                    f"Retrying in {wait}s..."
                )
                time.sleep(wait)

        logger.error(f"LLM request failed after 3 attempts: {last_error}")
        return ""


def get_llm_client(provider: str, model: str, api_key: Optional[str] = None) -> BaseLLMClient:
    if provider == "gemini":
        return GeminiClient(model=model, api_key=api_key)
    raise ValueError(f"Unknown provider: {provider}")
