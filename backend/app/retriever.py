import re
from collections.abc import Sequence
from difflib import SequenceMatcher
from typing import Protocol

from app.config import get_settings
from app.schemas import RetrievedChunk
from app.vectorstore import SearchResult, VectorStore


class QueryEmbedder(Protocol):
    def embed_query(self, text: str) -> list[float]: ...


class Retriever:
    def __init__(
        self,
        embeddings: QueryEmbedder,
        vector_store: VectorStore,
        top_k: int | None = None,
        min_score: float | None = None,
    ) -> None:
        settings = get_settings()
        self._embeddings = embeddings
        self._vector_store = vector_store
        self._top_k = top_k if top_k is not None else settings.top_k
        self._min_score = min_score if min_score is not None else settings.min_score

    def retrieve(
        self,
        question: str,
        top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        requested_top_k = top_k if top_k is not None else self._top_k
        results = self._vector_store.query(
            self._embeddings.embed_query(question),
            requested_top_k,
        )
        relevant = [
            self._to_retrieved_chunk(result)
            for result in results
            if result["score"] >= self._min_score
        ]
        return self._deduplicate(relevant)

    def count(self) -> int:
        return self._vector_store.count()

    @staticmethod
    def _to_retrieved_chunk(result: SearchResult) -> RetrievedChunk:
        return RetrievedChunk(
            text=result["text"],
            page=int(result["metadata"]["page"]),
            source=str(result["metadata"]["source"]),
            score=result["score"],
        )

    @classmethod
    def _deduplicate(
        cls,
        chunks: Sequence[RetrievedChunk],
    ) -> list[RetrievedChunk]:
        unique_chunks: list[RetrievedChunk] = []
        for chunk in chunks:
            if any(cls._is_duplicate(chunk, existing) for existing in unique_chunks):
                continue
            unique_chunks.append(chunk)
        return unique_chunks

    @staticmethod
    def _is_duplicate(left: RetrievedChunk, right: RetrievedChunk) -> bool:
        if left.page != right.page:
            return False

        left_text = Retriever._normalize_text(left.text)
        right_text = Retriever._normalize_text(right.text)
        if not left_text or not right_text:
            return left_text == right_text
        if left_text in right_text or right_text in left_text:
            return True

        similarity = SequenceMatcher(None, left_text, right_text).ratio()
        if similarity >= 0.85:
            return True

        left_words = left_text.split()
        right_words = right_text.split()
        shorter_length = min(len(left_words), len(right_words))
        shared_words = set(left_words) & set(right_words)
        return shorter_length > 0 and len(shared_words) / shorter_length >= 0.8

    @staticmethod
    def _normalize_text(text: str) -> str:
        normalized = re.sub(r"[^\w\s]", " ", text.casefold())
        return re.sub(r"\s+", " ", normalized).strip()
