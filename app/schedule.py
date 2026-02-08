import datetime

# 성경일독 파트별 시작~종료
_BIBLE_RANGES = [
    (datetime.date(2026, 2, 2), datetime.date(2026, 5, 30)),
    (datetime.date(2026, 6, 8), datetime.date(2026, 9, 26)),
    (datetime.date(2026, 10, 5), datetime.date(2026, 12, 19)),
]

# 신약일독 파트별 시작~종료
_NT_RANGES = [
    (datetime.date(2026, 2, 2), datetime.date(2026, 5, 29)),
    (datetime.date(2026, 6, 8), datetime.date(2026, 9, 25)),
    (datetime.date(2026, 10, 5), datetime.date(2026, 12, 18)),
]


def _generate_dates(ranges):
    """범위 내 일요일 제외 날짜를 "M/D" 문자열 frozenset으로 반환"""
    dates = set()
    for start, end in ranges:
        current = start
        while current <= end:
            if current.weekday() != 6:  # 6 = 일요일
                dates.add(f"{current.month}/{current.day}")
            current += datetime.timedelta(days=1)
    return frozenset(dates)


BIBLE_DATES = _generate_dates(_BIBLE_RANGES)
NT_DATES = _generate_dates(_NT_RANGES)


def detect_schedule(rows):
    """CSV 메시지들에서 키워드 감지하여 진도표 선택.

    rows: [(user, message), ...]
    반환: frozenset | None
    """
    has_genesis = False
    has_exodus = False
    has_matthew = False
    has_mark = False

    for _, message in rows:
        if "창세기" in message:
            has_genesis = True
        if "출애굽기" in message:
            has_exodus = True
        if "마태복음" in message:
            has_matthew = True
        if "마가복음" in message:
            has_mark = True

    is_bible = has_genesis and has_exodus
    is_nt = has_matthew and has_mark

    if is_bible:
        return BIBLE_DATES
    if is_nt:
        return NT_DATES
    return None
