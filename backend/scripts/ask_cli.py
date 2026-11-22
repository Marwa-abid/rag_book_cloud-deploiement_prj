import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.logging_config import configure_script_logging
from app.rag import RAGPipeline
from app.schemas import RetrievedChunk

logger = logging.getLogger(__name__)


def ask_once(pipeline: RAGPipeline, question: str) -> None:
    stream, sources = pipeline.answer_stream(question)
    sys.stdout.write("Answer: ")
    for token in stream:
        sys.stdout.write(token)
        sys.stdout.flush()
    sys.stdout.write("\n")
    _display_sources(sources)


def run_interactive(pipeline: RAGPipeline) -> None:
    history: list[dict[str, str]] = []
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

        stream, sources = pipeline.answer_stream(question, history=history)
        sys.stdout.write("Answer: ")
        answer_parts: list[str] = []
        for token in stream:
            answer_parts.append(token)
            sys.stdout.write(token)
            sys.stdout.flush()
        sys.stdout.write("\n")
        _display_sources(sources)
        history.extend(
            [
                {"role": "user", "content": question},
                {"role": "assistant", "content": "".join(answer_parts)},
            ]
        )


def _display_sources(sources: list[RetrievedChunk]) -> None:
    if not sources:
        return
    sys.stdout.write("Sources:\n")
    for source in sources:
        excerpt = source.text[:300]
        if len(source.text) > 300:
            excerpt += "..."
        sys.stdout.write(
            f"- [p. {source.page}] score={source.score:.3f} "
            f"({source.source}): {excerpt}\n"
        )


def main() -> None:
    configure_script_logging()
    parser = argparse.ArgumentParser(description="Ask questions about the indexed book.")
    parser.add_argument(
        "question",
        nargs="*",
        help="Question to ask; omit it to start an interactive session.",
    )
    args = parser.parse_args()
    pipeline = RAGPipeline()
    if args.question:
        ask_once(pipeline, " ".join(args.question))
        return
    run_interactive(pipeline)


if __name__ == "__main__":
    main()
