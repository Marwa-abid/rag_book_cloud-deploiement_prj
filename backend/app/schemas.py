from typing import Literal

from pydantic import BaseModel, Field, field_validator


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)

    @field_validator("question", mode="before")
    @classmethod
    def strip_question(cls, question: str) -> str:
        return question.strip() if isinstance(question, str) else question


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(AskRequest):
    history: list[ChatMessage] = Field(default_factory=list)


class Source(BaseModel):
    page: int
    excerpt: str
    score: float
    source: str


class AskResponse(BaseModel):
    answer: str
    sources: list[Source]


class Chunk(BaseModel):
    id: str
    text: str
    page: int
    chunk_index: int
    source: str


class RetrievedChunk(BaseModel):
    text: str
    page: int
    source: str
    score: float
