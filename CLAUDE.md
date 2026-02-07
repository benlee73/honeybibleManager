# CLAUDE.md

## 프로젝트 개요

카카오톡 대화 CSV를 업로드하면 멤버별 이모티콘/날짜를 분석하여 결과 CSV로 반환하는 웹 서버.

## 기술 스택

- Python 3.12+ / openpyxl (XLSX 생성)
- 의존성 관리: Poetry
- 테스트: pytest (dev 의존성)

## 프로젝트 구조

```
server.py              # 진입점. HTTPServer 실행 (--host, --port)
app/
  handler.py           # HoneyBibleHandler: HTTP 요청 처리 (GET 정적파일, POST /analyze), extract_multipart_field()
  analyzer.py          # analyze_chat(), build_output_csv(), build_preview_data(), build_output_xlsx(), extract_tracks(): CSV 분석/결과 생성/트랙 감지
  date_parser.py       # parse_dates(): 메시지에서 날짜 파싱 (범위~, 쉼표, M/D 형식)
  emoji.py             # extract_trailing_emoji(), normalize_emoji(): 이모티콘 추출/정규화
  logger.py            # setup_logging(), get_logger(): 콘솔+파일(server.log) 로깅 설정
tests/                 # 각 app 모듈에 대응하는 테스트 파일
public/                # 프론트엔드 정적 파일 (index.html, app.js, styles.css)
```

## 핵심 동작 흐름

1. 클라이언트가 CSV 파일과 `track_mode`(`single`/`dual`)를 `POST /analyze`로 업로드
2. `handler.py`가 multipart 데이터에서 파일과 트랙 모드 추출
3. `analyzer.py`가 CSV를 파싱하고 사용자별 이모티콘 할당 및 날짜 수집 (투트랙 모드 시 구약/신약 분리)
4. `date_parser.py`와 `emoji.py`가 각각 날짜/이모티콘 추출 담당
5. 결과를 스타일 적용된 XLSX로 변환하고, JSON 응답(xlsx_base64 + preview 데이터)으로 반환

## 분석 규칙 요약

- 한 메시지에서 추출된 날짜가 14개(`MAX_DATES_PER_MESSAGE`)를 초과하면 공지성 메시지로 간주하여 스킵한다.

## 작업 규칙

- 기능을 추가하거나 수정할 때 관련 테스트 코드도 반드시 작성하거나 수정한다.
- 기능 추가/수정 후 모든 테스트(`poetry run python -m pytest tests/ -v`)가 통과하면 커밋한다.
- 테스트 코드, Git 커밋 메시지 등은 모두 한글로 작성한다.
- 프로젝트 구조, 모듈, 기술 스택 등이 변경되면 CLAUDE.md도 함께 업데이트한다.
