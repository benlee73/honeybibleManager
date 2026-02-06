# Honey Bible Server

카카오톡 대화 CSV를 업로드하면 프론트 화면과 분석 API를 함께 제공하는
단일 서버입니다. 결과는 멤버별 이모티콘/날짜를 정리한 CSV로 내려받습니다.

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

## 엔드포인트
- POST /analyze (multipart/form-data)
  - 필드 이름: file
  - 응답: CSV 파일 다운로드 (UTF-8 with BOM)

## 정적 파일
- 프론트 파일은 `public/`에 위치합니다.
- `GET /`는 `public/index.html`을 제공합니다.

## 분석 규칙 요약
- 전체 CSV를 먼저 훑어 사람별 “지정 이모티콘”을 결정합니다.
- 해당 이모티콘이 포함된 메시지만 대상으로 날짜를 수집합니다.
- 날짜 파싱은 공백을 제거하고 범위/콤마 목록을 허용합니다.
  - 예: `2/4~5`, `2/4,5`, `2/4, 2/5`
- 날짜는 `M/D` 형식으로 정규화하고 월/일 기준으로 정렬합니다.
- 결과 CSV 컬럼: `이름`, `이모티콘`, `day1...N`

## 배포 (방법 A: Render)
1) 이 저장소를 GitHub에 업로드합니다.
2) Render에서 **New Web Service**를 생성합니다.
3) GitHub 저장소를 연결합니다.
4) **Root Directory**는 저장소 루트로 설정합니다.
5) **Start Command**를 아래처럼 입력합니다.

```bash
python3 server.py --host 0.0.0.0 --port $PORT
```

배포가 완료되면 제공된 URL로 외부에서 접속할 수 있습니다.

## TODO
- ~~테스트 코드 추가~~
- ~~프로젝트 구조 리팩토링~~
- 로깅 추가
- 결과 포맷 변경
  - as-is: 컬럼에 day1, day2 ...
  - to-be: 컬럼에 2/2, 2/3 ...
- 투트랙도 볼 수 있도록
- 중복 허용
- 결과 csv 말고 엑셀같은 걸로 해서 더 이쁘게 보여주기