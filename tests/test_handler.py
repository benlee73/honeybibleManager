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
    MAX_DECOMPRESSED_BYTES,
    MAX_DRIVE_PAYLOAD_BYTES,
    MAX_UPLOAD_BYTES,
    HoneyBibleHandler,
    PUBLIC_DIR,
    _build_drive_filename,
    _clean_leader_name,
    _detect_file_format,
    _detect_schedule_type,
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
        assert result == "꿀성경_김방장_20260209_1050.xlsx"

    def test_방장만_있음(self):
        result = _build_drive_filename("김방장", None)
        assert result == "꿀성경_김방장.xlsx"

    def test_날짜만_있음(self):
        result = _build_drive_filename(None, "2026/02/09-10:50")
        assert result == "꿀성경_결과_20260209_1050.xlsx"

    def test_둘_다_없음__None_반환(self):
        result = _build_drive_filename(None, None)
        assert result is None

    def test_room_name_포함(self):
        result = _build_drive_filename("방장", "2026/02/09-10:50", room_name="꿀성경 2026 성경일독 part1")
        assert result == "꿀성경_방장_20260209_1050_2026 성경일독 part1.xlsx"

    def test_room_name_꿀성경_접두사_제거(self):
        result = _build_drive_filename("방장", "2026/02/09-10:50", room_name="꿀성경 - 교육국")
        assert result == "꿀성경_방장_20260209_1050_교육국.xlsx"

    def test_room_name_None__기존_형식(self):
        result = _build_drive_filename("방장", "2026/02/09-10:50", room_name=None)
        assert result == "꿀성경_방장_20260209_1050.xlsx"

    def test_room_name_빈문자열__기존_형식(self):
        result = _build_drive_filename("방장", "2026/02/09-10:50", room_name="")
        assert result == "꿀성경_방장_20260209_1050.xlsx"


class TestDetectScheduleType:
    def test_dual_모드__dual_반환(self):
        assert _detect_schedule_type([], "아무방", "dual") == "dual"

    def test_교육국_방이름__education_반환(self):
        assert _detect_schedule_type([], "꿀성경 - 교육국", "single") == "education"

    def test_성경일독_키워드__bible_반환(self):
        rows = [("user1", "창세기 1장"), ("user2", "출애굽기 2장")]
        assert _detect_schedule_type(rows, "일반방", "single") == "bible"

    def test_신약일독_키워드__nt_반환(self):
        rows = [("user1", "마태복음 1장"), ("user2", "마가복음 2장")]
        assert _detect_schedule_type(rows, "일반방", "single") == "nt"

    def test_키워드_없음__unknown_반환(self):
        rows = [("user1", "안녕하세요")]
        assert _detect_schedule_type(rows, "일반방", "single") == "unknown"


def _make_analyze_payload(filename, file_content, fields=None, boundary="testboundary"):
    """POST /analyze용 multipart 페이로드를 생성한다."""
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n"
        f"\r\n"
    ).encode("utf-8")
    body += file_content
    for name, value in (fields or {}).items():
        body += (
            f"\r\n--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n'
            f"\r\n"
            f"{value}"
        ).encode("utf-8")
    body += f"\r\n--{boundary}--\r\n".encode("utf-8")
    return body, f"multipart/form-data; boundary={boundary}"


# CSV용 최소 데이터
_CSV_DATA = (
    "Date,User,Message\n"
    "2026-02-10,홍길동,꿀성경 진행 방식 안내\n"
    "2026-02-10,김철수,1/6 ❤️\n"
).encode("utf-8")

# TXT용 (카카오톡 모바일 내보내기 형식)
_TXT_DATA = (
    "홍길동 님과 카카오톡 대화\n"
    "저장한 날짜 : 2026년 2월 10일 오전 10:30\n"
    "\n"
    "2026년 2월 10일 월요일\n"
    "홍길동 : 꿀성경 진행 방식 안내\n"
    "김철수 : 1/6 ❤️\n"
).encode("utf-8")


