from pathlib import Path

import pytest

from app.retriever import Retriever
from app.schemas import Chunk
from app.vectorstore import VectorStore


class MiniCorpusEmbeddings:
    _vectors = {
        "bees live in organized colonies inside hives": [1.0, 0.0, 0.0, 0.0, 0.0],
        "the earth orbits the sun once every year": [0.0, 1.0, 0.0, 0.0, 0.0],
        "water freezes at zero degrees celsius": [0.0, 0.0, 1.0, 0.0, 0.0],
        "chess is a strategy game played on a board": [0.0, 0.0, 0.0, 1.0, 0.0],
        "bread is baked from flour water and yeast": [0.0, 0.0, 0.0, 0.0, 1.0],
    }

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        normalized = text.casefold()
        if "bee" in normalized or "hive" in normalized:
            return self._vectors["bees live in organized colonies inside hives"]
        if "earth" in normalized or "sun" in normalized or "planet" in normalized:
            return self._vectors["the earth orbits the sun once every year"]
        if "water" in normalized or "freeze" in normalized or "ice" in normalized:
            return self._vectors["water freezes at zero degrees celsius"]
        if "chess" in normalized or "board" in normalized:
            return self._vectors["chess is a strategy game played on a board"]
        if "bread" in normalized or "flour" in normalized or "yeast" in normalized:
            return self._vectors["bread is baked from flour water and yeast"]
        return [0.0] * 5


@pytest.fixture
def mini_corpus_retriever(tmp_path: Path) -> Retriever:
    embeddings = MiniCorpusEmbeddings()
    vector_store = VectorStore(
        path=tmp_path / "chroma",
        collection_name="retriever_corpus",
        embedding_service=embeddings,
    )
    sentences = [
        "Bees live in organized colonies inside hives.",
        "The Earth orbits the Sun once every year.",
        "Water freezes at zero degrees Celsius.",
        "Chess is a strategy game played on a board.",
        "Bread is baked from flour, water, and yeast.",
    ]
    vector_store.add_chunks(
        [
            Chunk(
                id=f"sentence-{index}",
                text=sentence,
                page=index + 1,
                chunk_index=0,
                source="mini-corpus.pdf",
            )
            for index, sentence in enumerate(sentences)
        ]
    )
    return Retriever(
        embeddings,
        vector_store,
        top_k=5,
        min_score=0.25,
    )


def test_retrieve_returns_the_relevant_phrase_first(
    mini_corpus_retriever: Retriever,
) -> None:
    results = mini_corpus_retriever.retrieve("Where do bees live?")

    assert results
    assert results[0].text == "Bees live in organized colonies inside hives."
    assert results[0].page == 1
    assert results[0].source == "mini-corpus.pdf"
    assert results[0].score >= 0.25


def test_retrieve_filters_an_off_topic_question(
    mini_corpus_retriever: Retriever,
) -> None:
    assert mini_corpus_retriever.retrieve("How do volcanoes erupt?") == []


def test_retrieve_deduplicates_overlapping_chunks(
    tmp_path: Path,
) -> None:
    embeddings = MiniCorpusEmbeddings()
    vector_store = VectorStore(
        path=tmp_path / "duplicates",
        collection_name="duplicate_chunks",
        embedding_service=embeddings,
    )
    vector_store.add_chunks(
        [
            Chunk(
                id="duplicate-1",
                text="Bees live in organized colonies inside hives.",
                page=1,
                chunk_index=0,
                source="book.pdf",
            ),
            Chunk(
                id="duplicate-2",
                text="Organized colonies inside hives are where bees live.",
                page=1,
                chunk_index=1,
                source="book.pdf",
            ),
        ]
    )
    retriever = Retriever(embeddings, vector_store, top_k=2, min_score=-1.0)

    results = retriever.retrieve("Where do bees live?")

    assert len(results) == 1
