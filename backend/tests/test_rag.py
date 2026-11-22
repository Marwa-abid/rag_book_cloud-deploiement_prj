from pathlib import Path

import pytest

from app.llm import FakeProvider, Message
from app.rag import RAGPipeline
from app.retriever import Retriever
from app.schemas import Chunk
from app.vectorstore import VectorStore


class MiniCorpusEmbeddings:
    _vectors = {
        "honey bees live in colonies and communicate through dances": [
            1.0,
            0.0,
            0.0,
            0.0,
            0.0,
        ],
        "the earth travels around the sun once each year": [
            0.0,
            1.0,
            0.0,
            0.0,
            0.0,
        ],
        "water boils at one hundred degrees celsius at sea level": [
            0.0,
            0.0,
            1.0,
            0.0,
            0.0,
        ],
        "chess players plan moves to control the board": [
            0.0,
            0.0,
            0.0,
            1.0,
            0.0,
        ],
        "bread dough rises when yeast ferments sugar": [
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
        ],
    }

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vectors[text.casefold()] for text in texts]

    def embed_query(self, text: str) -> list[float]:
        normalized = text.casefold()
        if any(term in normalized for term in ("bee", "bees", "honey", "abeille")):
            return self._vectors[
                "honey bees live in colonies and communicate through dances"
            ]
        if any(term in normalized for term in ("earth", "sun", "terre", "soleil")):
            return self._vectors["the earth travels around the sun once each year"]
        if any(term in normalized for term in ("water", "boil", "eau", "bouillir")):
            return self._vectors[
                "water boils at one hundred degrees celsius at sea level"
            ]
        if any(term in normalized for term in ("chess", "échecs")):
            return self._vectors["chess players plan moves to control the board"]
        if any(term in normalized for term in ("bread", "yeast", "pain", "levure")):
            return self._vectors["bread dough rises when yeast ferments sugar"]
        return [0.0] * 5


