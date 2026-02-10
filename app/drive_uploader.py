import os
from datetime import datetime
from io import BytesIO

from app.logger import get_logger

logger = get_logger("drive_uploader")

_ENV_CLIENT_ID = "GOOGLE_CLIENT_ID"
_ENV_CLIENT_SECRET = "GOOGLE_CLIENT_SECRET"
_ENV_REFRESH_TOKEN = "GOOGLE_REFRESH_TOKEN"
_ENV_FOLDER_ID = "GOOGLE_DRIVE_FOLDER_ID"


def is_drive_configured():
    """Google Drive OAuth 환경변수가 모두 설정되어 있는지 확인."""
    return bool(
        os.environ.get(_ENV_CLIENT_ID)
        and os.environ.get(_ENV_CLIENT_SECRET)
        and os.environ.get(_ENV_REFRESH_TOKEN)
        and os.environ.get(_ENV_FOLDER_ID)
    )


def upload_to_drive(file_bytes, filename=None):
    """XLSX 파일을 Google Drive에 업로드하고 결과를 반환.

    Returns:
        dict: 성공 시 {"success": True, "fileId": "...", "webViewLink": "..."}
              실패 시 {"success": False, "message": "에러 메시지"}
    """
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseUpload
    except ImportError:
        logger.error("Google API 라이브러리가 설치되지 않았습니다.")
        return {"success": False, "message": "Google API 라이브러리가 설치되지 않았습니다."}

    client_id = os.environ.get(_ENV_CLIENT_ID)
    client_secret = os.environ.get(_ENV_CLIENT_SECRET)
    refresh_token = os.environ.get(_ENV_REFRESH_TOKEN)
    folder_id = os.environ.get(_ENV_FOLDER_ID)

    if not all([client_id, client_secret, refresh_token, folder_id]):
        return {"success": False, "message": "Google Drive가 설정되지 않았습니다."}

    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"honeybible-results-{timestamp}.xlsx"

    try:
        credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
        )
        service = build("drive", "v3", credentials=credentials)

        file_metadata = {
            "name": filename,
            "parents": [folder_id],
        }
        media = MediaIoBaseUpload(
            BytesIO(file_bytes),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            resumable=False,
        )
        result = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, webViewLink",
            supportsAllDrives=True,
        ).execute()

        file_id = result.get("id", "")
        web_view_link = result.get("webViewLink", "")
        logger.info("Drive 업로드 성공: fileId=%s", file_id)

        return {
            "success": True,
            "fileId": file_id,
            "webViewLink": web_view_link,
        }
    except Exception as exc:
        logger.error("Drive 업로드 실패: %s", exc)
        return {"success": False, "message": f"업로드 실패: {exc}"}
