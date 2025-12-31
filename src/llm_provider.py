"""
LLM Provider Abstraction.

Provides a unified interface for LLM calls that can be swapped between:
- AnthropicProvider: Real Claude API calls
- NullLLMProvider: Test stub for CI/CD without API keys
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Any, Dict
import os
import logging

logger = logging.getLogger(__name__)


@dataclass
class MockTextBlock:
    """Minimal text block for NullLLM responses."""
    text: str
    type: str = "text"


@dataclass
class MockToolUseBlock:
    """Minimal tool use block for NullLLM responses."""
    id: str
    name: str
    input: Dict[str, Any]
    type: str = "tool_use"


@dataclass
class MockResponse:
    """Minimal response structure matching Anthropic API."""
    content: List[Any]
    stop_reason: str = "end_turn"
    model: str = "null-llm"

    @property
    def text(self) -> str:
        """Return text content from first text block."""
        for block in self.content:
            if hasattr(block, 'text'):
                return block.text
        return ""


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def create_message(
        self,
        model: str,
        max_tokens: int,
        messages: List[Dict[str, Any]],
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Any:
        """Create a message/completion request."""
        pass

    @property
    @abstractmethod
    def is_null(self) -> bool:
        """Return True if this is a null/mock provider."""
        pass


class AnthropicProvider(LLMProvider):
    """Real Anthropic Claude API provider."""

    def __init__(self, api_key: Optional[str] = None):
        from anthropic import Anthropic
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY required for AnthropicProvider")
        self.client = Anthropic(api_key=self.api_key)

    def create_message(
        self,
        model: str,
        max_tokens: int,
        messages: List[Dict[str, Any]],
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Any:
        params = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            params["system"] = system
        if tools:
            params["tools"] = tools
        params.update(kwargs)
        return self.client.messages.create(**params)

    @property
    def is_null(self) -> bool:
        return False


class NullLLMProvider(LLMProvider):
    """
    NullLLMProvider is NOT a mock of Anthropic behavior.
    It exists to:
    - unblock test collection
    - verify control flow
    - assert call boundaries

    Do NOT make this "smart" or try to simulate real responses.
    """

    def __init__(self):
        self.call_count = 0
        self.last_messages = None
        self.last_model = None
        self.last_tools = None
        logger.info("NullLLMProvider initialized - LLM calls will return canned responses")

    def create_message(
        self,
        model: str,
        max_tokens: int,
        messages: List[Dict[str, Any]],
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> MockResponse:
        self.call_count += 1
        self.last_messages = messages
        self.last_model = model
        self.last_tools = tools

        logger.debug(f"NullLLM call #{self.call_count}: model={model}, messages={len(messages)}")

        # Return minimal valid response
        return MockResponse(
            content=[MockTextBlock(text="[NullLLM: No real LLM call made]")],
            stop_reason="end_turn",
            model="null-llm"
        )

    @property
    def is_null(self) -> bool:
        return True


def get_llm_provider(
    api_key: Optional[str] = None,
    use_null: bool = False
) -> LLMProvider:
    """
    Get an LLM provider instance.

    Args:
        api_key: Optional API key (uses env var if not provided)
        use_null: Force use of NullLLMProvider (for testing)

    Returns:
        LLMProvider instance

    Environment Variables:
        USE_NULL_LLM: Set to "true" to use NullLLMProvider
        ANTHROPIC_API_KEY: API key for AnthropicProvider
    """
    if use_null or os.environ.get("USE_NULL_LLM", "").lower() == "true":
        return NullLLMProvider()

    # Try to create real provider, fall back to null if no API key
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("No ANTHROPIC_API_KEY found, using NullLLMProvider")
        return NullLLMProvider()

    return AnthropicProvider(api_key=api_key)


def require_llm_provider(api_key: Optional[str] = None) -> LLMProvider:
    """
    Get an LLM provider, raising if no API key is available.

    Use this when LLM calls are required (not optional).
    """
    if os.environ.get("USE_NULL_LLM", "").lower() == "true":
        return NullLLMProvider()

    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY required. "
            "Set environment variable or use USE_NULL_LLM=true for testing."
        )

    return AnthropicProvider(api_key=api_key)
