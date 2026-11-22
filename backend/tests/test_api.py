import json
from pathlib import Path
from collections.abc import Iterator, Sequence
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from app.config import Settings
from app.llm import FakeProvider, LLMQuotaError, Message
from app.main import create_app, get_pipeline
from app.rag import RAGPipeline
from app.retriever import Retriever
from app.schemas import Chunk
from app.vectorstore import VectorStore


class MiniCorpusEmbeddings:
    _sentences = (
        "bees live together in colonies",
        "the earth orbits the sun",
        "water freezes at zero degrees celsius",
        "chess is played on a board",
        "bread is made with flour and yeast",
    )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        if any(term in text.casefold() for term in ("bee", "bees", "abeille")):
            return self._vector(self._sentences[0])
        return [0.0] * len(self._sentences)

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * len(self._sentences)
        vector[self._sentences.index(text)] = 1.0
        return vector


class QuotaFakeProvider(FakeProvider):
    def generate(self, messages: Sequence[Message]) -> str:
        raise LLMQuotaError("private details must not be returned")

    def stream(self, messages: Sequence[Message]) -> Iterator[str]:
        raise LLMQuotaError("private details must not be returned")


def build_test_pipeline(tmp_path: Path, provider: FakeProvider) -> RAGPipeline:
    embeddings = MiniCorpusEmbeddings()
    store = VectorStore(
        path=tmp_path / "chroma",
        collection_name="api_test",
        embedding_service=embeddings,
    )
    store.add_chunks(
        [
            Chunk(
                id=f"test-{index}",
                text=text,
                page=index + 1,
                chunk_index=0,
                source="mini.pdf",
            )
            for index, text in enumerate(embeddings._sentences)
        ]
    )
    retriever = Retriever(embeddings, store, top_k=5, min_score=0.25)
    settings = Settings(
        _env_file=None,
        chroma_path=tmp_path / "chroma",
        collection_name="api_test",
        llm_provider="fake",
        llm_model="test-model",
        top_k=5,
    )
    return RAGPipeline(retriever=retriever, provider=provider, settings=settings)


@pytest.fixture
def api_client(tmp_path: Path) -> TestClient:
    pipeline = build_test_pipeline(tmp_path, FakeProvider("Bees live in colonies [p. 1]."))
    application = create_app(pipeline_factory=lambda: pipeline)
    application.dependency_overrides[get_pipeline] = lambda: pipeline
    with TestClient(application) as client:
        yield client
    application.dependency_overrides.clear()


def test_health_returns_index_and_safe_provider_details(api_client: TestClient) -> None:
    response = api_client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["chunks"] == 5
    assert "provider" in payload
    assert "model" in payload
    assert "key" not in json.dumps(payload).casefold()


def test_chat_returns_answer_and_sources(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/chat",
        json={"question": "Where do bees live?", "history": []},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "Bees live in colonies [p. 1]."
    assert payload["sources"][0]["page"] == 1
    assert payload["sources"][0]["score"] >= 0.25


def test_chat_without_results_does_not_call_llm(tmp_path: Path) -> None:
    provider = FakeProvider()
    pipeline = build_test_pipeline(tmp_path, provider)
    application = create_app(pipeline_factory=lambda: pipeline)
    with TestClient(application) as client:
        response = client.post(
            "/api/chat",
            json={"question": "How do volcanoes erupt?", "history": []},
        )

    assert response.status_code == 200
    assert response.json()["sources"] == []
    assert response.json()["answer"] == "I couldn't find this information in the book."
    assert provider.calls == []


def test_empty_question_is_rejected(api_client: TestClient) -> None:
    response = api_client.post("/api/chat", json={"question": " ", "history": []})

    assert response.status_code == 422


def test_chat_stream_emits_tokens_sources_and_done(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/chat/stream",
        json={"question": "Where do bees live?", "history": []},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.text
    assert 'event: token\ndata: {"token": "Bees live in colonies [p. 1]."}' in body
    assert "event: sources" in body
    assert "event: done" in body
    assert body.index("event: token") < body.index("event: sources") < body.index("event: done")


def test_llm_quota_error_returns_sanitized_429(tmp_path: Path) -> None:
    pipeline = build_test_pipeline(tmp_path, QuotaFakeProvider())
    application = create_app(pipeline_factory=lambda: pipeline)
    with TestClient(application) as client:
        response = client.post(
            "/api/chat",
            json={"question": "Where do bees live?", "history": []},
        )

    assert response.status_code == 429
    assert "quota" in response.json()["detail"].casefold()
    assert "private details" not in response.text


def create_test_pdf(path: Path) -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_metadata({"/Title": "Miniature de test"})
    with path.open("wb") as pdf_file:
        writer.write(pdf_file)
    return path.read_bytes()


def test_book_info_and_inline_pdf_support_range(tmp_path: Path) -> None:
    pdf_path = tmp_path / "mini-book.pdf"
    pdf_bytes = create_test_pdf(pdf_path)
    settings = Settings(_env_file=None, book_path=pdf_path)
    application = create_app(
        pipeline_factory=lambda: build_test_pipeline(tmp_path, FakeProvider()),
        settings_override=settings,
    )
    with TestClient(application) as client:
        info_response = client.get("/api/book/info")
        pdf_response = client.get(
            "/api/book",
            headers={"Range": "bytes=0-15"},
        )

    assert info_response.status_code == 200
    assert info_response.json() == {
        "title": "Miniature de test",
        "pages": 1,
        "available": True,
    }
    assert pdf_response.status_code == 206
    assert pdf_response.headers["content-type"] == "application/pdf"
    assert pdf_response.headers["content-disposition"].startswith("inline")
    assert pdf_response.headers["content-range"].startswith("bytes 0-15/")
    assert pdf_response.content == pdf_bytes[:16]


def test_book_endpoints_report_missing_pdf_in_french(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, book_path=tmp_path / "missing.pdf")
    application = create_app(
        pipeline_factory=lambda: build_test_pipeline(tmp_path, FakeProvider()),
        settings_override=settings,
    )
    with TestClient(application) as client:
        info_response = client.get("/api/book/info")
        pdf_response = client.get("/api/book")

    assert info_response.status_code == 200
    assert info_response.json()["available"] is False
    assert pdf_response.status_code == 404
    assert "introuvable" in pdf_response.json()["detail"]
