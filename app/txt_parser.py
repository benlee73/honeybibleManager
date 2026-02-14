import re

from app.logger import get_logger

logger = get_logger("txt_parser")

# ── 한국어 정규식 ──

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

# ── 갤럭시(Android) 정규식 ──

# 갤럭시 방이름: "방이름 16 카카오톡 대화" (님과 없음)
_GALAXY_ROOM_NAME_RE = re.compile(r"^(.+)\s+카카오톡 대화$")

# 갤럭시 저장 날짜: "저장한 날짜 : 2026년 2월 9일 오후 6:35"
_GALAXY_SAVED_DATE_RE = re.compile(
    r"^저장한 날짜\s*:\s*(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일\s*(오전|오후)\s*(\d{1,2}):(\d{2})"
)

# 갤럭시 날짜 헤더: "2026년 2월 1일 오후 8:24" (요일 없이 시간으로 끝남)
_GALAXY_DATE_HEADER_RE = re.compile(
    r"^\d{4}년\s*\d{1,2}월\s*\d{1,2}일\s*[오전후]+\s*\d{1,2}:\d{2}$"
)

# 갤럭시 사용자 메시지: "2026년 2월 2일 오전 7:52, 김태환 : 메시지"
_GALAXY_USER_MSG_RE = re.compile(
    r"^\d{4}년\s*\d{1,2}월\s*\d{1,2}일\s*[오전후]+\s*\d{1,2}:\d{2},\s*(.+?)\s*:\s*(.*)"
)

# 갤럭시 시스템 메시지: "2026년 2월 1일 오후 8:24, 김태환님이 ...을 초대했습니다."
# (타임스탬프+쉼표 뒤에 ` : ` 가 없는 라인 = USER_MSG 미매치 후 이 패턴으로 캐치)
_GALAXY_SYSTEM_MSG_RE = re.compile(
    r"^\d{4}년\s*\d{1,2}월\s*\d{1,2}일\s*[오전후]+\s*\d{1,2}:\d{2},\s"
)

# ── 영문 정규식 ──

_EN_MONTHS = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"

_EN_MONTH_MAP = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}

# Date Saved : Feb 13, 2026 at 18:42
_EN_SAVED_DATE_RE = re.compile(
    rf"^Date Saved\s*:\s*({_EN_MONTHS})\s+(\d{{1,2}}),\s*(\d{{4}})\s+at\s+(\d{{1,2}}):(\d{{2}})"
)

# Sunday, February 1, 2026
_EN_DATE_HEADER_RE = re.compile(
    r"^(?:Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday),\s+"
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+"
    r"\d{1,2},\s*\d{4}$"
)

# Feb 1, 2026 at 20:35, 김예슬 : 메시지
_EN_USER_MSG_RE = re.compile(
    rf"^{_EN_MONTHS}\s+\d{{1,2}},\s*\d{{4}}\s+at\s+\d{{1,2}}:\d{{2}},\s*(.+?)\s*:\s*(.*)"
)

# Feb 1, 2026 at 20:29: 시스템텍스트 (쉼표 없이 콜론)
_EN_SYSTEM_MSG_RE = re.compile(
    rf"^{_EN_MONTHS}\s+\d{{1,2}},\s*\d{{4}}\s+at\s+\d{{1,2}}:\d{{2}}:\s"
)

# ── 공용 ──

# 파일 헤더 또는 저장 날짜 줄
_FILE_HEADER_RE = re.compile(r"^(Talk_|저장한 날짜|Date Saved)")


def _detect_language(lines):
    """앞쪽 10줄을 확인하여 'en', 'ko', 'ko_ymd' 중 하나를 반환한다."""
    for line in lines[:10]:
        stripped = line.strip()
        if stripped.startswith("Date Saved"):
            return "en"
        if stripped.startswith("저장한 날짜"):
            if "년" in stripped:
                return "ko_ymd"
            return "ko"
    return "ko"


def extract_chat_meta(text):
    """TXT 파일 헤더에서 방 이름과 저장 날짜를 추출한다.

    Returns:
        dict: {"room_name": str|None, "saved_date": str|None}
              saved_date 형식: "YYYY/MM/DD-HH:MM"
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    lang = _detect_language(lines)
    room_name = None
    saved_date = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # 방이름: 한국어 형식에만 존재 (영문 TXT에는 방이름 헤더 없음)
        if room_name is None and lang in ("ko", "ko_ymd"):
            room_re = _GALAXY_ROOM_NAME_RE if lang == "ko_ymd" else _ROOM_NAME_RE
            m = room_re.match(stripped)
            if m:
                room_name = m.group(1).strip()
                continue

        if saved_date is None:
            if lang == "en":
                m = _EN_SAVED_DATE_RE.match(stripped)
                if m:
                    month_name, day, year = m.group(1), m.group(2), m.group(3)
                    hour, minute = int(m.group(4)), m.group(5)
                    month = _EN_MONTH_MAP[month_name]
                    saved_date = f"{year}/{month:02d}/{int(day):02d}-{hour:02d}:{minute}"
                    continue
            else:
                saved_re = _GALAXY_SAVED_DATE_RE if lang == "ko_ymd" else _SAVED_DATE_RE
                m = saved_re.match(stripped)
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
    lang = _detect_language(lines)

    if lang == "en":
        date_header_re = _EN_DATE_HEADER_RE
        user_msg_re = _EN_USER_MSG_RE
        system_msg_re = _EN_SYSTEM_MSG_RE
    elif lang == "ko_ymd":
        date_header_re = _GALAXY_DATE_HEADER_RE
        user_msg_re = _GALAXY_USER_MSG_RE
        system_msg_re = _GALAXY_SYSTEM_MSG_RE
    else:
        date_header_re = _DATE_HEADER_RE
        user_msg_re = _USER_MSG_RE
        system_msg_re = _SYSTEM_MSG_RE

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

        if date_header_re.match(stripped):
            skip_date_header += 1
            continue

        user_match = user_msg_re.match(stripped)
        if user_match:
            if current_user is not None:
                rows.append((current_user, current_message))
            current_user = user_match.group(1).strip()
            current_message = user_match.group(2).strip()
            continue

        if system_msg_re.match(stripped):
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
        "TXT 파싱 (%s): 전체 %d줄, 사용자 메시지 %d건 (파일헤더 %d, 날짜헤더 %d, "
        "시스템메시지 %d, 멀티라인연결 %d)",
        lang, len(lines), len(rows), skip_header, skip_date_header,
        skip_system, multiline_count,
    )

    return rows
