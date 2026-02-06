import logging
import sys

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
LOG_FILE = "server.log"


def setup_logging(level=logging.INFO):
    """로깅 설정을 초기화한다. 콘솔과 파일 핸들러를 등록한다."""
    root_logger = logging.getLogger("honeybible")
    root_logger.setLevel(level)

    if root_logger.handlers:
        return root_logger

    formatter = logging.Formatter(LOG_FORMAT)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    return root_logger


def get_logger(name):
    """모듈별 로거를 반환한다."""
    return logging.getLogger(f"honeybible.{name}")
