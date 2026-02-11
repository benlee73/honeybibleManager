# CLAUDE.md

## 프로젝트 개요

카카오톡 대화 파일(CSV/TXT/ZIP)을 업로드하면 멤버별 이모티콘/날짜를 분석하여 결과 XLSX 및 PNG 이미지로 반환하는 웹 서버. PC 카카오톡(CSV)과 모바일 카카오톡(TXT/ZIP) 내보내기를 모두 지원한다. "이미지로 보기" 기능으로 카카오톡 인앱 브라우저에서 결과를 사진으로 저장할 수 있다.

## 프로젝트 구조

```
server.py              # 진입점 (HTTPServer)
app/
  handler.py           # HTTP 요청 처리, 파일 형식 감지
  analyzer.py          # 채팅 분석, 결과 생성 (CSV/XLSX/preview)
  image_builder.py     # 결과 PNG 이미지 생성 (4종 테마)
  txt_parser.py        # 모바일 TXT 내보내기 파싱
  schedule.py          # 진도표 날짜 생성 및 선택
  date_parser.py       # 메시지 날짜 파싱
  emoji.py             # 이모티콘 추출/정규화
  drive_uploader.py    # Google Drive 업로드
  logger.py            # 로깅 설정
  fonts/               # 한글/이모지 폰트 번들
tests/                 # 테스트
scripts/
  get_google_token.py  # OAuth refresh token 발급
public/                # 프론트엔드 (index.html, app.js, styles.css)
```

## 핵심 동작 흐름

1. 클라이언트가 대화 파일(CSV/TXT/ZIP)과 `track_mode`(`single`/`dual`), `theme`(honey/bw/brew/neon)를 `POST /analyze`로 업로드
2. `handler.py`가 multipart 데이터에서 파일과 트랙 모드 추출, 파일 형식 감지(매직바이트/확장자)
3. 파일 형식에 따라 파싱: CSV → `parse_csv_rows()`, TXT → `parse_txt()`, ZIP → TXT 추출 후 `parse_txt()`
4. `analyzer.py`가 `(user, message)` 리스트를 분석하여 사용자별 이모티콘 할당 및 날짜 수집 (투트랙 모드 시 구약/신약 분리)
5. `date_parser.py`와 `emoji.py`가 각각 날짜/이모티콘 추출 담당
6. 결과를 스타일 적용된 XLSX와 PNG 이미지로 변환하고, JSON 응답(xlsx_base64 + image_base64 + preview 데이터)으로 반환
7. 프론트엔드에서 "이미지로 보기" 버튼 클릭 시 PNG 이미지를 `<img>` 태그로 표시 (모바일에서 길게 눌러 사진 저장 가능)
8. (선택) "구글 드라이브 저장" 버튼 클릭 시 `POST /upload-drive`로 XLSX base64를 전송하여 Google Drive에 업로드

## 분석 규칙 요약

- 한 메시지에서 추출된 날짜가 14개(`MAX_DATES_PER_MESSAGE`)를 초과하면 공지성 메시지로 간주하여 스킵한다.
- 진도표 기반 날짜 필터링: 일요일 및 파트 간 쉬는 기간의 날짜는 결과에서 제외한다.
  - 성경일독: 월~토 읽기 (일요일 쉼), 신약일독: 월~금 읽기 (토·일요일 쉼)
  - Single 모드: CSV 메시지에서 '창세기'+'출애굽기' → 성경일독, '마태복음'+'마가복음' → 신약일독 진도표 적용 (키워드 없으면 필터 미적용)
  - Dual 모드: 구약 → 성경일독, 신약 → 신약일독 진도표 자동 적용

## 환경변수 (Google Drive 업로드용, 선택)

- `GOOGLE_CLIENT_ID`: OAuth 2.0 클라이언트 ID
- `GOOGLE_CLIENT_SECRET`: OAuth 2.0 클라이언트 보안 비밀번호
- `GOOGLE_REFRESH_TOKEN`: OAuth 2.0 refresh token (`scripts/get_google_token.py`로 발급)
- `GOOGLE_DRIVE_FOLDER_ID`: 업로드 대상 폴더 ID (URL에서 추출)

네 환경변수가 모두 설정되어 있어야 Drive 업로드 기능이 활성화된다. 미설정 시 버튼 클릭 시 안내 메시지를 표시한다.

## 작업 규칙

- 기능을 추가하거나 수정할 때 관련 테스트 코드도 반드시 작성하거나 수정한다.
- 기능 추가/수정 후 모든 테스트(`poetry run python -m pytest tests/ -v`)가 통과하면 커밋한다.
- 테스트 코드, Git 커밋 메시지 등은 모두 한글로 작성한다.
- 복잡한 작업은 항상 Plan Mode로 시작한다.
- 병렬 작업을 최대한 활용한다.
- 프로젝트 구조나 핵심 규칙이 변경되면 CLAUDE.md도 함께 업데이트한다.