@pytest.fixture
def mini_corpus_retriever(tmp_path: Path) -> Retriever:
    embeddings = MiniCorpusEmbeddings()
    vector_store = VectorStore(
        path=tmp_path / "chroma",
        collection_name="rag_test",
        embedding_service=embeddings,
    )
    sentences = list(embeddings._vectors)
    vector_store.add_chunks(
        [
            Chunk(
                id=f"test-chunk-{index}",
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


def test_prompt_contains_context_page_citation_and_language_instruction(
    mini_corpus_retriever: Retriever,
) -> None:
    provider = FakeProvider("Les abeilles vivent en colonies [p. 1].")
    pipeline = RAGPipeline(mini_corpus_retriever, provider)

    answer, sources = pipeline.answer("Où vivent les abeilles ?")

    assert answer.endswith("[p. 1].")
    assert len(sources) == 1
    answer_prompt = provider.calls[0]
    assert "[p. 1]" in answer_prompt[1]["content"]
    assert "honey bees live in colonies" in answer_prompt[1]["content"]
    assert "same language" in answer_prompt[0]["content"]
    assert "cite" in answer_prompt[0]["content"].casefold()


def test_prompt_explains_partial_relevant_and_irrelevant_context_handling(
    mini_corpus_retriever: Retriever,
) -> None:
    provider = FakeProvider("Les abeilles vivent en colonies [p. 1].")
    pipeline = RAGPipeline(mini_corpus_retriever, provider)

    pipeline.answer("Où vivent les abeilles ?")

    prompt = provider.calls[0][0]["content"].casefold()
    assert "only when none of the context passages discusses the subject" in prompt
    assert "answers only partially" in prompt
    assert "durations, steps, and numbers" in prompt
    assert "briefly say what the book does not specify" in prompt
    assert "ignore context passages that are unrelated" in prompt


def test_no_results_returns_fallback_without_calling_llm(
    mini_corpus_retriever: Retriever,
) -> None:
    provider = FakeProvider()
    pipeline = RAGPipeline(mini_corpus_retriever, provider)

    answer, sources = pipeline.answer("How do volcanoes erupt?")

    assert answer == "I couldn't find this information in the book."
    assert sources == []
    assert provider.calls == []


def test_llm_rejection_returns_no_sources_when_chunks_were_retrieved(
    mini_corpus_retriever: Retriever,
) -> None:
    rejection = "I couldn't find this information in the book."
    provider = FakeProvider(rejection)
    pipeline = RAGPipeline(mini_corpus_retriever, provider)

    answer, sources = pipeline.answer("Where do bees live?")

    assert answer == rejection
    assert sources == []


def test_answer_stream_returns_tokens_and_sources(
    mini_corpus_retriever: Retriever,
) -> None:
    provider = FakeProvider("Bees live in colonies [p. 1].")
    pipeline = RAGPipeline(mini_corpus_retriever, provider)

    stream, sources = pipeline.answer_stream("Where do bees live?")

    assert "".join(stream) == "Bees live in colonies [p. 1]."
    assert sources[0].page == 1
    assert len(provider.calls) == 1


def test_streamed_rejection_clears_sources_after_stream_consumption(
    mini_corpus_retriever: Retriever,
) -> None:
    rejection = "I couldn't find this information in the book."
    provider = FakeProvider(rejection)
    pipeline = RAGPipeline(mini_corpus_retriever, provider)

    stream, sources = pipeline.answer_stream("Where do bees live?")
    assert sources
    assert "".join(stream) == rejection
    assert sources == []


def test_follow_up_is_rewritten_with_recent_history(
    mini_corpus_retriever: Retriever,
) -> None:
    provider = FakeProvider(
        responses=[
            "Where do honey bees live?",
            "Honey bees live in colonies [p. 1].",
        ]
    )
    pipeline = RAGPipeline(mini_corpus_retriever, provider)
    history: list[Message] = [
        {"role": "user", "content": "Tell me about bees."},
        {"role": "assistant", "content": "They live in colonies."},
    ]

    answer, sources = pipeline.answer("Where exactly?", history)

    assert answer.startswith("Honey bees")
    assert sources[0].page == 1
    assert len(provider.calls) == 2
    rewrite_prompt = provider.calls[0]
    assert rewrite_prompt[1]["content"] == "Tell me about bees."
    assert rewrite_prompt[-1]["content"] == "Where exactly?"
    assert provider.calls[1][-1]["content"].startswith(
        "Original question: Where exactly?"
    )


@pytest.mark.parametrize(
    "rejection",
    [
        "Je n'ai pas trouvé cette information dans le livre.",
        "I couldn't find this information in the book.",
    ],
)
def test_rejection_history_does_not_influence_rewrite_or_answer(
    mini_corpus_retriever: Retriever,
    rejection: str,
) -> None:
    provider = FakeProvider(
        responses=[
            "Where do honey bees live?",
            "Honey bees live in colonies [p. 1].",
        ]
    )
    pipeline = RAGPipeline(mini_corpus_retriever, provider)
    history: list[Message] = [
        {"role": "user", "content": "Tell me about honey bees."},
        {"role": "assistant", "content": "Honey bees live in colonies [p. 1]."},
        {"role": "user", "content": "What about volcanoes?"},
        {"role": "assistant", "content": rejection},
    ]

    answer, sources = pipeline.answer("Where do they live?", history)

    assert answer.startswith("Honey bees")
    assert sources[0].page == 1
    rewrite_content = "\n".join(message["content"] for message in provider.calls[0])
    generation_history = "\n".join(
        message["content"] for message in provider.calls[1][1:-1]
    )
    assert rejection not in rewrite_content
    assert "What about volcanoes?" not in rewrite_content
    assert "[p. 1]" not in rewrite_content
    assert rejection not in generation_history
    assert "What about volcanoes?" not in generation_history
    assert "Honey bees live in colonies" in generation_history
    assert "Un refus précédent dans la conversation" in provider.calls[1][0]["content"]


@pytest.mark.parametrize(
    "rewrite",
    ["", "x" * 301, "Honey bees live in colonies."],
)
def test_empty_or_overlong_rewrite_falls_back_to_original_question(
    mini_corpus_retriever: Retriever,
    monkeypatch: pytest.MonkeyPatch,
    rewrite: str,
) -> None:
    queries: list[str] = []
    monkeypatch.setattr(
        mini_corpus_retriever,
        "retrieve",
        lambda query: queries.append(query) or [],
    )
    provider = FakeProvider(responses=[rewrite])
    pipeline = RAGPipeline(mini_corpus_retriever, provider)
    history: list[Message] = [
        {"role": "user", "content": "Tell me about honey bees."},
    ]

    answer, sources = pipeline.answer("Where exactly?", history)

    assert answer == "I couldn't find this information in the book."
    assert sources == []
    assert queries == [
        "Where exactly?",
        "Where exactly? Tell me about honey bees.",
    ]


def test_retrieval_retries_original_and_combined_follow_up_question(
    mini_corpus_retriever: Retriever,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_retrieve = mini_corpus_retriever.retrieve
    queries: list[str] = []

    def retrieve(query: str):
        queries.append(query)
        if query == "Where do they live? Tell me about honey bees.":
            return original_retrieve("Where do honey bees live?")
        return []

    monkeypatch.setattr(mini_corpus_retriever, "retrieve", retrieve)
    provider = FakeProvider(
        responses=[
            "Which colonies do they live in?",
            "Honey bees live in colonies [p. 1].",
        ]
    )
    pipeline = RAGPipeline(mini_corpus_retriever, provider)
    history: list[Message] = [
        {"role": "user", "content": "Tell me about honey bees."},
        {"role": "assistant", "content": "They live in colonies [p. 1]."},
    ]

    answer, sources = pipeline.answer("Where do they live?", history)

    assert answer.startswith("Honey bees live in colonies")
    assert sources[0].page == 1
    assert queries == [
        "Which colonies do they live in?",
        "Where do they live?",
        "Where do they live? Tell me about honey bees.",
    ]