class TestAnalyzeEndpoint:
    def test_CSV_파일_분석__정상_응답(self, test_server):
        body, content_type = _make_analyze_payload("chat.csv", _CSV_DATA)
        req = Request(
            f"{test_server}/analyze",
            data=body,
            headers={"Content-Type": content_type},
            method="POST",
        )
        resp = urlopen(req)
        assert resp.status == 200
        data = json.loads(resp.read())
        assert "xlsx_base64" in data
        assert "image_base64" in data
        assert "preview" in data
        assert "filename" in data
        assert "headers" in data["preview"]
        assert "rows" in data["preview"]

    def test_CSV_파일_분석__drive_filename_포함(self, test_server):
        body, content_type = _make_analyze_payload(
            "KakaoTalk_Chat_꿀성경방_2026-02-10-10-30.csv",
            _CSV_DATA,
        )
        req = Request(
            f"{test_server}/analyze",
            data=body,
            headers={"Content-Type": content_type},
            method="POST",
        )
        resp = urlopen(req)
        assert resp.status == 200
        data = json.loads(resp.read())
        assert "drive_filename" in data
        # 방장 '홍길동' → 후처리 → '길동'
        assert "길동" in data["drive_filename"]

    def test_TXT_파일_분석__정상_응답(self, test_server):
        body, content_type = _make_analyze_payload("chat.txt", _TXT_DATA)
        req = Request(
            f"{test_server}/analyze",
            data=body,
            headers={"Content-Type": content_type},
            method="POST",
        )
        resp = urlopen(req)
        assert resp.status == 200
        data = json.loads(resp.read())
        assert "xlsx_base64" in data
        assert "image_base64" in data
        assert "preview" in data

    def test_ZIP_파일_분석__정상_응답(self, test_server):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("chat.txt", _TXT_DATA.decode("utf-8"))
        zip_bytes = buf.getvalue()

        body, content_type = _make_analyze_payload("chat.zip", zip_bytes)
        req = Request(
            f"{test_server}/analyze",
            data=body,
            headers={"Content-Type": content_type},
            method="POST",
        )
        resp = urlopen(req)
        assert resp.status == 200
        data = json.loads(resp.read())
        assert "xlsx_base64" in data
        assert "image_base64" in data
        assert "preview" in data

    def test_track_mode_dual__정상_응답(self, test_server):
        body, content_type = _make_analyze_payload(
            "chat.csv", _CSV_DATA, fields={"track_mode": "dual"},
        )
        req = Request(
            f"{test_server}/analyze",
            data=body,
            headers={"Content-Type": content_type},
            method="POST",
        )
        resp = urlopen(req)
        assert resp.status == 200
        data = json.loads(resp.read())
        assert "xlsx_base64" in data
        assert "preview" in data

    def test_빈_파일__400_에러(self, test_server):
        body, content_type = _make_analyze_payload("empty.csv", b"")
        req = Request(
            f"{test_server}/analyze",
            data=body,
            headers={"Content-Type": content_type},
            method="POST",
        )
        try:
            urlopen(req)
            assert False, "400 에러가 발생해야 합니다"
        except Exception as exc:
            assert "400" in str(exc)


_SAMPLES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "resources", "samples",
)

_SAMPLE_CSV_PART1 = os.path.join(
    _SAMPLES_DIR,
    "KakaoTalk_Chat_\U0001f36f 2026 성경일독 part1_2026-02-11-10-28-57.csv",
)
_SAMPLE_CSV_EDUC = os.path.join(
    _SAMPLES_DIR,
    "KakaoTalk_Chat_꿀성경 - 교육국_2026-02-11-10-29-14.csv",
)
_SAMPLE_ZIP = os.path.join(
    _SAMPLES_DIR,
    "Kakaotalk_Chat_\U0001f36f 2026 성경일독 part1_20260210_121623.zip",
)

_samples_exist = all(
    os.path.isfile(p) for p in (_SAMPLE_CSV_PART1, _SAMPLE_CSV_EDUC, _SAMPLE_ZIP)
)


