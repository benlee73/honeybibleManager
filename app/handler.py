import json
import mimetypes
import os
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler
from urllib.parse import unquote

from app.analyzer import analyze_chat, build_output_csv, decode_csv_payload
from app.logger import get_logger

logger = get_logger("handler")

PUBLIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public")


def _parse_multipart(payload, content_type):
    header = f"Content-Type: {content_type}\r\n\r\n".encode("utf-8")
    return BytesParser(policy=default).parsebytes(header + payload)


def extract_multipart_field(payload, content_type, field_name):
    try:
        message = _parse_multipart(payload, content_type)
    except Exception:
        return None

    if message.get_content_maintype() != "multipart":
        return None

    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue
        name = part.get_param("name", header="content-disposition")
        if name != field_name:
            continue
        data = part.get_payload(decode=True)
        if data is None:
            return None
        return data.decode("utf-8", errors="replace").strip()

    return None


def extract_multipart_file(payload, content_type, field_name="file"):
    try:
        header = f"Content-Type: {content_type}\r\n\r\n".encode("utf-8")
        message = BytesParser(policy=default).parsebytes(header + payload)
    except Exception:
        return None, None, "Failed to parse multipart payload"

    if message.get_content_maintype() != "multipart":
        return None, None, "Expected multipart/form-data"

    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue
        name = part.get_param("name", header="content-disposition")
        if name != field_name:
            continue
        filename = part.get_filename()
        data = part.get_payload(decode=True)
        return filename, data, None

    return None, None, "CSV file is required"


class HoneyBibleHandler(BaseHTTPRequestHandler):
    server_version = "HoneyBibleServer/0.1"

    def _send_json(self, status_code, payload):
        if status_code >= 400:
            logger.warning("에러 응답 %d: %s", status_code, payload.get("message", ""))
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors()
        self.end_headers()
        self.wfile.write(body)

    def _send_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _resolve_public_path(self, request_path):
        clean_path = request_path.split("?", 1)[0].split("#", 1)[0]
        clean_path = unquote(clean_path or "/")
        if clean_path in ("", "/"):
            clean_path = "/index.html"
        clean_path = clean_path.lstrip("/")

        base_path = os.path.realpath(PUBLIC_DIR)
        target_path = os.path.realpath(os.path.join(base_path, clean_path))
        if not target_path.startswith(base_path + os.sep):
            return None
        return target_path

    def _send_file(self, file_path):
        if not file_path or not os.path.isfile(file_path):
            logger.warning("파일 없음 404: %s", file_path)
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Not found")
            return

        content_type, _ = mimetypes.guess_type(file_path)
        if not content_type:
            content_type = "application/octet-stream"

        try:
            with open(file_path, "rb") as handle:
                body = handle.read()
        except OSError:
            logger.error("파일 읽기 실패 500: %s", file_path)
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Failed to read file")
            return

        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors()
        self.end_headers()

    def do_GET(self):
        logger.info("요청 수신: GET %s", self.path)
        if self.path.startswith("/analyze"):
            self._send_json(405, {"message": "Method not allowed"})
            return

        file_path = self._resolve_public_path(self.path)
        self._send_file(file_path)

    def do_POST(self):
        logger.info("요청 수신: POST %s", self.path)
        if self.path != "/analyze":
            self._send_json(404, {"message": "Not found"})
            return

        content_type = self.headers.get("Content-Type")
        if not content_type:
            self._send_json(400, {"message": "Missing Content-Type header"})
            return

        if "multipart/form-data" not in content_type:
            self._send_json(400, {"message": "Expected multipart/form-data"})
            return

        content_length = self.headers.get("Content-Length")
        if not content_length:
            self._send_json(411, {"message": "Missing Content-Length header"})
            return

        try:
            length = int(content_length)
        except ValueError:
            self._send_json(400, {"message": "Invalid Content-Length header"})
            return

        if length <= 0:
            self._send_json(400, {"message": "CSV file is empty"})
            return

        payload = self.rfile.read(length)
        filename, file_bytes, error_message = extract_multipart_file(
            payload,
            content_type,
        )
        if error_message:
            self._send_json(400, {"message": error_message})
            return

        if not file_bytes:
            self._send_json(400, {"message": "CSV file is empty"})
            return

        track_mode = extract_multipart_field(payload, content_type, "track_mode")
        if track_mode not in ("single", "dual"):
            track_mode = "single"

        csv_text = decode_csv_payload(file_bytes)
        users = analyze_chat(csv_text, track_mode=track_mode)
        output_csv = build_output_csv(users, track_mode=track_mode)
        logger.info("분석 완료: %d명 처리", len(users))

        filename = "honeybible-results.csv"
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header(
            "Content-Disposition",
            f'attachment; filename="{filename}"',
        )
        self.send_header("Content-Length", str(len(output_csv)))
        self._send_cors()
        self.end_headers()
        self.wfile.write(output_csv)
