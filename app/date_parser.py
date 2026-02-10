import re

DATE_TIME_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}")
DATE_PATTERN = re.compile(r"(?<!\d)(\d{1,2})\s*/\s*(\d{1,2})(?!\d)")
DATE_TOKEN_PATTERN = re.compile(r"(\d{1,2})/(\d{1,2})")
DAY_ONLY_PATTERN = re.compile(r"(\d{1,2})")

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


def parse_dates(message, last_date=None):
    if not message:
        return []
    cleaned = re.sub(r"\s+", "", message)
    results = []
    index = 0

    if cleaned[:1] in ("~", "-") and last_date is not None:
        index = 1
        match = DATE_TOKEN_PATTERN.search(cleaned, index)
        if match and match.start() == index:
            month = int(match.group(1))
            day = int(match.group(2))
            if is_valid_date(month, day):
                results.extend(
                    expand_range(last_date[0], last_date[1], month, day)
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
