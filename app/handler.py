import base64
import json
import mimetypes
import os
import re
import zipfile
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler
from io import BytesIO
from urllib.parse import unquote

from app.analyzer import (
    analyze_chat,
    build_output_xlsx,
    build_preview_data,
    decode_payload,
    parse_csv_rows,
)
from app.drive_uploader import is_drive_configured, upload_to_drive
from app.image_builder import build_output_image
from app.logger import get_logger
from app.txt_parser import extract_chat_meta, parse_txt

logger = get_logger("handler")

PUBLIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public")

_ZIP_MAGIC = b"PK\x03\x04"

# CSV 파일명 패턴: KakaoTalk_Chat_방이름_YYYY-MM-DD-HH-MM(-SS).csv
_CSV_FILENAME_RE = re.compile(
    r"KakaoTalk_Chat_(.+)_(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})"
)


def _build_drive_filename(room_name, saved_date):
    """방 이름과 저장 날짜로 Drive 업로드용 파일명을 생성한다.

    Args:
        room_name: 카톡방 이름 (None이면 기본값 사용)
        saved_date: "YYYY/MM/DD-HH:MM" 형식 (None이면 기본값 사용)

    Returns:
        str|None: "result_방이름_YYYY/MM/DD-HH:MM.xlsx" 또는 None
    """
    if not room_name and not saved_date:
        return None
    name_part = room_name or "결과"
    date_part = f"_{saved_date}" if saved_date else ""
    return f"result_{name_part}{date_part}.xlsx"


def _extract_csv_meta(filename):
    """CSV 파일명에서 방 이름과 내보내기 시점을 추출한다.

    Returns:
        tuple: (room_name, saved_date) — 각각 str|None
    """
    if not filename:
        return None, None
    m = _CSV_FILENAME_RE.search(filename)
    if not m:
        return None, None
    room_name = m.group(1)
    saved_date = f"{m.group(2)}/{m.group(3)}/{m.group(4)}-{m.group(5)}:{m.group(6)}"
    return room_name, saved_date


def _detect_file_format(filename, file_bytes):
    """확장자와 매직바이트로 파일 형식을 판별한다. csv/txt/zip 중 하나를 반환."""
    if file_bytes[:4] == _ZIP_MAGIC:
        return "zip"
    if filename:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext == "zip":
            return "zip"
        if ext == "txt":
            return "txt"
    return "csv"


def _extract_txt_from_zip(file_bytes):
    """ZIP 파일에서 첫 번째 TXT 파일을 추출하여 바이트로 반환한다."""
    try:
        zf = zipfile.ZipFile(BytesIO(file_bytes))
    except zipfile.BadZipFile:
        return None, "올바른 ZIP 파일이 아닙니다."
    txt_names = [n for n in zf.namelist() if n.lower().endswith(".txt")]
    if not txt_names:
        return None, "ZIP 파일 안에 TXT 파일이 없습니다."
    return zf.read(txt_names[0]), None


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

    def _handle_get(self, send_body=True):
        logger.info("요청 수신: %s %s", self.command, self.path)
        clean = self.path.split("?", 1)[0].split("#", 1)[0]

        if clean == "/health":
            body = b'{"status":"ok"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if send_body:
                self.wfile.write(body)
            return

        if clean.startswith("/analyze"):
            self._send_json(405, {"message": "Method not allowed"})
            return

        file_path = self._resolve_public_path(self.path)
        if send_body:
            self._send_file(file_path)
        else:
            self._send_file_head(file_path)

    def _send_file_head(self, file_path):
        if not file_path or not os.path.isfile(file_path):
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            return

        content_type, _ = mimetypes.guess_type(file_path)
        if not content_type:
            content_type = "application/octet-stream"

        try:
            size = os.path.getsize(file_path)
        except OSError:
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(size))
        self.end_headers()

    def do_GET(self):
        self._handle_get(send_body=True)

    def do_HEAD(self):
        self._handle_get(send_body=False)

    def _handle_upload_drive(self):
        content_type = self.headers.get("Content-Type", "")
        content_length = self.headers.get("Content-Length")
        if not content_length:
            self._send_json(411, {"message": "Missing Content-Length header"})
            return

        try:
            length = int(content_length)
        except ValueError:
            self._send_json(400, {"message": "Invalid Content-Length header"})
            return

        payload = self.rfile.read(length)

        try:
            body = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            self._send_json(400, {"message": "올바른 JSON 형식이 아닙니다."})
            return

        xlsx_base64 = body.get("xlsx_base64")
        if not xlsx_base64:
            self._send_json(400, {"message": "xlsx_base64 필드가 필요합니다."})
            return

        if not is_drive_configured():
            self._send_json(200, {"success": False, "message": "Google Drive가 설정되지 않았습니다."})
            return

        drive_filename = body.get("filename")

        try:
            file_bytes = base64.b64decode(xlsx_base64)
        except Exception:
            self._send_json(400, {"message": "base64 디코딩에 실패했습니다."})
            return

        result = upload_to_drive(file_bytes, filename=drive_filename)
        self._send_json(200, result)

    def do_POST(self):
        logger.info("요청 수신: POST %s", self.path)
        clean_path = self.path.split("?", 1)[0].split("#", 1)[0]

        if clean_path == "/upload-drive":
            self._handle_upload_drive()
            return

        if clean_path != "/analyze":
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
            self._send_json(400, {"message": "파일이 비어 있습니다."})
            return

        track_mode = extract_multipart_field(payload, content_type, "track_mode")
        if track_mode not in ("single", "dual"):
            track_mode = "single"

        file_format = _detect_file_format(filename, file_bytes)

        room_name = None
        saved_date = None

        if file_format == "zip":
            txt_bytes, zip_error = _extract_txt_from_zip(file_bytes)
            if zip_error:
                self._send_json(400, {"message": zip_error})
                return
            text = decode_payload(txt_bytes)
            rows = parse_txt(text)
            meta = extract_chat_meta(text)
            room_name = meta["room_name"]
            saved_date = meta["saved_date"]
        elif file_format == "txt":
            text = decode_payload(file_bytes)
            rows = parse_txt(text)
            meta = extract_chat_meta(text)
            room_name = meta["room_name"]
            saved_date = meta["saved_date"]
        else:
            csv_text = decode_payload(file_bytes)
            rows = parse_csv_rows(csv_text)
            room_name, saved_date = _extract_csv_meta(filename)

        theme = extract_multipart_field(payload, content_type, "theme") or "honey"

        users = analyze_chat(rows=rows, track_mode=track_mode)
        xlsx_bytes = build_output_xlsx(users, track_mode=track_mode)
        image_bytes = build_output_image(users, track_mode=track_mode, theme=theme)
        headers, rows = build_preview_data(users, track_mode=track_mode)
        logger.info("분석 완료: %d명 처리", len(users))

        drive_filename = _build_drive_filename(room_name, saved_date)

        response_payload = {
            "xlsx_base64": base64.b64encode(xlsx_bytes).decode("ascii"),
            "image_base64": base64.b64encode(image_bytes).decode("ascii"),
            "filename": "honeybible-results.xlsx",
            "preview": {"headers": headers, "rows": rows},
        }
        if drive_filename:
            response_payload["drive_filename"] = drive_filename

        self._send_json(200, response_payload)
