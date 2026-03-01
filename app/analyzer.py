import csv
import io

from app.date_parser import DATE_TIME_PATTERN, parse_dates
from app.emoji import extract_trailing_emoji, is_emoji_component, normalize_emoji
from app.logger import get_logger
from app.schedule import BIBLE_DATES, NT_DATES, detect_schedule

# 출력 함수를 output_builder에서 re-export (하위호환)
from app.output_builder import (  # noqa: F401
    apply_sheet_style as _apply_sheet_style,
    build_dual_preview_data,
    build_output_csv,
    build_output_xlsx,
    build_preview_data,
    sort_dates,
    _add_meta_sheet,
)
from app.style_constants import COL_PAD, ROW_PAD  # noqa: F401

logger = get_logger("analyzer")

MAX_DATES_PER_MESSAGE = 14

_STRIP_WORDS = ("맑은샘", "광천", "누나", "오빠", "언니", " 형")
_STRIP_SUFFIXES = ()


def normalize_user_name(name: str) -> str:
    """이름에서 숫자·이모티콘·영어·공백·특정 키워드를 제거하여 한글 이름만 남긴다."""
    result = name
    for word in _STRIP_WORDS:
        result = result.replace(word, "")
    for suffix in _STRIP_SUFFIXES:
        result = result.removesuffix(suffix)
    result = "".join(
        ch for ch in result
        if not is_emoji_component(ch)
        and not ch.isdigit()
        and not ch.isspace()
        and not ("A" <= ch <= "Z" or "a" <= ch <= "z")
    )
    return result if result else name


def _max_date(dates):
    best = None
    for d in dates:
        try:
            month, day = d.split("/")
            t = (int(month), int(day))
        except (ValueError, TypeError):
            continue
        if best is None or t > best:
            best = t
    return best


def decode_payload(payload):
    for encoding in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            result = payload.decode(encoding)
            logger.info("인코딩 감지: %s (%d bytes → %d chars)", encoding, len(payload), len(result))
            return result
        except UnicodeDecodeError:
            continue
    logger.warning("인코딩 감지 실패 — utf-8 errors=replace로 폴백 (%d bytes)", len(payload))
    return payload.decode("utf-8", errors="replace")


# 하위호환 alias
decode_csv_payload = decode_payload


def iter_data_rows(reader):
    first_row = next(reader, None)
    if first_row is None:
        return
    if first_row and not DATE_TIME_PATTERN.match(first_row[0].strip()):
        pass
    else:
        yield first_row
    for row in reader:
        yield row


def choose_assigned_emoji(counts, order):
    if not counts:
        return ""
    max_count = max(counts.values())
    for emoji in order:
        if counts.get(emoji) == max_count:
            return emoji
    return next(iter(counts.keys()))


def message_contains_emoji(message, emoji_key, emoji_raw):
    if emoji_raw and emoji_raw in message:
        return True
    normalized_message = normalize_emoji(message)
    return emoji_key in normalized_message


def extract_tracks(message):
    tracks = set()
    if "구약" in message:
        tracks.add("old")
    if "신약" in message:
        tracks.add("new")
    if not tracks:
        tracks = {"old", "new"}
    return tracks


def parse_csv_rows(csv_text):
    """CSV 텍스트를 파싱하여 (user, message) 튜플 리스트를 반환한다."""
    rows = []
    total_rows = 0
    skip_short = 0
    skip_empty = 0
    reader = csv.reader(io.StringIO(csv_text, newline=""))
    for row in iter_data_rows(reader):
        total_rows += 1
        if not row or len(row) < 3:
            skip_short += 1
            continue
        user = row[1].strip()
        message = row[2].strip()
        if not user or not message:
            skip_empty += 1
            continue
        rows.append((user, message))
    logger.info("CSV 파싱: 전체 %d행, 유효 %d행 (컬럼 부족 %d행, 빈 값 %d행 스킵)",
                total_rows, len(rows), skip_short, skip_empty)
    return rows


