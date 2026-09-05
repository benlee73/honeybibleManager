import datetime
import re

from app.logger import get_logger

logger = get_logger("schedule")

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


def _generate_dates_for_range(start, end, exclude_weekdays):
    dates = set()
    current = start
    while current <= end:
        if current.weekday() not in exclude_weekdays:
            dates.add(f"{current.month}/{current.day}")
        current += datetime.timedelta(days=1)
    return frozenset(dates)


def _generate_dates(ranges, exclude_weekdays=(6,)):
    dates = set()
    for start, end in ranges:
        dates |= _generate_dates_for_range(start, end, exclude_weekdays)
    return frozenset(dates)


# 파트별 진도표 (인덱스 0=PART1, 1=PART2, 2=PART3)
BIBLE_PART_DATES = tuple(
    _generate_dates_for_range(s, e, (6,)) for s, e in _BIBLE_RANGES
)
NT_PART_DATES = tuple(
    _generate_dates_for_range(s, e, (5, 6)) for s, e in _NT_RANGES
)

# 전체 합집합 (후방 호환)
BIBLE_DATES = _generate_dates(_BIBLE_RANGES, exclude_weekdays=(6,))
NT_DATES = _generate_dates(_NT_RANGES, exclude_weekdays=(5, 6))


# 파트별 책 키워드 (해당 파트에서 읽는 책 일부)
_BIBLE_PART_KEYWORDS = (
    # PART 1: 창세기 ~ 욥기
    ("창세기", "출애굽기", "레위기", "민수기", "신명기",
     "여호수아", "사사기", "룻기",
     "사무엘상", "사무엘하", "열왕기상", "열왕기하",
     "역대상", "역대하", "에스라", "느헤미야", "에스더", "욥기"),
    # PART 2: 시편 ~ 말라기
    ("시편", "잠언", "전도서", "아가",
     "이사야", "예레미야", "예레미야애가", "에스겔", "다니엘",
     "호세아", "요엘", "아모스", "오바댜", "요나", "미가",
     "나훔", "하박국", "스바냐", "학개", "스가랴", "말라기"),
    # PART 3: 마태복음 ~ 요한계시록
    ("마태복음", "마가복음", "누가복음", "요한복음",
     "사도행전", "로마서", "고린도전서", "고린도후서",
     "갈라디아서", "에베소서", "빌립보서", "골로새서",
     "데살로니가전서", "데살로니가후서", "디모데전서", "디모데후서",
     "디도서", "빌레몬서", "히브리서", "야고보서",
     "베드로전서", "베드로후서", "요한일서", "요한이서", "요한삼서",
     "유다서", "요한계시록"),
)

_NT_PART_KEYWORDS = (
    # PART 1: 마태복음 ~ 요한복음
    ("마태복음", "마가복음", "누가복음", "요한복음"),
    # PART 2: 사도행전 ~ 에베소서
    ("사도행전", "로마서", "고린도전서", "고린도후서",
     "갈라디아서", "에베소서"),
    # PART 3: 빌립보서 ~ 요한계시록
    ("빌립보서", "골로새서",
     "데살로니가전서", "데살로니가후서", "디모데전서", "디모데후서",
     "디도서", "빌레몬서", "히브리서", "야고보서",
     "베드로전서", "베드로후서", "요한일서", "요한이서", "요한삼서",
     "유다서", "요한계시록"),
)


def current_part(today=None):
    """오늘 날짜가 속한 파트(1/2/3)를 반환한다.

    - 파트 진행 기간 안이면 해당 파트
    - 파트 간 쉬는 기간이거나 전체 종료 후면 직전(가장 최근 시작한) 파트
    - 첫 파트 시작 전이면 PART 1
    """
    if today is None:
        today = datetime.date.today()
    result = 1
    for idx, (start, end) in enumerate(_BIBLE_RANGES):
        if today < start:
            break
        result = idx + 1
        if today <= end:
            break
    return result


def resolve_part(part=None, today=None):
    """요청된 파트를 1~3으로 확정한다. 미지정/비정상 값은 오늘 날짜 기준 파트."""
    try:
        value = int(part)
    except (TypeError, ValueError):
        return current_part(today)
    if 1 <= value <= len(_BIBLE_RANGES):
        return value
    return current_part(today)


_MD_PATTERN = re.compile(r"(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)")

_ALL_BOOK_KEYWORDS = frozenset(
    kw for kws in _BIBLE_PART_KEYWORDS + _NT_PART_KEYWORDS for kw in kws
)


def _is_schedule_period(month, day):
    """월/일이 어느 파트든 진행 기간에 속하면 True (연도 무시)."""
    for start, end in _BIBLE_RANGES:
        if (start.month, start.day) <= (month, day) <= (end.month, end.day):
            return True
    return False


