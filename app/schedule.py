import datetime

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


def _date_in_part(month, day, ranges_index):
    """월/일이 파트 인덱스의 범위에 포함되면 True (연도는 무시)."""
    start, end = _BIBLE_RANGES[ranges_index]
    target = (start.year, month, day)
    s = (start.year, start.month, start.day)
    # NT 종료가 더 이르므로 BIBLE 범위(더 넓음)를 사용해서 파트 매칭
    e = (end.year, end.month, end.day)
    return s <= target <= e


def detect_part(rows):
    """메시지 timestamps의 월/일 분포로 파트(1/2/3)를 결정한다.

    - rows의 user 메시지 본문에는 "M/D" 인증 패턴이 들어있으므로 그것으로는
      판단하기 어렵다. 대신 시스템 메시지에 포함된 안내 날짜("🗓️ 3/2") 등
      모든 텍스트의 M/D 등장 분포를 카운트한다.
    - 가장 많은 표를 받은 파트를 반환. 동률이면 더 늦은 파트.
    - 매칭 표가 0이면 None.
    """
    import re
    pattern = re.compile(r"(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)")
    counts = [0, 0, 0]
    for _, message in rows:
        if not message:
            continue
        for m in pattern.finditer(message):
            try:
                mo = int(m.group(1))
                da = int(m.group(2))
            except ValueError:
                continue
            if not (1 <= mo <= 12 and 1 <= da <= 31):
                continue
            for idx in range(3):
                if _date_in_part(mo, da, idx):
                    counts[idx] += 1
                    break
    logger.info("파트 감지 표 — P1: %d, P2: %d, P3: %d", *counts)
    if max(counts) == 0:
        return None
    # 최다 득표, 동률이면 더 늦은 파트
    best = 0
    for i in range(3):
        if counts[i] >= counts[best]:
            best = i
    return best + 1


def _detect_part_by_keywords(rows):
    """책 키워드로만 파트를 추정한다 (날짜 분포가 없을 때 fallback).

    각 파트의 모든 트랙 키워드 매칭 수를 세고, 가장 많은 파트를 반환.
    """
    counts = [0, 0, 0]
    for part_idx in range(3):
        kws = set(_BIBLE_PART_KEYWORDS[part_idx]) | set(_NT_PART_KEYWORDS[part_idx])
        for _, message in rows:
            if not message:
                continue
            for kw in kws:
                if kw in message:
                    counts[part_idx] += 1
                    break
    if max(counts) == 0:
        return None
    # 키워드 동률 시 가장 이른 파트 선호 (P3는 P1·P2 책 다 포함하므로 늘 동률 위험)
    best = 0
    for i in range(1, 3):
        if counts[i] > counts[best]:
            best = i
    return best + 1


def detect_schedule(rows):
    """메시지 날짜+책 키워드로 파트와 트랙(bible/nt)을 결정한다.

    1) detect_part: 메시지 내 M/D 분포로 파트 결정 (가장 안정적)
    2) fallback: 날짜 분포 0이면 책 키워드로 파트 추정
    3) 트랙: 파트별 책 키워드로 bible/nt 결정.
       PART 3는 성경일독·신약일독 책이 동일하여 키워드만으로 구분 불가 →
       날짜가 P3에 매칭되면 기본 bible, 신약 전용 키워드만 보이면 nt.

    rows: [(user, message), ...]
    반환: frozenset | None
    """
    part = detect_part(rows)
    if part is None:
        part = _detect_part_by_keywords(rows)
    if part is None:
        logger.info("파트 미감지 — 진도표 미적용")
        return None

    bible_kw = _BIBLE_PART_KEYWORDS[part - 1]
    nt_kw = _NT_PART_KEYWORDS[part - 1]
    # bible 전용 키워드 = bible_kw - nt_kw, nt 전용 = nt_kw - bible_kw
    bible_only = tuple(set(bible_kw) - set(nt_kw))
    nt_only = tuple(set(nt_kw) - set(bible_kw))
    has_bible_only = False
    has_nt_only = False
    has_any_bible = False
    has_any_nt = False
    for _, message in rows:
        if not message:
            continue
        if not has_bible_only and any(kw in message for kw in bible_only):
            has_bible_only = True
        if not has_nt_only and any(kw in message for kw in nt_only):
            has_nt_only = True
        if not has_any_bible and any(kw in message for kw in bible_kw):
            has_any_bible = True
        if not has_any_nt and any(kw in message for kw in nt_kw):
            has_any_nt = True
        if has_bible_only and has_nt_only and has_any_bible and has_any_nt:
            break

    # P1/P2: 전용 키워드로 명확히 구분 가능
    # P3: 두 트랙이 같은 책을 읽으므로 신약 전용 키워드만 매칭되면 nt, 아니면 bible
    if part == 3:
        # P3에서 nt 전용 키워드(빌립보서 이후)가 보이고 bible 전용은 없으면 nt
        # 그렇지 않으면 bible 기본
        track = "nt" if has_nt_only and not has_bible_only else "bible"
    elif has_bible_only and not has_nt_only:
        track = "bible"
    elif has_nt_only and not has_bible_only:
        track = "nt"
    elif has_any_bible:
        track = "bible"
    elif has_any_nt:
        track = "nt"
    else:
        track = "bible"

    logger.info(
        "진도표 감지 — PART %d, 트랙: %s",
        part, "성경일독" if track == "bible" else "신약일독",
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
