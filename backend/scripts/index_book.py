import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tqdm import tqdm

from app.config import get_settings
from app.ingestion import chunk_pages, extract_pages
from app.logging_config import configure_script_logging
from app.vectorstore import VectorStore

logger = logging.getLogger(__name__)
_BATCH_SIZE = 64


def index_book(pdf_path: Path) -> tuple[int, float]:
    started_at = time.perf_counter()
    settings = get_settings()
    pages = extract_pages(pdf_path)
    chunks = chunk_pages(pages, settings.chunk_size, settings.chunk_overlap)
    if not chunks:
        raise ValueError(f"No extractable text found in PDF: {pdf_path}")

    vector_store = VectorStore()
    for start in tqdm(
        range(0, len(chunks), _BATCH_SIZE),
        desc="Indexing chunks",
        unit="batch",
    ):
        vector_store.add_chunks(chunks[start : start + _BATCH_SIZE])

    return len(chunks), time.perf_counter() - started_at


def main() -> None:
    configure_script_logging()
    parser = argparse.ArgumentParser(description="Index a PDF book in ChromaDB.")
    parser.add_argument("pdf_path", type=Path, help="Path to the PDF to index")
    args = parser.parse_args()

    chunk_count, elapsed_seconds = index_book(args.pdf_path)
    logger.info("Indexed %d chunks in %.2f seconds.", chunk_count, elapsed_seconds)


if __name__ == "__main__":
    main()