@pytest.mark.skipif(not _samples_exist, reason="resources/samples 파일 없음")
class TestAnalyzeEndpointWithSamples:
    """실제 카카오톡 내보내기 샘플 파일을 사용한 POST /analyze 통합 테스트."""

    def test_성경일독_CSV__정상_분석(self, test_server):
        with open(_SAMPLE_CSV_PART1, "rb") as f:
            file_bytes = f.read()
        filename = os.path.basename(_SAMPLE_CSV_PART1)
        body, content_type = _make_analyze_payload(filename, file_bytes)
        req = Request(
            f"{test_server}/analyze",
            data=body,
            headers={"Content-Type": content_type},
            method="POST",
        )
        resp = urlopen(req)
        assert resp.status == 200
        data = json.loads(resp.read())
        assert "xlsx_base64" in data
        assert "image_base64" in data
        preview = data["preview"]
        assert len(preview["headers"]) >= 3  # 이모티콘, 이름, 날짜 1개 이상
        assert len(preview["rows"]) >= 2  # 최소 2명 이상

    def test_성경일독_CSV__drive_filename_포함(self, test_server):
        with open(_SAMPLE_CSV_PART1, "rb") as f:
            file_bytes = f.read()
        filename = os.path.basename(_SAMPLE_CSV_PART1)
        body, content_type = _make_analyze_payload(filename, file_bytes)
        req = Request(
            f"{test_server}/analyze",
            data=body,
            headers={"Content-Type": content_type},
            method="POST",
        )
        resp = urlopen(req)
        data = json.loads(resp.read())
        # 방장 키워드("꿀성경 진행 방식 안내") 포함 → drive_filename 존재
        assert "drive_filename" in data
        assert data["drive_filename"].endswith(".xlsx")

    def test_교육국_CSV__정상_분석(self, test_server):
        with open(_SAMPLE_CSV_EDUC, "rb") as f:
            file_bytes = f.read()
        filename = os.path.basename(_SAMPLE_CSV_EDUC)
        body, content_type = _make_analyze_payload(filename, file_bytes)
        req = Request(
            f"{test_server}/analyze",
            data=body,
            headers={"Content-Type": content_type},
            method="POST",
        )
        resp = urlopen(req)
        assert resp.status == 200
        data = json.loads(resp.read())
        assert "xlsx_base64" in data
        assert "image_base64" in data
        assert len(data["preview"]["rows"]) >= 1

    def test_ZIP_파일__정상_분석(self, test_server):
        with open(_SAMPLE_ZIP, "rb") as f:
            file_bytes = f.read()
        filename = os.path.basename(_SAMPLE_ZIP)
        body, content_type = _make_analyze_payload(filename, file_bytes)
        req = Request(
            f"{test_server}/analyze",
            data=body,
            headers={"Content-Type": content_type},
            method="POST",
        )
        resp = urlopen(req)
        assert resp.status == 200
        data = json.loads(resp.read())
        assert "xlsx_base64" in data
        assert "image_base64" in data
        assert len(data["preview"]["rows"]) >= 2

    def test_성경일독_CSV_dual_모드__정상_분석(self, test_server):
        with open(_SAMPLE_CSV_PART1, "rb") as f:
            file_bytes = f.read()
        filename = os.path.basename(_SAMPLE_CSV_PART1)
        body, content_type = _make_analyze_payload(
            filename, file_bytes, fields={"track_mode": "dual"},
        )
        req = Request(
            f"{test_server}/analyze",
            data=body,
            headers={"Content-Type": content_type},
            method="POST",
        )
        resp = urlopen(req)
        assert resp.status == 200
        data = json.loads(resp.read())
        assert "xlsx_base64" in data
        assert "image_base64" in data
        assert "preview" in data

    def test_성경일독_CSV__xlsx_디코딩_가능(self, test_server):
        with open(_SAMPLE_CSV_PART1, "rb") as f:
            file_bytes = f.read()
        filename = os.path.basename(_SAMPLE_CSV_PART1)
        body, content_type = _make_analyze_payload(filename, file_bytes)
        req = Request(
            f"{test_server}/analyze",
            data=body,
            headers={"Content-Type": content_type},
            method="POST",
        )
        resp = urlopen(req)
        data = json.loads(resp.read())
        # base64 디코딩이 정상적으로 되는지 확인
        xlsx_bytes = base64.b64decode(data["xlsx_base64"])
        assert len(xlsx_bytes) > 0
        # XLSX 매직바이트 (PK ZIP)
        assert xlsx_bytes[:2] == b"PK"


class TestSizeLimit:
    def test_analyze_크기_초과_413(self, test_server):
        """MAX_UPLOAD_BYTES보다 큰 Content-Length로 요청 시 413 응답."""
        body = b"x" * 1024  # 실제 본문은 작게
        req = Request(
            f"{test_server}/analyze",
            data=body,
            headers={
                "Content-Type": "multipart/form-data; boundary=testboundary",
                "Content-Length": str(MAX_UPLOAD_BYTES + 1),
            },
            method="POST",
        )
        try:
            urlopen(req)
            assert False, "413 에러가 발생해야 합니다"
        except Exception as exc:
            assert "413" in str(exc)

    def test_drive_크기_초과_413(self, test_server):
        """MAX_DRIVE_PAYLOAD_BYTES보다 큰 Content-Length로 요청 시 413 응답."""
        body = b"{}"
        req = Request(
            f"{test_server}/upload-drive",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(MAX_DRIVE_PAYLOAD_BYTES + 1),
            },
            method="POST",
        )
        try:
            urlopen(req)
            assert False, "413 에러가 발생해야 합니다"
        except Exception as exc:
            assert "413" in str(exc)

    def test_zip_압축해제_크기_초과(self):
        """압축해제 크기가 MAX_DECOMPRESSED_BYTES를 초과하는 ZIP 파일 처리."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            # 실제 file_size가 MAX_DECOMPRESSED_BYTES보다 큰 TXT 파일 생성
            zf.writestr("chat.txt", "x" * (MAX_DECOMPRESSED_BYTES + 1))
        zip_bytes = buf.getvalue()

        data, error = _extract_txt_from_zip(zip_bytes)
        assert data is None
        assert "너무 큽니다" in error