def _has_schedule_evidence(rows):
    """꿀성경 인증방으로 볼 만한 흔적(진행 기간 날짜 또는 성경 권 이름)이 있는지."""
    for _, message in rows:
        if not message:
            continue
        for m in _MD_PATTERN.finditer(message):
            month = int(m.group(1))
            day = int(m.group(2))
            if 1 <= month <= 12 and 1 <= day <= 31 and _is_schedule_period(month, day):
                return True
        if any(kw in message for kw in _ALL_BOOK_KEYWORDS):
            return True
    return False


def detect_schedule(rows, part=None):
    """파트와 책 키워드로 적용할 진도표를 결정한다.

    파트는 메시지 내용이 아니라 요청값(없으면 오늘 날짜)으로 정한다.
    PART 1부터 이어온 방은 과거 파트 인증이 더 많아 메시지 기반 감지가
    직전 파트로 쏠리는 문제가 있었다.

    트랙(bible/nt)은 해당 파트의 책 키워드로 판별한다. PART 3는 성경일독·
    신약일독이 같은 책을 읽어 키워드만으로 구분되지 않으므로 bible이 기본이다.

    rows: [(user, message), ...]
    반환: frozenset | None (꿀성경 인증 흔적이 없으면 None → 필터 미적용)
    """
    if not _has_schedule_evidence(rows):
        logger.info("진도표 흔적 없음 — 진도표 미적용")
        return None
    part = resolve_part(part)

    bible_kw = _BIBLE_PART_KEYWORDS[part - 1]
    nt_kw = _NT_PART_KEYWORDS[part - 1]
    # bible 전용 키워드 = bible_kw - nt_kw, nt 전용 = nt_kw - bible_kw
    bible_only = tuple(set(bible_kw) - set(nt_kw))
    nt_only = tuple(set(nt_kw) - set(bible_kw))
    # 존재 여부가 아니라 등장 횟수로 비교한다. 방을 잘못 찾아 들어온 안내 한 건이
    # 트랙 전체를 뒤집는 사고가 실제로 있었다.
    bible_hits = 0
    nt_hits = 0
    for _, message in rows:
        if not message:
            continue
        if any(kw in message for kw in bible_only):
            bible_hits += 1
        if any(kw in message for kw in nt_only):
            nt_hits += 1

    # PART 3는 성경일독·신약일독이 같은 책을 읽어 전용 키워드가 겹치므로
    # 양쪽 다 0이 되는 경우가 많다 — 그때는 bible이 기본값이다.
    track = "nt" if nt_hits > bible_hits else "bible"

    logger.info(
        "진도표 감지 — PART %d, 트랙: %s (성경일독 키워드 %d건, 신약일독 키워드 %d건)",
        part, "성경일독" if track == "bible" else "신약일독", bible_hits, nt_hits,
    )

    if track == "bible":
        return BIBLE_PART_DATES[part - 1]
    return NT_PART_DATES[part - 1]


# 진도표 frozenset → 시작 (month, day) 매핑
def _build_start_map():
    m = {}
    for i, (s, _) in enumerate(_BIBLE_RANGES):
        m[BIBLE_PART_DATES[i]] = (s.month, s.day)
    for i, (s, _) in enumerate(_NT_RANGES):
        m[NT_PART_DATES[i]] = (s.month, s.day)
    m[BIBLE_DATES] = (_BIBLE_RANGES[0][0].month, _BIBLE_RANGES[0][0].day)
    m[NT_DATES] = (_NT_RANGES[0][0].month, _NT_RANGES[0][0].day)
    return m


_SCHEDULE_START_MAP = _build_start_map()


def get_schedule_start(schedule):
    """진도표 frozenset의 첫 인증 날짜를 (month, day)로 반환."""
    if schedule is None:
        return None
    return _SCHEDULE_START_MAP.get(schedule)


def get_part_schedule(track, part):
    """track('bible'|'nt') × part(1|2|3) 진도표 반환."""
    if part is None or not (1 <= part <= 3):
        return None
    if track == "bible":
        return BIBLE_PART_DATES[part - 1]
    if track == "nt":
        return NT_PART_DATES[part - 1]
    return None


def get_part_books(track, part):
    """track('bible'|'nt') × part(1|2|3)의 대략적인 성경 권 순서를 반환."""
    if part is None or not (1 <= part <= 3):
        return ()
    if track == "bible":
        return _BIBLE_PART_KEYWORDS[part - 1]
    if track == "nt":
        return _NT_PART_KEYWORDS[part - 1]
    return ()
