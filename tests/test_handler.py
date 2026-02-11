import base64
import io
import json
import os
import threading
import zipfile
from http.server import HTTPServer
from unittest.mock import patch
from urllib.request import Request, urlopen

import pytest

from app.handler import (
    HoneyBibleHandler,
    PUBLIC_DIR,
    _build_drive_filename,
    _clean_leader_name,
    _detect_file_format,
    _extract_csv_meta,
    _extract_leader,
    _extract_txt_from_zip,
    extract_multipart_field,
    extract_multipart_file,
)


def _make_multipart_payload(field_name, filename, content, boundary="testboundary"):
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
        f"Content-Type: text/csv\r\n"
        f"\r\n"
    ).encode("utf-8")
    body += content
    body += f"\r\n--{boundary}--\r\n".encode("utf-8")
    return body, f"multipart/form-data; boundary={boundary}"


def _make_multipart_with_field(file_name, file_content, field_name, field_value, boundary="testboundary"):
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{file_name}"\r\n'
        f"Content-Type: text/csv\r\n"
        f"\r\n"
    ).encode("utf-8")
    body += file_content
    body += (
        f"\r\n--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field_name}"\r\n'
        f"\r\n"
        f"{field_value}"
        f"\r\n--{boundary}--\r\n"
    ).encode("utf-8")
    return body, f"multipart/form-data; boundary={boundary}"


class TestExtractMultipartFile:
    def test_extract_multipart_file__valid_file__extracts_correctly(self):
        content = b"col1,col2\nval1,val2"
        payload, content_type = _make_multipart_payload("file", "test.csv", content)
        filename, data, error = extract_multipart_file(payload, content_type)
        assert filename == "test.csv"
        assert data == content
        assert error is None

    def test_extract_multipart_file__wrong_field_name__returns_error(self):
        content = b"col1,col2\nval1,val2"
        payload, content_type = _make_multipart_payload("other", "test.csv", content)
        filename, data, error = extract_multipart_file(payload, content_type)
        assert filename is None
        assert data is None
        assert error == "CSV file is required"

    def test_extract_multipart_file__non_multipart__returns_error(self):
        content_type = "application/json"
        payload = b'{"key": "value"}'
        filename, data, error = extract_multipart_file(payload, content_type)
        assert filename is None
        assert data is None
        assert error == "Expected multipart/form-data"


class TestResolvePublicPath:
    def _resolve(self, request_path):
        from app.handler import HoneyBibleHandler

        handler = HoneyBibleHandler.__new__(HoneyBibleHandler)
        return handler._resolve_public_path(request_path)

    def test_resolve_public_path__normal_path__returns_full_path(self):
        result = self._resolve("/index.html")
        assert result is not None
        assert result.endswith("index.html")
        assert os.path.realpath(PUBLIC_DIR) in result

    def test_resolve_public_path__root_path__resolves_to_index(self):
        result = self._resolve("/")
        assert result is not None
        assert result.endswith("index.html")

    def test_resolve_public_path__path_traversal__returns_none(self):
        result = self._resolve("/../../../etc/passwd")
        assert result is None

    def test_resolve_public_path__double_dot_in_middle__returns_none(self):
        result = self._resolve("/subdir/../../etc/passwd")
        assert result is None


class TestExtractMultipartField:
    def test_extract_multipart_field__텍스트_필드_추출_성공(self):
        payload, content_type = _make_multipart_with_field(
            "test.csv", b"col1,col2", "track_mode", "dual",
        )
        result = extract_multipart_field(payload, content_type, "track_mode")
        assert result == "dual"

    def test_extract_multipart_field__존재하지_않는_필드__None_반환(self):
        payload, content_type = _make_multipart_with_field(
            "test.csv", b"col1,col2", "track_mode", "dual",
        )
        result = extract_multipart_field(payload, content_type, "nonexistent")
        assert result is None

    def test_extract_multipart_field__비_multipart__None_반환(self):
        result = extract_multipart_field(b"plain text", "text/plain", "field")
        assert result is None

    def test_extract_multipart_field__single_값_추출(self):
        payload, content_type = _make_multipart_with_field(
            "test.csv", b"col1,col2", "track_mode", "single",
        )
        result = extract_multipart_field(payload, content_type, "track_mode")
        assert result == "single"


