import json
import logging
from collections.abc import AsyncIterator, Callable, Iterator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from pypdf import PdfReader
from starlette.concurrency import run_in_threadpool

from app.config import Settings, get_settings
from app.llm import (
    LLMConfigurationError,
    LLMError,
    LLMOverloadedError,
    LLMQuotaError,
    LLMTimeoutError,
    Message,
)
from app.rag import RAGPipeline
from app.schemas import ChatRequest, RetrievedChunk, Source

logger = logging.getLogger(__name__)
logging.getLogger("google_genai").setLevel(logging.WARNING)

_LLM_HTTP_ERRORS: tuple[tuple[type[LLMError], int, str], ...] = (
    (LLMConfigurationError, 500, "La configuration du fournisseur LLM est invalide."),
    (LLMQuotaError, 429, "Le quota du fournisseur LLM est dépassé."),
    (LLMOverloadedError, 503, "Le fournisseur LLM est temporairement surchargé."),
    (LLMTimeoutError, 504, "Le fournisseur LLM n'a pas répondu dans le délai imparti."),
    (LLMError, 502, "Une erreur est survenue auprès du fournisseur LLM."),
)


def get_pipeline(request: Request) -> RAGPipeline:
    return request.app.state.pipeline


def _cors_origins(settings: Settings) -> list[str]:
    return [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]


def create_app(
    pipeline_factory: Callable[[], RAGPipeline] | None = None,
    settings_override: Settings | None = None,
) -> FastAPI:
    settings = settings_override or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        factory = application.state.pipeline_factory
        application.state.pipeline = await run_in_threadpool(factory)
        try:
            yield
        finally:
            del application.state.pipeline

    application = FastAPI(title="RAG Book API", version="0.1.0", lifespan=lifespan)
    application.state.settings = settings
    application.state.pipeline_factory = pipeline_factory or (
        lambda: RAGPipeline(settings=settings)
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(settings),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.exception_handler(LLMError)
    async def llm_error_handler(_: Request, error: LLMError) -> JSONResponse:
        status_code, message = _llm_error_response(error)
        return JSONResponse(status_code=status_code, content={"detail": message})

    @application.get("/api/health")
    def health(pipeline: RAGPipeline = Depends(get_pipeline)) -> dict[str, Any]:
        active_settings = get_settings()
        return {
            "status": "ok",
            "chunks": pipeline.count_chunks(),
            "provider": active_settings.llm_provider,
            "model": active_settings.llm_model,
        }

    @application.get("/api/book")
    def book(request: Request) -> Response:
        path = _book_path(request.app.state.settings)
        if not path.is_file():
            return JSONResponse(
                status_code=404,
                content={"detail": "Le fichier du livre est introuvable."},
            )
        return FileResponse(
            path,
            media_type="application/pdf",
            filename=path.name,
            content_disposition_type="inline",
        )

    @application.get("/api/book/info")
    def book_info(request: Request) -> dict[str, Any]:
        settings = request.app.state.settings
        path = _book_path(settings)
        available = path.is_file()
        title = settings.book_path.stem
        pages = 0
        if available:
            reader = PdfReader(str(path))
            pages = len(reader.pages)
            title = reader.metadata.title or path.stem
        return {
            "title": title,
            "pages": pages,
            "available": available,
        }

    @application.post("/api/chat")
    def chat(
        body: ChatRequest,
        pipeline: RAGPipeline = Depends(get_pipeline),
    ) -> dict[str, Any]:
        history = _history_messages(body)
        answer, sources = pipeline.answer(body.question, history=history)
        return {"answer": answer, "sources": _serialize_sources(sources)}

    @application.post("/api/chat/stream")
    def chat_stream(
        body: ChatRequest,
        pipeline: RAGPipeline = Depends(get_pipeline),
    ) -> StreamingResponse:
        history = _history_messages(body)
        response_stream, sources = pipeline.answer_stream(
            body.question,
            history=history,
        )
        return StreamingResponse(
            _sse_events(response_stream, sources),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return application


def _book_path(settings: Settings) -> Path:
    path = settings.book_path
    if path.is_absolute():
        return path
    return Path(__file__).resolve().parents[1] / path


def _history_messages(body: ChatRequest) -> list[Message]:
    return [
        {"role": message.role, "content": message.content}
        for message in body.history[-10:]
    ]


def _serialize_sources(sources: Sequence[RetrievedChunk]) -> list[dict[str, Any]]:
    return [
        Source(
            page=source.page,
            excerpt=source.text,
            score=source.score,
            source=source.source,
        ).model_dump()
        for source in sources
    ]


def _sse_event(event: str, data: Any) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def _sse_events(
    response_stream: Iterator[str],
    sources: list[RetrievedChunk],
) -> Iterator[str]:
    try:
        for token in response_stream:
            yield _sse_event("token", {"token": token})
        yield _sse_event("sources", _serialize_sources(sources))
        yield _sse_event("done", {})
    except LLMError as error:
        _, message = _llm_error_response(error)
        yield _sse_event("error", {"message": message})
    except Exception:
        logger.exception("Unexpected error while streaming a chat response")
        yield _sse_event("error", {"message": "Une erreur est survenue pendant le flux."})


def _llm_error_response(error: LLMError) -> tuple[int, str]:
    for error_type, status_code, message in _LLM_HTTP_ERRORS:
        if isinstance(error, error_type):
            return status_code, message
    return 502, "Une erreur est survenue auprès du fournisseur LLM."


app = create_app()
