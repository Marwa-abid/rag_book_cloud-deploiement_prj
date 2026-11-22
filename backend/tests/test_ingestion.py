from pathlib import Path

import pytest

from app.ingestion import chunk_pages, clean_text, extract_pages
from app.schemas import Chunk


def test_clean_text_removes_hyphenation_page_numbers_and_extra_whitespace() -> None:
    text = "A hyphen-\nated word.\n\n  More   text. \n 12 \n"

    assert clean_text(text) == "A hyphenated word. More text."


def test_extract_pages_removes_repeated_headers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class FakePage:
        def __init__(self, text: str) -> None:
            self._text = text

        def extract_text(self) -> str:
            return self._text

    class FakeReader:
        def __init__(self, _: str) -> None:
            self.pages = [
                FakePage("Book Title\nFirst page text\n1"),
                FakePage("Book Title\nSecond page text\n2"),
                FakePage("Third page text\n3"),
            ]

    monkeypatch.setattr("app.ingestion.PdfReader", FakeReader)
    pdf_path = tmp_path / "book.pdf"
    pdf_path.touch()
    pages = extract_pages(pdf_path)

    assert [page["page"] for page in pages] == [1, 2, 3]
    assert [page["text"] for page in pages] == [
        "First page text",
        "Second page text",
        "Third page text",
    ]
    assert all(page["source"] == "book.pdf" for page in pages)


def test_chunk_pages_respects_chunk_size_and_includes_metadata() -> None:
    pages = [
        {
            "page": 7,
            "text": "alpha beta gamma delta epsilon zeta eta theta",
            "source": "book.pdf",
        }
    ]

    chunks = chunk_pages(pages, chunk_size=15, chunk_overlap=3)

    assert len(chunks) > 1
    assert all(len(chunk.text) <= 15 for chunk in chunks)
    assert all(isinstance(chunk, Chunk) for chunk in chunks)
    assert all(chunk.page == 7 for chunk in chunks)
    assert all(chunk.source == "book.pdf" for chunk in chunks)
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
    assert all(chunk.id for chunk in chunks)
    assert chunks == chunk_pages(pages, chunk_size=15, chunk_overlap=3)


@pytest.mark.parametrize(
    ("chunk_size", "chunk_overlap"),
    [(0, 0), (5, 5), (5, 6)],
)
def test_chunk_pages_rejects_invalid_chunk_configuration(
    chunk_size: int,
    chunk_overlap: int,
) -> None:
    with pytest.raises(ValueError):
        chunk_pages([], chunk_size, chunk_overlap)
