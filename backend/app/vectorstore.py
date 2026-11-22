from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, TypedDict

import chromadb
from chromadb.api.models.Collection import Collection

from app.config import get_settings
from app.embeddings import EmbeddingService
from app.schemas import Chunk

_BATCH_SIZE = 64


class SearchResult(TypedDict):
    text: str
    metadata: dict[str, str | int]
    score: float


class EmbeddingProvider(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


class VectorStore:
    def __init__(
        self,
        path: Path | None = None,
        collection_name: str | None = None,
        embedding_service: EmbeddingProvider | None = None,
    ) -> None:
        settings = get_settings()
        chroma_path = path if path is not None else settings.chroma_path
        name = collection_name if collection_name is not None else settings.collection_name
        self._client = chromadb.PersistentClient(path=str(chroma_path))
        self._collection: Collection = self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )
        self._embedding_service = embedding_service or EmbeddingService()

    def add_chunks(self, chunks: Sequence[Chunk]) -> int:
        for start in range(0, len(chunks), _BATCH_SIZE):
            batch = chunks[start : start + _BATCH_SIZE]
            embeddings = self._embedding_service.embed_documents(
                [chunk.text for chunk in batch]
            )
            self._collection.upsert(
                ids=[chunk.id for chunk in batch],
                documents=[chunk.text for chunk in batch],
                embeddings=embeddings,
                metadatas=[
                    {
                        "page": chunk.page,
                        "source": chunk.source,
                        "chunk_index": chunk.chunk_index,
                    }
                    for chunk in batch
                ],
            )
        return len(chunks)

    def query(self, embedding: list[float], top_k: int) -> list[SearchResult]:
        result = self._collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        documents = result["documents"][0]
        metadatas = result["metadatas"][0]
        distances = result["distances"][0]
        matches: list[SearchResult] = []
        for text, metadata, distance in zip(documents, metadatas, distances):
            if text is None or metadata is None or distance is None:
                continue
            matches.append(
                {
                    "text": text,
                    "metadata": {
                        "page": int(metadata["page"]),
                        "source": str(metadata["source"]),
                    },
                    "score": 1.0 - float(distance),
                }
            )
        return matches

    def count(self) -> int:
        return self._collection.count()

    def reset(self) -> None:
        collection_name = self._collection.name
        self._client.delete_collection(collection_name)
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
