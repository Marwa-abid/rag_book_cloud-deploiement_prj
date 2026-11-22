import re
import unicodedata
from collections.abc import Iterator, Sequence

from app.config import Settings, get_settings
from app.embeddings import EmbeddingService
from app.llm import LLMProvider, Message, create_llm_provider
from app.retriever import Retriever
from app.schemas import RetrievedChunk
from app.vectorstore import VectorStore

_FRENCH_INDICATORS = {
    "comment",
    "pourquoi",
    "quel",
    "quelle",
    "quels",
    "quelles",
    "est",
    "sont",
    "dans",
    "avec",
    "pour",
    "livre",
    "peux",
    "explique",
    "décris",
    "décrire",
    "où",
}
_ENGLISH_INDICATORS = {
    "what",
    "why",
    "how",
    "when",
    "where",
    "which",
    "does",
    "do",
    "is",
    "are",
    "the",
    "book",
    "explain",
    "describe",
}
_PAGE_CITATION = re.compile(r"\[p\.\s*\d+\]", re.IGNORECASE)
_FRENCH_REJECTION = "je n'ai pas trouve cette information dans le livre"
_ENGLISH_REJECTIONS = {
    "i couldn't find this information in the book",
    "i could not find this information in the book",
    "i didn't find this information in the book",
    "i did not find this information in the book",
}


