import argparse
import logging
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.ingestion import chunk_pages, extract_pages
from app.logging_config import configure_script_logging

logger = logging.getLogger(__name__)


def inspect_pdf(pdf_path: Path) -> None:
    settings = get_settings()
    pages = extract_pages(pdf_path)
    chunks = chunk_pages(pages, settings.chunk_size, settings.chunk_overlap)

    logger.info("Pages: %d", len(pages))
    logger.info("Chunks: %d", len(chunks))
    for chunk in random.sample(chunks, k=min(5, len(chunks))):
        logger.info("Chunk on page %d:\n%s", chunk.page, chunk.text)


def main() -> None:
    configure_script_logging()
    parser = argparse.ArgumentParser(description="Inspect chunks extracted from a PDF.")
    parser.add_argument("pdf_path", type=Path, help="Path to the PDF to inspect")
    args = parser.parse_args()
    inspect_pdf(args.pdf_path)


if __name__ == "__main__":
    main()