def analyze_chat(csv_text=None, track_mode="single", rows=None):
    if rows is None:
        rows = parse_csv_rows(csv_text or "")

    # 사용자 이름 정규화
    rows = [(normalize_user_name(user), message) for user, message in rows]

    logger.info("파싱된 메시지 수: %d, 트랙 모드: %s", len(rows), track_mode)
    if not rows:
        logger.warning("파싱된 메시지가 0건 — 파일 형식이나 인코딩을 확인하세요")
        return {}

    unique_users = {user for user, _ in rows}
    logger.info("메시지 발신자 수: %d명 (%s)", len(unique_users),
                ", ".join(sorted(unique_users)[:10]) + ("..." if len(unique_users) > 10 else ""))

    emoji_counts = {}
    emoji_order = {}
    emoji_raw = {}

    skip_no_date = 0
    skip_too_many_dates = 0
    skip_no_emoji = 0

    for user, message in rows:
        dates = parse_dates(message)
        if not dates:
            skip_no_date += 1
            continue
        if len(dates) > MAX_DATES_PER_MESSAGE:
            skip_too_many_dates += 1
            continue
        trailing_emoji = extract_trailing_emoji(message)
        if not trailing_emoji:
            skip_no_emoji += 1
            continue
        emoji_key = normalize_emoji(trailing_emoji)
        counts = emoji_counts.setdefault(user, {})
        counts[emoji_key] = counts.get(emoji_key, 0) + 1
        order = emoji_order.setdefault(user, [])
        if emoji_key not in order:
            order.append(emoji_key)
        raw_map = emoji_raw.setdefault(user, {})
        if emoji_key not in raw_map:
            raw_map[emoji_key] = trailing_emoji

    logger.info(
        "이모지 감지 단계 — 날짜 없음: %d건, 날짜 과다(>%d): %d건, 이모지 없음: %d건",
        skip_no_date, MAX_DATES_PER_MESSAGE, skip_too_many_dates, skip_no_emoji,
    )

    user_emojis = {}
    for user, counts in emoji_counts.items():
        order = emoji_order.get(user, [])
        emoji_key = choose_assigned_emoji(counts, order)
        if not emoji_key:
            continue
        emoji_value = emoji_raw.get(user, {}).get(emoji_key, emoji_key)
        user_emojis[user] = {"emoji_key": emoji_key, "emoji": emoji_value}

    logger.info("이모지 할당된 사용자: %d명", len(user_emojis))
    if not user_emojis:
        logger.warning(
            "이모지 할당된 사용자가 0명 — 메시지에 날짜+이모지 조합이 없습니다. "
            "샘플 메시지(처음 5건): %s",
            [msg[:80] for _, msg in rows[:5]],
        )
        return {}
    for user, info in sorted(user_emojis.items()):
        logger.debug("  %s → %s", user, info["emoji"])

    if track_mode == "dual":
        schedule_old = BIBLE_DATES
        schedule_new = NT_DATES
        logger.info("듀얼 모드 — 구약 진도표 날짜 %d개, 신약 진도표 날짜 %d개",
                     len(schedule_old), len(schedule_new))
    else:
        schedule = detect_schedule(rows)
        if schedule is not None:
            logger.info("싱글 모드 — 진도표 감지됨 (유효 날짜 %d개)", len(schedule))
        else:
            logger.info("싱글 모드 — 진도표 미감지 (날짜 필터 미적용)")

    users = {}
    user_last_date = {}
    skip_no_assigned = 0
    skip_emoji_mismatch = 0
    skip_no_dates_2 = 0
    skip_too_many_dates_2 = 0
    skip_schedule_filter = 0
    skip_no_track = 0

    for user, message in rows:
        assigned = user_emojis.get(user)
        if not assigned:
            skip_no_assigned += 1
            continue
        if not message_contains_emoji(message, assigned["emoji_key"], assigned["emoji"]):
            skip_emoji_mismatch += 1
            continue

        if track_mode == "dual":
            tracks = extract_tracks(message)
            if not tracks:
                skip_no_track += 1
                continue
            last_old = user_last_date.get((user, "old"))
            last_new = user_last_date.get((user, "new"))
            if tracks == {"old"}:
                last_date = last_old
            elif tracks == {"new"}:
                last_date = last_new
            else:
                if last_old is not None and last_new is not None:
                    last_date = min(last_old, last_new)
                else:
                    last_date = last_old or last_new
            dates = parse_dates(message, last_date=last_date)
        else:
            last_date = user_last_date.get(user)
            dates = parse_dates(message, last_date=last_date)

        if not dates:
            skip_no_dates_2 += 1
            continue
        if len(dates) > MAX_DATES_PER_MESSAGE:
            skip_too_many_dates_2 += 1
            continue

        if track_mode == "dual":
            dates_old = [d for d in dates if d in schedule_old] if "old" in tracks else []
            dates_new = [d for d in dates if d in schedule_new] if "new" in tracks else []
            if not dates_old and not dates_new:
                skip_schedule_filter += 1
                continue
            entry = users.setdefault(
                user,
                {"dates_old": set(), "dates_new": set(), "emoji": assigned["emoji"]},
            )
            for date_value in dates_old:
                entry["dates_old"].add(date_value)
            for date_value in dates_new:
                entry["dates_new"].add(date_value)
            if dates_old:
                md = _max_date(dates_old)
                if md:
                    prev = user_last_date.get((user, "old"))
                    if prev is None or md > prev:
                        user_last_date[(user, "old")] = md
            if dates_new:
                md = _max_date(dates_new)
                if md:
                    prev = user_last_date.get((user, "new"))
                    if prev is None or md > prev:
                        user_last_date[(user, "new")] = md
        else:
            if schedule is not None:
                filtered_dates = [d for d in dates if d in schedule]
                if not filtered_dates and dates:
                    skip_schedule_filter += 1
                dates = filtered_dates
            if not dates:
                continue
            entry = users.setdefault(
                user,
                {"dates": set(), "emoji": assigned["emoji"]},
            )
            for date_value in dates:
                entry["dates"].add(date_value)
            md = _max_date(dates)
            if md:
                prev = user_last_date.get(user)
                if prev is None or md > prev:
                    user_last_date[user] = md

    logger.info(
        "날짜 수집 단계 — 이모지 미할당: %d건, 이모지 불일치: %d건, "
        "날짜 없음: %d건, 날짜 과다: %d건, 진도표 필터링: %d건%s",
        skip_no_assigned, skip_emoji_mismatch,
        skip_no_dates_2, skip_too_many_dates_2, skip_schedule_filter,
        f", 트랙 미지정(구약/신약): {skip_no_track}건" if track_mode == "dual" else "",
    )
    logger.info("최종 분석 결과: %d명", len(users))
    if not users:
        logger.warning(
            "분석 결과 0명 — 이모지 할당자 %d명 중 유효 날짜를 가진 사용자가 없습니다",
            len(user_emojis),
        )

    return users