class RAGPipeline:
    def __init__(
        self,
        retriever: Retriever | None = None,
        provider: LLMProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        if retriever is None:
            embeddings = EmbeddingService()
            vector_store = VectorStore(
                self._settings.chroma_path,
                self._settings.collection_name,
                embedding_service=embeddings,
            )
            retriever = Retriever(embeddings, vector_store, self._settings.top_k)
        self._retriever = retriever
        self._provider = provider or create_llm_provider(self._settings)

    def count_chunks(self) -> int:
        return self._retriever.count()

    def answer(
        self,
        question: str,
        history: Sequence[Message] | None = None,
    ) -> tuple[str, list[RetrievedChunk]]:
        usable_history = self._usable_history(history)
        autonomous_question = self._standalone_question(question, usable_history)
        sources = self._retrieve_with_fallbacks(
            question,
            autonomous_question,
            usable_history,
        )
        if not sources:
            return self._not_found_message(question), []

        response = self._provider.generate(
            self._answer_messages(question, sources, usable_history)
        )
        if self._is_rejection(response):
            return response, []
        return response, sources

    def answer_stream(
        self,
        question: str,
        history: Sequence[Message] | None = None,
    ) -> tuple[Iterator[str], list[RetrievedChunk]]:
        usable_history = self._usable_history(history)
        autonomous_question = self._standalone_question(question, usable_history)
        sources = self._retrieve_with_fallbacks(
            question,
            autonomous_question,
            usable_history,
        )
        if not sources:
            return iter((self._not_found_message(question),)), []

        response_stream = self._provider.stream(
            self._answer_messages(question, sources, usable_history)
        )
        return self._clear_sources_on_rejection(response_stream, sources), sources

    def _clear_sources_on_rejection(
        self,
        response_stream: Iterator[str],
        sources: list[RetrievedChunk],
    ) -> Iterator[str]:
        response_parts: list[str] = []
        for token in response_stream:
            response_parts.append(token)
            yield token
        if self._is_rejection("".join(response_parts)):
            sources.clear()

    def _standalone_question(
        self,
        question: str,
        history: Sequence[Message],
    ) -> str:
        if not history:
            return question

        messages: list[Message] = [
            {
                "role": "system",
                "content": (
                    "Rewrite the user's latest question as one standalone "
                    "question only when it needs conversation context. If it is "
                    "already standalone, return it unchanged. Preserve the "
                    "language of the latest question. Return exactly one "
                    "sentence containing only the question, with no answer or "
                    "explanation. Do not include page citations or a previous "
                    "refusal. Limit your output to 300 characters."
                ),
            },
            *history[-8:],
            {"role": "user", "content": question},
        ]
        rewritten = self._provider.generate(messages).strip()
        if len(rewritten) > 300:
            return question
        rewritten = _PAGE_CITATION.sub("", rewritten).strip()
        if (
            not rewritten
            or not rewritten.endswith("?")
            or self._is_rejection(rewritten)
            or len(re.split(r"(?<=[.!?])\s+", rewritten)) > 1
        ):
            return question
        return rewritten

    def _retrieve_with_fallbacks(
        self,
        question: str,
        autonomous_question: str,
        history: Sequence[Message],
    ) -> list[RetrievedChunk]:
        queries = [autonomous_question, question]
        previous_user_question = next(
            (
                message["content"]
                for message in reversed(history)
                if message["role"] == "user"
            ),
            None,
        )
        if previous_user_question:
            queries.append(f"{question} {previous_user_question}")

        seen_queries: set[str] = set()
        for query in queries:
            if query in seen_queries:
                continue
            seen_queries.add(query)
            sources = self._retriever.retrieve(query)
            if sources:
                return sources
        return []

    @classmethod
    def _usable_history(cls, history: Sequence[Message] | None) -> list[Message]:
        if not history:
            return []

        excluded: set[int] = set()
        for index, message in enumerate(history):
            if message["role"] != "assistant" or not cls._is_rejection(
                message["content"]
            ):
                continue
            excluded.add(index)
            if index > 0 and history[index - 1]["role"] == "user":
                excluded.add(index - 1)

        usable: list[Message] = []
        for index, message in enumerate(history):
            if index in excluded:
                continue
            content = message["content"]
            if message["role"] == "assistant":
                content = _PAGE_CITATION.sub("", content).strip()
            usable.append({"role": message["role"], "content": content})
        return usable

    @staticmethod
    def _is_rejection(text: str) -> bool:
        normalized = unicodedata.normalize("NFKD", text).casefold()
        normalized = "".join(
            character
            for character in normalized
            if not unicodedata.combining(character)
        )
        normalized = normalized.replace("’", "'")
        normalized = re.sub(r"\s+", " ", normalized).strip(" .!?\"'`")
        return (
            normalized == _FRENCH_REJECTION
            or normalized in _ENGLISH_REJECTIONS
        )

    def _answer_messages(
        self,
        question: str,
        sources: Sequence[RetrievedChunk],
        history: Sequence[Message],
    ) -> list[Message]:
        context = "\n\n".join(
            f"[p. {source.page}]\n{source.text}" for source in sources
        )
        fallback = self._not_found_message(question)
        system_prompt = (
            "Answer in the same language as the user's original question, using "
            "only relevant information from the supplied book context. The "
            "retrieved context below takes precedence over all prior messages. "
            "Previous conversation messages may only help identify the subject "
            "and must never justify a refusal. Un refus précédent dans la "
            "conversation ne doit pas influencer ta réponse : réponds uniquement "
            "d'après le contexte fourni ci-dessous. A previous refusal in the "
            "conversation must not influence your response: answer only from "
            "the context provided below. Ignore context passages that are "
            "unrelated to the question. Never invent facts. The fallback "
            "sentence may be used only when none of the context passages "
            "discusses the subject of the question; use this exact sentence in "
            f"that case: {fallback} "
            "If the context discusses the subject but answers only partially, "
            "give all relevant available details completely, including durations, "
            "steps, and numbers, cite supporting pages as [p. X], and briefly say "
            "what the book does not specify. Do not refuse merely because an "
            "unrelated passage is present."
        )
        return [
            {"role": "system", "content": system_prompt},
            *history,
            {
                "role": "user",
                "content": (
                    f"Original question: {question}\n\n"
                    f"Retrieved book context:\n{context}"
                ),
            },
        ]

    @staticmethod
    def _not_found_message(question: str) -> str:
        words = set(re.findall(r"\w+", question.casefold()))
        french_matches = len(words & _FRENCH_INDICATORS)
        english_matches = len(words & _ENGLISH_INDICATORS)
        if french_matches > english_matches:
            return "Je n'ai pas trouvé cette information dans le livre."
        return "I couldn't find this information in the book."


RagService = RAGPipeline
