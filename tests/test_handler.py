import os
from unittest.mock import patch

import pytest

from app.handler import PUBLIC_DIR, extract_multipart_file


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
