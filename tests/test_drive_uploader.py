import os
from unittest.mock import MagicMock, patch

import pytest

from app.drive_uploader import is_drive_configured, upload_to_drive

_OAUTH_ENVS = {
    "GOOGLE_CLIENT_ID": "test-client-id",
    "GOOGLE_CLIENT_SECRET": "test-client-secret",
    "GOOGLE_REFRESH_TOKEN": "test-refresh-token",
    "GOOGLE_DRIVE_FOLDER_ID": "folder123",
}


class TestIsDriveConfigured:
    def test_환경변수_모두_설정__True_반환(self, monkeypatch):
        for key, value in _OAUTH_ENVS.items():
            monkeypatch.setenv(key, value)
        assert is_drive_configured() is True

    def test_클라이언트ID_없음__False_반환(self, monkeypatch):
        for key, value in _OAUTH_ENVS.items():
            monkeypatch.setenv(key, value)
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        assert is_drive_configured() is False

    def test_클라이언트시크릿_없음__False_반환(self, monkeypatch):
        for key, value in _OAUTH_ENVS.items():
            monkeypatch.setenv(key, value)
        monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
        assert is_drive_configured() is False

    def test_리프레시토큰_없음__False_반환(self, monkeypatch):
        for key, value in _OAUTH_ENVS.items():
            monkeypatch.setenv(key, value)
        monkeypatch.delenv("GOOGLE_REFRESH_TOKEN", raising=False)
        assert is_drive_configured() is False

    def test_폴더ID_없음__False_반환(self, monkeypatch):
        for key, value in _OAUTH_ENVS.items():
            monkeypatch.setenv(key, value)
        monkeypatch.delenv("GOOGLE_DRIVE_FOLDER_ID", raising=False)
        assert is_drive_configured() is False

    def test_모두_없음__False_반환(self, monkeypatch):
        for key in _OAUTH_ENVS:
            monkeypatch.delenv(key, raising=False)
        assert is_drive_configured() is False

    def test_빈_문자열__False_반환(self, monkeypatch):
        for key in _OAUTH_ENVS:
            monkeypatch.setenv(key, "")
        assert is_drive_configured() is False


class TestUploadToDrive:
    def test_환경변수_미설정__실패_반환(self, monkeypatch):
        for key in _OAUTH_ENVS:
            monkeypatch.delenv(key, raising=False)
        result = upload_to_drive(b"fake xlsx bytes")
        assert result["success"] is False
        assert "설정되지 않았습니다" in result["message"]

    @patch("googleapiclient.discovery.build")
    @patch("google.oauth2.credentials.Credentials")
    def test_업로드_성공__fileId_webViewLink_반환(self, mock_creds_cls, mock_build, monkeypatch):
        for key, value in _OAUTH_ENVS.items():
            monkeypatch.setenv(key, value)

        mock_creds = MagicMock()
        mock_creds_cls.return_value = mock_creds

        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_create = mock_service.files.return_value.create.return_value
        mock_create.execute.return_value = {
            "id": "file_abc",
            "webViewLink": "https://drive.google.com/file/d/file_abc/view",
        }

        result = upload_to_drive(b"fake xlsx bytes", filename="test.xlsx")

        assert result["success"] is True
        assert result["fileId"] == "file_abc"
        assert "drive.google.com" in result["webViewLink"]

        mock_creds_cls.assert_called_once_with(
            token=None,
            refresh_token="test-refresh-token",
            token_uri="https://oauth2.googleapis.com/token",
            client_id="test-client-id",
            client_secret="test-client-secret",
        )
        mock_service.files.return_value.create.assert_called_once()
        call_kwargs = mock_service.files.return_value.create.call_args
        assert call_kwargs.kwargs.get("supportsAllDrives") is True

    @patch("googleapiclient.discovery.build")
    @patch("google.oauth2.credentials.Credentials")
    def test_업로드_API_예외__실패_반환(self, mock_creds_cls, mock_build, monkeypatch):
        for key, value in _OAUTH_ENVS.items():
            monkeypatch.setenv(key, value)

        mock_creds = MagicMock()
        mock_creds_cls.return_value = mock_creds

        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.files.return_value.create.return_value.execute.side_effect = Exception("API 오류")

        result = upload_to_drive(b"fake xlsx bytes")
        assert result["success"] is False
        assert "업로드 실패" in result["message"]
