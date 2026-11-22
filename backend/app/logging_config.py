import logging


_NOISY_LOGGERS = (
    "httpx",
    "httpx2",
    "huggingface_hub",
    "sentence_transformers",
    "google_genai",
)


def configure_script_logging() -> None:
    logging.basicConfig(level=logging.INFO)
    for logger_name in _NOISY_LOGGERS:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
