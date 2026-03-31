# Honey Bible Server

카카오톡 대화 파일(CSV/TXT/ZIP)을 업로드하면 멤버별 이모티콘/날짜를 분석하여
스타일 적용된 XLSX와 PNG 이미지로 반환하는 웹 서버입니다.
PC 카카오톡(CSV)과 모바일 카카오톡(TXT/ZIP) 내보내기를 모두 지원하며,
분석 결과를 Google Drive에 저장하고 여러 방의 결과를 통합할 수 있습니다.

## 꿀성경이란?

꿀성경은 매일 성경을 읽고 카카오톡 단톡방에서 인증하는 성경통독 프로그램입니다.

### 운영 방식

2026 꿀성경은 1년을 PART 1 · PART 2 · PART 3로 나누어 진행됩니다.

**2가지 트랙:**
- **Track 1. 성경일독**: 구약 → 신약 순으로 성경 전체를 1년 동안 통독
- **Track 2. 신약일독**: 신약만으로 1년 통독

**3개의 카톡방:**
- 성경일독 방 (Track 1만)
- 신약일독 방 (Track 2만)
- 투트랙 방 (Track 1 + Track 2 동시 진행)

### 인증 방법

매일 읽은 후 날짜 + 이모티콘으로 인증합니다. 이모티콘은 타인과 중복되지 않게 지정합니다.

**일반 방 (성경일독/신약일독):**
- 예시: `2/12🐷`

**투트랙 방:**
- 구약만 읽은 경우: `2/2 구약 🐷`
- 신약만 읽은 경우: `2/2 신약 🐷`
- 둘 다 읽은 경우: `2/2 구약 신약 🐷`

## 요구사항
- Python 3.12+
- Poetry

## 로컬 실행

```bash
poetry install
poetry run python server.py --port 8000
```

브라우저에서 `http://localhost:8000`을 열면 됩니다.

## 테스트

```bash
poetry run python -m pytest tests/ -v
```

## 주요 기능

### 개별 분석

카카오톡 대화 파일을 업로드하면 멤버별 인증 현황을 분석합니다.

- **파일 형식**: PC 카카오톡 CSV, 모바일 카카오톡 TXT/ZIP
- **트랙 모드**: 싱글(single) / 투트랙(dual)
- **테마**: honey, bw, brew, neon (4종)
- **출력**: 스타일 적용 XLSX + 테마별 PNG 이미지
- **이미지로 보기**: 카카오톡 인앱 브라우저에서 결과를 사진으로 저장 가능

### Google Drive 연동

분석 결과 XLSX를 Google Drive에 저장합니다. 통합 기능을 사용하려면 각 방의 결과가 Drive에 업로드되어 있어야 합니다.

### 통합 진도표

여러 카톡방의 분석 결과를 Drive에서 가져와 하나의 통합 진도표로 병합합니다. 교육국 멤버 분류(`education_config.json`)를 기반으로 성경일독/신약일독 시트를 자동 분배합니다.

## 엔드포인트

### `POST /analyze`
- **Content-Type**: `multipart/form-data`
- **필드**: `file` (CSV/TXT/ZIP 파일), `theme` (`"honey"` | `"bw"` | `"brew"` | `"neon"`, 기본값 `"honey"`)
- **응답**: JSON (`xlsx_base64`, `image_base64`, `filename`, `drive_filename`, `preview`, `track_mode`)

### `POST /upload-drive`
- 분석 결과 XLSX를 Google Drive 폴더에 업로드
- **필드**: `xlsx_base64`, `filename`

### `POST /merge`
- Drive에 업로드된 방별 최신 XLSX를 병합하여 통합 진도표 생성
- **응답**: JSON (`xlsx_base64`, `image_base64`, `filename`, `preview`)

### `GET /health`
- 서버 상태 확인

## 정적 파일
- 프론트 파일은 `public/`에 위치합니다.
- `GET /`는 `public/index.html`을 제공합니다.

## 분석 규칙 요약
- 전체 대화를 먼저 훑어 사람별 "지정 이모티콘"을 결정합니다.
- 해당 이모티콘이 포함된 메시지만 대상으로 날짜를 수집합니다.
- 같은 사용자의 연속 메시지에서 이모지가 생략되어도 날짜를 카운트합니다.
- 멀티라인 메시지는 줄별로 분리하여 처리하며, 이모지가 없는 줄에는 전체 이모지를 자동 적용합니다.
- 날짜 파싱은 공백을 제거하고 범위/콤마 목록을 허용합니다.
  - 예: `2/4~5`, `2/4,5`, `2/4, 2/5`
- 한 메시지에서 추출된 날짜가 30개를 초과하면 공지성 메시지로 간주하여 스킵합니다.
- 진도표 기반 날짜 필터링: 일요일 및 파트 간 쉬는 기간의 날짜는 결과에서 제외합니다.
  - 성경일독: 월~토 (일요일 쉼), 신약일독: 월~금 (토·일요일 쉼)
- 날짜는 `M/D` 형식으로 정규화하고 월/일 기준으로 정렬합니다.
- 이름 정규화: 접미사 '형' 제거, 별칭 매핑 지원
- 결과 XLSX 컬럼: `이름`, `이모티콘`, 전체 날짜 컬럼 (해당 날짜 인증 시 `O` 표시)
- **투트랙 모드**: 메시지에 "구약"/"신약" 키워드가 포함된 경우 트랙별로 날짜를 분리 수집
  - 결과 XLSX에 `트랙` 컬럼이 추가되며, 구약 블록 → 신약 블록 순으로 출력
  - 해당 트랙에 날짜가 없는 사용자는 그 블록에서 생략

## 환경변수 (Google Drive 연동)

네 환경변수가 모두 설정되어 있어야 Drive 업로드/통합 기능이 활성화됩니다.

- `GOOGLE_CLIENT_ID`: OAuth 2.0 클라이언트 ID
- `GOOGLE_CLIENT_SECRET`: OAuth 2.0 클라이언트 보안 비밀번호
- `GOOGLE_REFRESH_TOKEN`: OAuth 2.0 refresh token (`scripts/get_google_token.py`로 발급)
- `GOOGLE_DRIVE_FOLDER_ID`: 업로드 대상 폴더 ID

## 배포 (Render)
1) 이 저장소를 GitHub에 업로드합니다.
2) Render에서 **New Web Service**를 생성합니다.
3) GitHub 저장소를 연결합니다.
4) **Root Directory**는 저장소 루트로 설정합니다.
5) **Start Command**를 아래처럼 입력합니다.

```bash
python3 server.py --host 0.0.0.0 --port $PORT
```

배포가 완료되면 제공된 URL로 외부에서 접속할 수 있습니다.
