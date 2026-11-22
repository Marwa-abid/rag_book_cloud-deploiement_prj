import json
from abc import ABC, abstractmethod
from collections.abc import Iterator, Sequence
from typing import Any, Literal, TypedDict

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)

from app.config import Settings, get_settings


class Message(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


_REQUEST_TIMEOUT = 60.0
_GEMINI_TIMEOUT_MILLISECONDS = 60_000


class LLMError(RuntimeError):
    """Base error for language-model providers."""


class LLMConfigurationError(LLMError):
    """Raised when a provider is configured incorrectly."""


class LLMQuotaError(LLMError):
    """Raised when a provider rejects a request due to quota or rate limits."""


class LLMOverloadedError(LLMError):
    """Raised when a provider is temporarily overloaded."""


class LLMTimeoutError(LLMError):
    """Raised when a provider request exceeds its timeout."""


class LLMRequestError(LLMError):
    """Raised when a provider cannot complete a request."""


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, messages: Sequence[Message]) -> str:
        raise NotImplementedError

    @abstractmethod
    def stream(self, messages: Sequence[Message]) -> Iterator[str]:
        raise NotImplementedError


class OpenAIProvider(LLMProvider):
    def __init__(
        self,
        model: str,
        api_key: str | None,
        temperature: float = 0.2,
    ) -> None:
        if not api_key:
            raise LLMConfigurationError(
                "LLM_API_KEY is required when LLM_PROVIDER is 'openai'."
            )
        self._client = OpenAI(api_key=api_key, timeout=_REQUEST_TIMEOUT)
        self._model = model
        self._temperature = temperature

    def generate(self, messages: Sequence[Message]) -> str:
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=list(messages),
                temperature=self._temperature,
            )
        except RateLimitError as error:
            raise LLMQuotaError("OpenAI quota or rate limit was exceeded.") from error
        except APITimeoutError as error:
            raise LLMTimeoutError("OpenAI request timed out after 60 seconds.") from error
        except AuthenticationError as error:
            raise LLMConfigurationError("OpenAI rejected the configured API key.") from error
        except APIStatusError as error:
            if error.status_code == 503:
                raise LLMOverloadedError("OpenAI is temporarily overloaded.") from error
            raise LLMRequestError(f"OpenAI request failed: {error}") from error
        except APIConnectionError as error:
            raise LLMRequestError(f"OpenAI request failed: {error}") from error
        content = response.choices[0].message.content
        if not content:
            raise LLMRequestError("OpenAI returned an empty response.")
        return content

    def stream(self, messages: Sequence[Message]) -> Iterator[str]:
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=list(messages),
                temperature=self._temperature,
                stream=True,
            )
            for event in response:
                content = event.choices[0].delta.content
                if content:
                    yield content
        except RateLimitError as error:
            raise LLMQuotaError("OpenAI quota or rate limit was exceeded.") from error
        except APITimeoutError as error:
            raise LLMTimeoutError("OpenAI request timed out after 60 seconds.") from error
        except AuthenticationError as error:
            raise LLMConfigurationError("OpenAI rejected the configured API key.") from error
        except APIStatusError as error:
            if error.status_code == 503:
                raise LLMOverloadedError("OpenAI is temporarily overloaded.") from error
            raise LLMRequestError(f"OpenAI request failed: {error}") from error
        except APIConnectionError as error:
            raise LLMRequestError(f"OpenAI request failed: {error}") from error


