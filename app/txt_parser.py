import re

from app.logger import get_logger

logger = get_logger("txt_parser")

# TXT 헤더 첫 줄: "XXX 님과 카카오톡 대화"
_ROOM_NAME_RE = re.compile(r"^(.+?)\s*님과 카카오톡 대화$")

# 저장 날짜 줄: "저장한 날짜 : 2026. 2. 9. 오전 10:50"
_SAVED_DATE_RE = re.compile(
    r"^저장한 날짜\s*:\s*(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.\s*(오전|오후)\s*(\d{1,2}):(\d{2})"
)

# 사용자 메시지: "2026. 2. 2. 오전 7:33, 유저이름 : 메시지"
_USER_MSG_RE = re.compile(
    r"^\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.\s*[오전후]+\s*\d{1,2}:\d{2},\s*(.+?)\s*:\s*(.*)"
)

# 시스템 메시지: "2026. 2. 1. 오후 8:26: 시스템텍스트" (쉼표 없이 콜론)
_SYSTEM_MSG_RE = re.compile(
    r"^\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.\s*[오전후]+\s*\d{1,2}:\d{2}:\s"
)

# 날짜 헤더: "2026년 2월 1일 일요일"
_DATE_HEADER_RE = re.compile(
    r"^\d{4}년\s*\d{1,2}월\s*\d{1,2}일\s*\S+요일$"
)

# 파일 헤더 또는 저장 날짜 줄
_FILE_HEADER_RE = re.compile(r"^(Talk_|저장한 날짜)")


def extract_chat_meta(text):
    """TXT 파일 헤더에서 방 이름과 저장 날짜를 추출한다.

    Returns:
        dict: {"room_name": str|None, "saved_date": str|None}
              saved_date 형식: "YYYY/MM/DD-HH:MM"
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    room_name = None
    saved_date = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if room_name is None:
            m = _ROOM_NAME_RE.match(stripped)
            if m:
                room_name = m.group(1).strip()
                continue

        if saved_date is None:
            m = _SAVED_DATE_RE.match(stripped)
            if m:
                year, month, day = m.group(1), m.group(2), m.group(3)
                ampm, hour, minute = m.group(4), int(m.group(5)), m.group(6)
                if ampm == "오후" and hour != 12:
                    hour += 12
                elif ampm == "오전" and hour == 12:
                    hour = 0
                saved_date = f"{year}/{int(month):02d}/{int(day):02d}-{hour:02d}:{minute}"
                continue

        # 방이름과 저장날짜를 모두 찾았으면 조기 종료
        if room_name is not None and saved_date is not None:
            break

    return {"room_name": room_name, "saved_date": saved_date}


def parse_txt(text):
    """카카오톡 모바일 TXT 내보내기를 파싱하여 (user, message) 튜플 리스트를 반환한다."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    rows = []
    current_user = None
    current_message = None
    skip_header = 0
    skip_date_header = 0
    skip_system = 0
    multiline_count = 0

    for line in lines:
        stripped = line.strip()

        if not stripped:
            continue

        if _FILE_HEADER_RE.match(stripped):
            skip_header += 1
            continue

        if _DATE_HEADER_RE.match(stripped):
            skip_date_header += 1
            continue

        user_match = _USER_MSG_RE.match(stripped)
        if user_match:
            if current_user is not None:
                rows.append((current_user, current_message))
            current_user = user_match.group(1).strip()
            current_message = user_match.group(2).strip()
            continue

        if _SYSTEM_MSG_RE.match(stripped):
            skip_system += 1
            if current_user is not None:
                rows.append((current_user, current_message))
                current_user = None
                current_message = None
            continue

        # 멀티라인 메시지: 타임스탬프 없는 줄은 이전 메시지에 연결
        if current_user is not None:
            current_message += "\n" + stripped
            multiline_count += 1

    if current_user is not None:
        rows.append((current_user, current_message))

    logger.info(
        "TXT 파싱: 전체 %d줄, 사용자 메시지 %d건 (파일헤더 %d, 날짜헤더 %d, "
        "시스템메시지 %d, 멀티라인연결 %d)",
        len(lines), len(rows), skip_header, skip_date_header,
        skip_system, multiline_count,
    )

    return rows
