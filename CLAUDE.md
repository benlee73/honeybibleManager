# CLAUDE.md

## 프로젝트 개요

카카오톡 대화 파일(CSV/TXT/ZIP)을 업로드하면 멤버별 이모티콘/날짜를 분석하여 결과 XLSX로 반환하는 웹 서버. PC 카카오톡(CSV)과 모바일 카카오톡(TXT/ZIP) 내보내기를 모두 지원한다.

## 기술 스택

- Python 3.12+ / openpyxl (XLSX 생성)
- 의존성 관리: Poetry
- 테스트: pytest (dev 의존성)

## 프로젝트 구조

```
server.py              # 진입점. HTTPServer 실행 (--host, --port)
app/
  handler.py           # HoneyBibleHandler: HTTP 요청 처리 (GET 정적파일, POST /analyze), 파일 형식 감지(CSV/TXT/ZIP)
  analyzer.py          # analyze_chat(), parse_csv_rows(), build_output_csv(), build_preview_data(), build_output_xlsx(), extract_tracks(): 분석/결과 생성/트랙 감지
  txt_parser.py        # parse_txt(): 카카오톡 모바일 TXT 내보내기 파싱 (멀티라인, 시스템 메시지 스킵)
  schedule.py          # BIBLE_DATES, NT_DATES, detect_schedule(): 진도표 날짜 생성 및 키워드 기반 진도표 선택
  date_parser.py       # parse_dates(): 메시지에서 날짜 파싱 (범위~, 쉼표, M/D 형식)
  emoji.py             # extract_trailing_emoji(), normalize_emoji(): 이모티콘 추출/정규화
  logger.py            # setup_logging(), get_logger(): 콘솔+파일(server.log) 로깅 설정
tests/                 # 각 app 모듈에 대응하는 테스트 파일
public/                # 프론트엔드 정적 파일 (index.html, app.js, styles.css)
```

## 핵심 동작 흐름

1. 클라이언트가 대화 파일(CSV/TXT/ZIP)과 `track_mode`(`single`/`dual`)를 `POST /analyze`로 업로드
2. `handler.py`가 multipart 데이터에서 파일과 트랙 모드 추출, 파일 형식 감지(매직바이트/확장자)
3. 파일 형식에 따라 파싱: CSV → `parse_csv_rows()`, TXT → `parse_txt()`, ZIP → TXT 추출 후 `parse_txt()`
4. `analyzer.py`가 `(user, message)` 리스트를 분석하여 사용자별 이모티콘 할당 및 날짜 수집 (투트랙 모드 시 구약/신약 분리)
5. `date_parser.py`와 `emoji.py`가 각각 날짜/이모티콘 추출 담당
6. 결과를 스타일 적용된 XLSX로 변환하고, JSON 응답(xlsx_base64 + preview 데이터)으로 반환

## 분석 규칙 요약

- 한 메시지에서 추출된 날짜가 14개(`MAX_DATES_PER_MESSAGE`)를 초과하면 공지성 메시지로 간주하여 스킵한다.
- 진도표 기반 날짜 필터링: 일요일 및 파트 간 쉬는 기간의 날짜는 결과에서 제외한다.
  - 성경일독: 월~토 읽기 (일요일 쉼), 신약일독: 월~금 읽기 (토·일요일 쉼)
  - Single 모드: CSV 메시지에서 '창세기'+'출애굽기' → 성경일독, '마태복음'+'마가복음' → 신약일독 진도표 적용 (키워드 없으면 필터 미적용)
  - Dual 모드: 구약 → 성경일독, 신약 → 신약일독 진도표 자동 적용

## 작업 규칙

- 기능을 추가하거나 수정할 때 관련 테스트 코드도 반드시 작성하거나 수정한다.
- 기능 추가/수정 후 모든 테스트(`poetry run python -m pytest tests/ -v`)가 통과하면 커밋한다.
- 테스트 코드, Git 커밋 메시지 등은 모두 한글로 작성한다.
- 프로젝트 구조, 모듈, 기술 스택 등이 변경되면 CLAUDE.md도 함께 업데이트한다.
