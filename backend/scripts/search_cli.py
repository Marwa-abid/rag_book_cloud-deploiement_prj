import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.embeddings import EmbeddingService
from app.logging_config import configure_script_logging
from app.retriever import Retriever
from app.vectorstore import VectorStore

logger = logging.getLogger(__name__)


def run_search_loop(retriever: Retriever) -> None:
    while True:
        try:
            question = input("Question (quit pour sortir) : ").strip()
        except EOFError:
            logger.info("")
            return

        if question.casefold() == "quit":
            return
        if not question:
            continue

        results = retriever.retrieve(question)
        if not results:
            logger.info("Aucun passage pertinent trouvé.")
            continue
        for result in results:
            excerpt = result.text[:300]
            if len(result.text) > 300:
                excerpt += "..."
            logger.info(
                f"\nPage {result.page} | score {result.score:.3f} "
                f"| {result.source}\n{excerpt}"
            )


def main() -> None:
    configure_script_logging()
    settings = get_settings()
    embeddings = EmbeddingService()
    vector_store = VectorStore(
        settings.chroma_path,
        settings.collection_name,
        embedding_service=embeddings,
    )
    retriever = Retriever(embeddings, vector_store)
    run_search_loop(retriever)


if __name__ == "__main__":
    main()
