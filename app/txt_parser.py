import re

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


def parse_txt(text):
    """카카오톡 모바일 TXT 내보내기를 파싱하여 (user, message) 튜플 리스트를 반환한다."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    rows = []
    current_user = None
    current_message = None

    for line in lines:
        stripped = line.strip()

        if not stripped:
            continue

        if _FILE_HEADER_RE.match(stripped):
            continue

        if _DATE_HEADER_RE.match(stripped):
            continue

        user_match = _USER_MSG_RE.match(stripped)
        if user_match:
            if current_user is not None:
                rows.append((current_user, current_message))
            current_user = user_match.group(1).strip()
            current_message = user_match.group(2).strip()
            continue

        if _SYSTEM_MSG_RE.match(stripped):
            if current_user is not None:
                rows.append((current_user, current_message))
                current_user = None
                current_message = None
            continue

        # 멀티라인 메시지: 타임스탬프 없는 줄은 이전 메시지에 연결
        if current_user is not None:
            current_message += "\n" + stripped

    if current_user is not None:
        rows.append((current_user, current_message))

    return rows
