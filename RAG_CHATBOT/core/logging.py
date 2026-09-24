import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from core.config import BASE_DIR, get_settings


def configure_logging() -> None:
    settings = get_settings()

    log_path = Path(settings.log_file)
    if not log_path.is_absolute():
        log_path = BASE_DIR / log_path

    log_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        fmt="[%(asctime)s] %(levelname)s - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=10_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    logging.basicConfig(
        level=settings.log_level.upper(),
        handlers=[console_handler, file_handler],
        force=True,
    )

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(logger_name).disabled = False