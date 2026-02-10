"""Google OAuth 2.0 Refresh Token 발급 스크립트.

1회성으로 실행하여 refresh token을 발급받는다.
브라우저에서 Google 로그인 → 권한 허용 후 터미널에 refresh token이 출력된다.

사용법:
    poetry run python scripts/get_google_token.py

발급된 refresh token을 .env 파일의 GOOGLE_REFRESH_TOKEN에 설정한다.
"""

import json
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def main():
    print("=" * 60)
    print("Google OAuth 2.0 Refresh Token 발급")
    print("=" * 60)

    client_id = input("\nGoogle Client ID를 입력하세요: ").strip()
    client_secret = input("Google Client Secret을 입력하세요: ").strip()

    if not client_id or not client_secret:
        print("\n[오류] Client ID와 Client Secret을 모두 입력해야 합니다.")
        sys.exit(1)

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
    credentials = flow.run_local_server(port=0, prompt="consent", access_type="offline")

    print("\n" + "=" * 60)
    print("Refresh Token 발급 완료!")
    print("=" * 60)
    print(f"\nREFRESH_TOKEN:\n{credentials.refresh_token}")
    print("\n.env 파일에 다음과 같이 설정하세요:")
    print(f"GOOGLE_CLIENT_ID={client_id}")
    print(f"GOOGLE_CLIENT_SECRET={client_secret}")
    print(f"GOOGLE_REFRESH_TOKEN={credentials.refresh_token}")
    print()


if __name__ == "__main__":
    main()
