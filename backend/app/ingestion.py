import argparse
import hashlib
import logging
import re
from collections import Counter
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from app.config import get_settings
from app.schemas import Chunk

logger = logging.getLogger(__name__)

_PAGE_NUMBER_PATTERN = re.compile(r"(?:\d+|[-\u2013\u2014]\s*\d+\s*[-\u2013\u2014])")
_DEHYPHENATION_PATTERN = re.compile(r"(?<=\w)-[ \t]*\n[ \t]*(?=\w)")


def _normalized_line(line: str) -> str:
    return " ".join(line.split()).casefold()


def _find_repeated_lines(pages: list[dict[str, str | int]]) -> set[str]:
    if not pages:
        return set()

    line_counts: Counter[str] = Counter()
    for page in pages:
        page_text = str(page["text"])
        line_counts.update(
            {_normalized_line(line) for line in page_text.splitlines() if line.strip()}
        )

    page_count = len(pages)
    return {
        line
        for line, count in line_counts.items()
        if count > 1 and count / page_count > 0.30
    }


def clean_text(text: str, repeated_lines: set[str] | None = None) -> str:
    lines_to_remove = repeated_lines if repeated_lines is not None else set()
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    retained_lines = [
        line
        for line in lines
        if _normalized_line(line) not in lines_to_remove
        and not _PAGE_NUMBER_PATTERN.fullmatch(line.strip())
    ]
    cleaned = "\n".join(retained_lines)
    cleaned = _DEHYPHENATION_PATTERN.sub("", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def extract_pages(pdf_path: Path) -> list[dict[str, str | int]]:
    source_path = Path(pdf_path)
    if not source_path.is_file():
        raise FileNotFoundError(f"PDF file not found: {source_path}")

    reader = PdfReader(str(source_path))
    raw_pages = [
        {"page": page_number, "text": page.extract_text() or "", "source": source_path.name}
        for page_number, page in enumerate(reader.pages, start=1)
    ]
    repeated_lines = _find_repeated_lines(raw_pages)
    return [
        {
            "page": int(page["page"]),
            "text": clean_text(str(page["text"]), repeated_lines),
            "source": str(page["source"]),
        }
        for page in raw_pages
    ]


def chunk_pages(
    pages: list[dict[str, str | int]],
    chunk_size: int,
    chunk_overlap: int,
) -> list[Chunk]:
    if chunk_size <= 0 or chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("Require 0 <= chunk_overlap < chunk_size")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    chunks: list[Chunk] = []
    for page_data in pages:
        page_number = int(page_data["page"])
        source = Path(str(page_data["source"])).name
        for chunk_index, text in enumerate(splitter.split_text(str(page_data["text"]))):
            chunk_id = hashlib.sha256(
                f"{source}:{page_number}:{chunk_index}:{text}".encode("utf-8")
            ).hexdigest()
            chunks.append(
                Chunk(
                    id=chunk_id,
                    text=text,
                    page=page_number,
                    chunk_index=chunk_index,
                    source=source,
                )
            )
    return chunks


def ingest_pdf(pdf_path: Path) -> int:
    from app.vectorstore import VectorStore

    settings = get_settings()
    chunks = chunk_pages(
        extract_pages(pdf_path),
        settings.chunk_size,
        settings.chunk_overlap,
    )
    if not chunks:
        raise ValueError(f"No extractable text found in PDF: {pdf_path}")

    vector_store = VectorStore(settings.chroma_path, settings.collection_name)
    vector_store.add_chunks(chunks)
    logger.info("Indexed %s chunks from %s", len(chunks), pdf_path)
    return len(chunks)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Index a PDF book for RAG.")
    parser.add_argument("pdf_path", type=Path, help="Path to the PDF to index")
    args = parser.parse_args()
    ingest_pdf(args.pdf_path)


if __name__ == "__main__":
    main()