@pytest.fixture()
def test_server():
    server = HTTPServer(("127.0.0.1", 0), HoneyBibleHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


class TestHeadRequest:
    def test_head_루트__200_응답_바디_없음(self, test_server):
        req = Request(f"{test_server}/", method="HEAD")
        resp = urlopen(req)
        assert resp.status == 200
        assert resp.read() == b""

    def test_head_health__200_json_응답(self, test_server):
        req = Request(f"{test_server}/health", method="HEAD")
        resp = urlopen(req)
        assert resp.status == 200
        assert resp.headers["Content-Type"] == "application/json; charset=utf-8"
        assert resp.read() == b""


class TestHealthEndpoint:
    def test_get_health__200_ok_응답(self, test_server):
        resp = urlopen(f"{test_server}/health")
        assert resp.status == 200
        body = resp.read()
        assert b'"status"' in body
        assert b'"ok"' in body


class TestDetectFileFormat:
    def test_zip_매직바이트__zip_반환(self):
        assert _detect_file_format("file.csv", b"PK\x03\x04rest") == "zip"

    def test_zip_확장자__zip_반환(self):
        assert _detect_file_format("chat.zip", b"some bytes") == "zip"

    def test_txt_확장자__txt_반환(self):
        assert _detect_file_format("chat.txt", b"some text") == "txt"

    def test_csv_확장자__csv_반환(self):
        assert _detect_file_format("chat.csv", b"col1,col2") == "csv"

    def test_확장자_없음__csv_기본값(self):
        assert _detect_file_format("chatfile", b"col1,col2") == "csv"

    def test_filename_None__csv_기본값(self):
        assert _detect_file_format(None, b"col1,col2") == "csv"


class TestExtractTxtFromZip:
    def _make_zip(self, files):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            for name, content in files.items():
                zf.writestr(name, content)
        return buf.getvalue()

    def test_정상_zip__txt_추출(self):
        zip_bytes = self._make_zip({"chat.txt": "hello", "image.png": "png"})
        data, error = _extract_txt_from_zip(zip_bytes)
        assert error is None
        assert data == b"hello"

    def test_txt_없는_zip__에러_반환(self):
        zip_bytes = self._make_zip({"image.png": "png"})
        data, error = _extract_txt_from_zip(zip_bytes)
        assert data is None
        assert "TXT" in error

    def test_잘못된_zip__에러_반환(self):
        data, error = _extract_txt_from_zip(b"not a zip")
        assert data is None
        assert "ZIP" in error


class TestUploadDriveEndpoint:
    def test_drive_미설정__적절한_에러_응답(self, test_server, monkeypatch):
        monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_JSON", raising=False)
        monkeypatch.delenv("GOOGLE_DRIVE_FOLDER_ID", raising=False)

        xlsx_b64 = base64.b64encode(b"fake xlsx content").decode("ascii")
        body = json.dumps({"xlsx_base64": xlsx_b64}).encode("utf-8")

        req = Request(
            f"{test_server}/upload-drive",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        resp = urlopen(req)
        assert resp.status == 200
        data = json.loads(resp.read())
        assert data["success"] is False
        assert "설정되지 않았습니다" in data["message"]

    def test_xlsx_base64_누락__400_에러(self, test_server):
        body = json.dumps({}).encode("utf-8")
        req = Request(
            f"{test_server}/upload-drive",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urlopen(req)
            assert False, "400 에러가 발생해야 합니다"
        except Exception as exc:
            assert "400" in str(exc)

    def test_잘못된_JSON__400_에러(self, test_server):
        body = b"not json at all"
        req = Request(
            f"{test_server}/upload-drive",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urlopen(req)
            assert False, "400 에러가 발생해야 합니다"
        except Exception as exc:
            assert "400" in str(exc)


class TestExtractCsvMeta:
    def test_정상_CSV_파일명__방이름_및_시점_추출(self):
        room, date = _extract_csv_meta("KakaoTalk_Chat_꿀성경 - 교육국_2026-02-09-10-50-28.csv")
        assert room == "꿀성경 - 교육국"
        assert date == "2026/02/09-10:50"

    def test_초_없는_CSV_파일명__정상_추출(self):
        room, date = _extract_csv_meta("KakaoTalk_Chat_테스트방_2026-01-15-08-30.csv")
        assert room == "테스트방"
        assert date == "2026/01/15-08:30"

    def test_일반_파일명__None_반환(self):
        room, date = _extract_csv_meta("data.csv")
        assert room is None
        assert date is None

    def test_None_파일명__None_반환(self):
        room, date = _extract_csv_meta(None)
        assert room is None
        assert date is None


class TestCleanLeaderName:
    def test_3글자_한글__성_제거(self):
        assert _clean_leader_name("홍길동") == "길동"

    def test_영어_제거(self):
        assert _clean_leader_name("홍길동ABC") == "길동"

    def test_공백_제거(self):
        assert _clean_leader_name("홍 길 동") == "길동"

    def test_2글자_한글__그대로(self):
        assert _clean_leader_name("길동") == "길동"

    def test_4글자_한글__그대로(self):
        assert _clean_leader_name("남궁길동") == "남궁길동"

    def test_영어와_공백_복합_제거(self):
        assert _clean_leader_name("Kim 길동") == "길동"

    def test_영어만__원본_반환(self):
        assert _clean_leader_name("John") == "John"

    def test_한글_영어_혼합_3글자_아님__성_유지(self):
        assert _clean_leader_name("길동A") == "길동"

    def test_숫자_포함__숫자_유지(self):
        assert _clean_leader_name("홍길동1") == "홍길동1"


class TestExtractLeader:
    def test_키워드_포함_메시지__후처리된_방장_반환(self):
        rows = [
            ("홍길동", "안녕하세요"),
            ("김방장", "꿀성경 진행 방식 안내입니다"),
            ("이참여", "감사합니다"),
        ]
        assert _extract_leader(rows) == "방장"

    def test_키워드_없음__None_반환(self):
        rows = [
            ("홍길동", "안녕하세요"),
            ("이참여", "감사합니다"),
        ]
        assert _extract_leader(rows) is None

    def test_빈_rows__None_반환(self):
        assert _extract_leader([]) is None

    def test_영어_포함_이름__영어_제거_후_반환(self):
        rows = [
            ("Kim 길동", "꿀성경 진행 방식 안내"),
        ]
        assert _extract_leader(rows) == "길동"


class TestBuildDriveFilename:
    def test_방장_및_날짜_모두_있음(self):
        result = _build_drive_filename("김방장", "2026/02/09-10:50")
        assert result == "result_김방장_2026/02/09-10:50.xlsx"

    def test_방장만_있음(self):
        result = _build_drive_filename("김방장", None)
        assert result == "result_김방장.xlsx"

    def test_날짜만_있음(self):
        result = _build_drive_filename(None, "2026/02/09-10:50")
        assert result == "result_결과_2026/02/09-10:50.xlsx"

    def test_둘_다_없음__None_반환(self):
        result = _build_drive_filename(None, None)
        assert result is None
