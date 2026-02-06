import argparse
from http.server import HTTPServer

from app.handler import HoneyBibleHandler
from app.logger import get_logger, setup_logging

logger = get_logger("server")


def main():
    setup_logging()

    parser = argparse.ArgumentParser(description="Honey Bible CSV analyzer server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), HoneyBibleHandler)
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