class OllamaProvider(LLMProvider):
    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434",
        temperature: float = 0.2,
    ) -> None:
        self._model = model
        self._url = f"{base_url.rstrip('/')}/api/chat"
        self._temperature = temperature

    def generate(self, messages: Sequence[Message]) -> str:
        try:
            response = httpx.post(
                self._url,
                json={
                    "model": self._model,
                    "messages": list(messages),
                    "options": {"temperature": self._temperature},
                    "stream": False,
                },
                timeout=_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException as error:
            raise LLMTimeoutError("Ollama request timed out after 60 seconds.") from error
        except httpx.HTTPStatusError as error:
            raise self._http_error(error) from error
        except httpx.RequestError as error:
            raise LLMRequestError(f"Could not connect to Ollama: {error}") from error
        except json.JSONDecodeError as error:
            raise LLMRequestError("Ollama returned invalid JSON.") from error
        return self._response_content(payload)

    def stream(self, messages: Sequence[Message]) -> Iterator[str]:
        try:
            with httpx.stream(
                "POST",
                self._url,
                json={
                    "model": self._model,
                    "messages": list(messages),
                    "options": {"temperature": self._temperature},
                    "stream": True,
                },
                timeout=_REQUEST_TIMEOUT,
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    payload = json.loads(line)
                    if "error" in payload:
                        raise LLMRequestError(f"Ollama error: {payload['error']}")
                    content = payload.get("message", {}).get("content", "")
                    if content:
                        yield str(content)
        except httpx.TimeoutException as error:
            raise LLMTimeoutError("Ollama request timed out after 60 seconds.") from error
        except httpx.HTTPStatusError as error:
            raise self._http_error(error) from error
        except httpx.RequestError as error:
            raise LLMRequestError(f"Could not connect to Ollama: {error}") from error
        except json.JSONDecodeError as error:
            raise LLMRequestError("Ollama returned invalid streaming JSON.") from error

    @staticmethod
    def _response_content(payload: dict[str, Any]) -> str:
        if "error" in payload:
            raise LLMRequestError(f"Ollama error: {payload['error']}")
        content = payload.get("message", {}).get("content")
        if not isinstance(content, str) or not content:
            raise LLMRequestError("Ollama returned an empty response.")
        return content

    @staticmethod
    def _http_error(error: httpx.HTTPStatusError) -> LLMError:
        status_code = error.response.status_code
        if status_code in (401, 403):
            return LLMConfigurationError(
                f"Ollama rejected the request with HTTP {status_code}."
            )
        if status_code == 429:
            return LLMQuotaError("Ollama quota or rate limit was exceeded.")
        if status_code == 503:
            return LLMOverloadedError("Ollama is temporarily overloaded.")
        return LLMRequestError(f"Ollama request failed with HTTP {status_code}.")


class GeminiProvider(LLMProvider):
    def __init__(
        self,
        model: str,
        api_key: str | None,
        temperature: float = 0.2,
        client: Any | None = None,
    ) -> None:
        if not api_key:
            raise LLMConfigurationError(
                "LLM_API_KEY is required when LLM_PROVIDER is 'gemini'."
            )
        self._model = model
        self._temperature = temperature
        self._client = client or genai.Client(
            api_key=api_key,
            http_options=genai_types.HttpOptions(
                timeout=_GEMINI_TIMEOUT_MILLISECONDS
            ),
        )

    def generate(self, messages: Sequence[Message]) -> str:
        system_instruction, contents = self._convert_messages(messages)
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=contents,
                config=genai_types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=self._temperature,
                ),
            )
        except (genai_errors.APIError, httpx.TimeoutException, TimeoutError) as error:
            raise self._map_error(error) from error
        return self._response_text(response)

    def stream(self, messages: Sequence[Message]) -> Iterator[str]:
        system_instruction, contents = self._convert_messages(messages)
        try:
            responses = self._client.models.generate_content_stream(
                model=self._model,
                contents=contents,
                config=genai_types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=self._temperature,
                ),
            )
            for response in responses:
                text = getattr(response, "text", None)
                if text:
                    yield str(text)
        except (genai_errors.APIError, httpx.TimeoutException, TimeoutError) as error:
            raise self._map_error(error) from error

    @staticmethod
    def _convert_messages(
        messages: Sequence[Message],
    ) -> tuple[str | None, list[genai_types.Content]]:
        system_messages = [
            message["content"]
            for message in messages
            if message["role"] == "system"
        ]
        contents = [
            genai_types.Content(
                role="model" if message["role"] == "assistant" else "user",
                parts=[genai_types.Part(text=message["content"])],
            )
            for message in messages
            if message["role"] != "system"
        ]
        system_instruction = "\n\n".join(system_messages) or None
        return system_instruction, contents

    @staticmethod
    def _response_text(response: Any) -> str:
        text = getattr(response, "text", None)
        if not text:
            raise LLMRequestError("Gemini returned an empty response.")
        return str(text)

    @staticmethod
    def _map_error(error: Exception) -> LLMError:
        if isinstance(error, (httpx.TimeoutException, TimeoutError)):
            return LLMTimeoutError("Gemini request timed out after 60 seconds.")
        if isinstance(error, genai_errors.APIError):
            status_code = error.code
            if status_code in (401, 403):
                return LLMConfigurationError(
                    f"Gemini rejected the configured API key (HTTP {status_code})."
                )
            if status_code == 429:
                return LLMQuotaError("Gemini quota or rate limit was exceeded.")
            if status_code == 503:
                return LLMOverloadedError("Gemini is temporarily overloaded.")
            return LLMRequestError(f"Gemini request failed: {error}")
        return LLMRequestError(f"Gemini request failed: {error}")


class FakeProvider(LLMProvider):
    def __init__(
        self,
        response: str = "Test response",
        responses: Sequence[str] | None = None,
    ) -> None:
        self.response = response
        self._responses = list(responses or [])
        self.calls: list[list[Message]] = []

    def generate(self, messages: Sequence[Message]) -> str:
        self.calls.append(list(messages))
        if self._responses:
            return self._responses.pop(0)
        return self.response

    def stream(self, messages: Sequence[Message]) -> Iterator[str]:
        self.calls.append(list(messages))
        yield self.response


def create_llm_provider(settings: Settings | None = None) -> LLMProvider:
    active_settings = settings or get_settings()
    provider = active_settings.llm_provider.casefold()
    if provider == "openai":
        return OpenAIProvider(
            active_settings.llm_model,
            active_settings.llm_api_key,
            active_settings.llm_temperature,
        )
    if provider == "ollama":
        return OllamaProvider(
            active_settings.llm_model,
            temperature=active_settings.llm_temperature,
        )
    if provider == "gemini":
        return GeminiProvider(
            active_settings.llm_model,
            active_settings.llm_api_key,
            active_settings.llm_temperature,
        )
    raise LLMConfigurationError(
        f"Unsupported LLM_PROVIDER '{active_settings.llm_provider}'. "
        "Supported providers: openai, ollama, gemini."
    )
