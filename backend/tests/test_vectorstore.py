from pathlib import Path

import pytest

from app.schemas import Chunk
from app.vectorstore import VectorStore


class FakeEmbeddingService:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = {
            "software development": [1.0, 0.0, 0.0],
            "healthy habits": [0.0, 1.0, 0.0],
        }
        return [vectors[text] for text in texts]


@pytest.fixture
def vector_store(tmp_path: Path) -> VectorStore:
    return VectorStore(
        path=tmp_path / "chroma",
        collection_name="test_chunks",
        embedding_service=FakeEmbeddingService(),
    )


def make_chunks() -> list[Chunk]:
    return [
        Chunk(
            id="stable-id-1",
            text="software development",
            page=3,
            chunk_index=0,
            source="book.pdf",
        ),
        Chunk(
            id="stable-id-2",
            text="healthy habits",
            page=8,
            chunk_index=1,
            source="book.pdf",
        ),
    ]


def test_add_chunks_and_count(vector_store: VectorStore) -> None:
    assert vector_store.add_chunks(make_chunks()) == 2
    assert vector_store.count() == 2


def test_query_returns_text_metadata_and_similarity(vector_store: VectorStore) -> None:
    vector_store.add_chunks(make_chunks())

    results = vector_store.query([1.0, 0.0, 0.0], top_k=1)

    assert len(results) == 1
    assert results[0]["text"] == "software development"
    assert results[0]["metadata"] == {"page": 3, "source": "book.pdf"}
    assert results[0]["score"] == pytest.approx(1.0)


def test_add_chunks_is_idempotent_for_stable_ids(vector_store: VectorStore) -> None:
    chunks = make_chunks()
    vector_store.add_chunks(chunks)
    vector_store.add_chunks(chunks)

    assert vector_store.count() == len(chunks)


def test_reset_empties_the_collection(vector_store: VectorStore) -> None:
    vector_store.add_chunks(make_chunks())
    vector_store.reset()

    assert vector_store.count() == 0
