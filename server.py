import argparse
import os
from http.server import ThreadingHTTPServer

from app.handler import HoneyBibleHandler
from app.logger import get_logger, setup_logging


def _load_env(path=".env"):
    """프로젝트 루트의 .env 파일에서 환경변수를 로딩한다."""
    env_path = os.path.join(os.path.dirname(__file__), path)
    if not os.path.isfile(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if key and _ == "=":
                os.environ.setdefault(key, value)

logger = get_logger("server")


def main():
    _load_env()
    setup_logging()

    parser = argparse.ArgumentParser(description="Honey Bible CSV analyzer server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), HoneyBibleHandler)
    logger.info("서버 시작: http://%s:%s", args.host, args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("서버 종료 (KeyboardInterrupt)")
    finally:
        server.server_close()
        logger.info("서버 종료 완료")


if __name__ == "__main__":
    main()
