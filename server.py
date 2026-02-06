import argparse
from http.server import HTTPServer

from app.handler import HoneyBibleHandler


def main():
    parser = argparse.ArgumentParser(description="Honey Bible CSV analyzer server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), HoneyBibleHandler)
    print(f"HoneyBible server running on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
