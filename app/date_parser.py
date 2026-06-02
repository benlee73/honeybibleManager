import re

DATE_TIME_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}")
DATE_PATTERN = re.compile(r"(?<!\d)(\d{1,2})\s*/\s*(\d{1,2})(?!\d)")
DATE_TOKEN_PATTERN = re.compile(r"(\d{1,2})/(\d{1,2})")
DAY_ONLY_PATTERN = re.compile(r"(\d{1,2})")
_CONCAT_DAY_PATTERN = re.compile(r"(?<!\d)(\d{1,2})/(\d{2,4})(?!\d)")

MONTH_DAYS = {
    1: 31,
    2: 28,
    3: 31,
    4: 30,
    5: 31,
    6: 30,
    7: 31,
    8: 31,
    9: 30,
    10: 31,
    11: 30,
    12: 31,
}


def normalize_date(match):
    try:
        month = int(match.group(1))
        day = int(match.group(2))
    except (TypeError, ValueError):
        return None
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    return f"{month}/{day}"


def is_valid_date(month, day):
    if not (1 <= month <= 12):
        return False
    if not (1 <= day <= 31):
        return False
    max_day = MONTH_DAYS.get(month, 31)
    return day <= max_day


def parse_date_or_day(text, index, current_month):
    match = DATE_TOKEN_PATTERN.match(text, index)
    if match:
        month = int(match.group(1))
        day = int(match.group(2))
        if not is_valid_date(month, day):
            return None
        return month, day, match.end()

    match = DAY_ONLY_PATTERN.match(text, index)
    if match:
        day = int(match.group(1))
        if not is_valid_date(current_month, day):
            return None
        return current_month, day, match.end()
    return None


def expand_range(start_month, start_day, end_month, end_day):
    if (end_month, end_day) < (start_month, start_day):
        return []

    results = []
    month = start_month
    day = start_day
    while (month, day) < (end_month, end_day):
        day += 1
        if day > MONTH_DAYS.get(month, 31):
            month += 1
            day = 1
            if month > 12:
                break
        results.append(f"{month}/{day}")
        if (month, day) == (end_month, end_day):
            break
    return results


def _split_concat_days(text):
    """'3/45' → '3/4,5', '3/910' → '3/9,10' 등 연결된 날짜를 분리한다.

    day 부분이 2~4자리이고 유효한 날짜가 아닐 때, 두 날짜로 분할을 시도한다.
    """
    def _replacer(match):
        month_str = match.group(1)
        day_str = match.group(2)
        month = int(month_str)
        day = int(day_str)
        if is_valid_date(month, day):
            return match.group(0)
        for i in range(1, len(day_str)):
            d1 = int(day_str[:i])
            d2_str = day_str[i:]
            d2 = int(d2_str)
            if d2 > 0 and is_valid_date(month, d1) and is_valid_date(month, d2):
                return f"{month_str}/{day_str[:i]},{d2_str}"
        return match.group(0)

    return _CONCAT_DAY_PATTERN.sub(_replacer, text)


def _clean_message(text):
    cleaned = _split_concat_days(text)
    cleaned = re.sub(r"(\d)\s+(\d)", r"\1,\2", cleaned)
    return re.sub(r"\s+", "", cleaned)


def _leading_tilde_end(cleaned):
    if not cleaned.startswith("~"):
        return None
    index = 0
    while index < len(cleaned) and cleaned[index] == "~":
        index += 1
    return index


def has_leading_tilde_catchup(message):
    if not message:
        return False
    cleaned = _clean_message(message)
    index = _leading_tilde_end(cleaned)
    if index is None:
        return False
    return DATE_TOKEN_PATTERN.match(cleaned, index) is not None


def _find_last_date_before(target, user_dates):
    """user_dates에서 target보다 앞선 가장 마지막 날짜를 찾는다."""
    best = None
    for d in user_dates:
        try:
            m, dy = d.split("/")
            t = (int(m), int(dy))
        except (ValueError, TypeError):
            continue
        if t < target and (best is None or t > best):
            best = t
    return best


MAX_TILDE_LOOKBACK = 30


def _go_back_days(target, days):
    """target에서 days일 전 날짜를 계산한다."""
    month, day = target
    for _ in range(days):
        day -= 1
        if day < 1:
            month -= 1
            if month < 1:
                return (1, 1)
            day = MONTH_DAYS.get(month, 31)
    return (month, day)


def _find_tilde_start(target, user_dates):
    """~target 확장 시작점: user_dates 내 가장 오래된 날짜(최대 30일 전)를 찾는다.

    빈 날짜를 모두 채우기 위해, target 직전 날짜가 아닌
    수집된 날짜 중 가장 오래된 것을 기준으로 시작한다.
    """
    cutoff = _go_back_days(target, MAX_TILDE_LOOKBACK)
    best = None
    for d in user_dates:
        try:
            m, dy = d.split("/")
            t = (int(m), int(dy))
        except (ValueError, TypeError):
            continue
        if cutoff <= t < target and (best is None or t < best):
            best = t
    return best


def parse_dates(message, last_date=None, user_dates=None, schedule_start=None):
    if not message:
        return []
    cleaned = _clean_message(message)
    results = []
    index = 0

    if cleaned[:1] in ("~", "-") and (
        last_date is not None or user_dates or schedule_start is not None
    ):
        index = _leading_tilde_end(cleaned) if cleaned.startswith("~") else 1
        match = DATE_TOKEN_PATTERN.search(cleaned, index)
        if match and match.start() == index:
            month = int(match.group(1))
            day = int(match.group(2))
            if is_valid_date(month, day):
                # user_dates가 있으면 빈 날짜를 모두 채우기 위해
                # 가장 오래된 수집 날짜(최대 30일 전)에서 시작
                start = None
                if user_dates:
                    start = _find_tilde_start((month, day), user_dates)
                if start is None:
                    start = last_date
                # 사용자의 첫 ~M/D 메시지: 진도표 시작일부터 채운다.
                # expand_range는 시작일을 제외하므로 하루 전을 시작점으로 넘긴다.
                if start is None and schedule_start is not None:
                    start = _go_back_days(schedule_start, 1)
                if start is not None:
                    results.extend(
                        expand_range(start[0], start[1], month, day)
                    )
                current_month = month
                current_day = day
                index = match.end()

                while index < len(cleaned) and cleaned[index] in ("~", "-", ","):
                    separator = cleaned[index]
                    index += 1
                    parsed = parse_date_or_day(cleaned, index, current_month)
                    if not parsed:
                        break
                    next_month, next_day, index = parsed
                    if separator in ("~", "-"):
                        results.extend(
                            expand_range(current_month, current_day, next_month, next_day)
                        )
                    else:
                        results.append(f"{next_month}/{next_day}")
                    current_month = next_month
                    current_day = next_day

                return results
        index = 0

    while index < len(cleaned):
        match = DATE_TOKEN_PATTERN.search(cleaned, index)
        if not match:
            break
        month = int(match.group(1))
        day = int(match.group(2))
        if not is_valid_date(month, day):
            index = match.end()
            continue
        results.append(f"{month}/{day}")
        current_month = month
        current_day = day
        index = match.end()

        while index < len(cleaned) and cleaned[index] in ("~", "-", ","):
            separator = cleaned[index]
            index += 1
            parsed = parse_date_or_day(cleaned, index, current_month)
            if not parsed:
                break
            next_month, next_day, index = parsed
            if separator in ("~", "-"):
                results.extend(
                    expand_range(current_month, current_day, next_month, next_day)
                )
            else:
                results.append(f"{next_month}/{next_day}")
            current_month = next_month
            current_day = next_day

    return results
