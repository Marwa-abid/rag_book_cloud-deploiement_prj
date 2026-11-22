from collections.abc import Iterator, Sequence
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from google.genai.errors import APIError

from app.config import Settings
from app.llm import (
    GeminiProvider,
    LLMConfigurationError,
    LLMQuotaError,
    LLMTimeoutError,
    Message,
    create_llm_provider,
)


class FakeModelsClient:
    def __init__(self) -> None:
        self.generate_arguments: dict[str, Any] | None = None
        self.stream_arguments: dict[str, Any] | None = None

    def generate_content(self, **kwargs: Any) -> SimpleNamespace:
        self.generate_arguments = kwargs
        return SimpleNamespace(text="Gemini fake answer")

    def generate_content_stream(self, **kwargs: Any) -> Iterator[SimpleNamespace]:
        self.stream_arguments = kwargs
        yield SimpleNamespace(text="Gemini ")
        yield SimpleNamespace(text="stream")


class FakeGeminiClient:
    def __init__(self) -> None:
        self.models = FakeModelsClient()


class ErrorModelsClient:
    def __init__(self, error: Exception) -> None:
        self._error = error

    def generate_content(self, **kwargs: Any) -> None:
        raise self._error


class ErrorGeminiClient:
    def __init__(self, error: Exception) -> None:
        self.models = ErrorModelsClient(error)


def test_gemini_provider_uses_fake_client_for_generate_and_stream() -> None:
    client = FakeGeminiClient()
    provider = GeminiProvider("gemini-test", "test-key", client=client)
    messages: Sequence[Message] = [
        {"role": "system", "content": "Use the supplied context only."},
        {"role": "user", "content": "What is in the book?"},
        {"role": "assistant", "content": "A software book."},
    ]

    assert provider.generate(messages) == "Gemini fake answer"
    assert list(provider.stream(messages)) == ["Gemini ", "stream"]

    assert client.models.generate_arguments is not None
    config = client.models.generate_arguments["config"]
    assert config.system_instruction == "Use the supplied context only."
    assert [content.role for content in client.models.generate_arguments["contents"]] == [
        "user",
        "model",
    ]
    assert client.models.stream_arguments is not None
    assert client.models.stream_arguments["model"] == "gemini-test"


@pytest.mark.parametrize("status_code", [401, 403])
def test_gemini_authentication_errors_are_clear(status_code: int) -> None:
    provider = GeminiProvider(
        "gemini-test",
        "test-key",
        client=ErrorGeminiClient(APIError(status_code, {"error": "unauthorized"})),
    )

    with pytest.raises(LLMConfigurationError, match=f"HTTP {status_code}"):
        provider.generate([{"role": "user", "content": "Question"}])


def test_gemini_quota_error_is_mapped() -> None:
    provider = GeminiProvider(
        "gemini-test",
        "test-key",
        client=ErrorGeminiClient(APIError(429, {"error": "quota"})),
    )

    with pytest.raises(LLMQuotaError, match="quota or rate limit"):
        provider.generate([{"role": "user", "content": "Question"}])


def test_gemini_timeout_is_mapped() -> None:
    provider = GeminiProvider(
        "gemini-test",
        "test-key",
        client=ErrorGeminiClient(httpx.ReadTimeout("timed out")),
    )

    with pytest.raises(LLMTimeoutError, match="60 seconds"):
        provider.generate([{"role": "user", "content": "Question"}])


def test_gemini_requires_an_api_key() -> None:
    with pytest.raises(LLMConfigurationError, match="LLM_API_KEY"):
        GeminiProvider("gemini-test", None)


def test_provider_factory_selects_gemini() -> None:
    settings = Settings(
        _env_file=None,
        llm_provider="gemini",
        llm_model="gemini-test",
        llm_api_key="test-key",
        llm_temperature=0.5,
    )

    provider = create_llm_provider(settings)

    assert isinstance(provider, GeminiProvider)
    assert provider._temperature == 0.5
