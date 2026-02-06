import csv
import io

from app.date_parser import DATE_TIME_PATTERN, parse_dates
from app.emoji import extract_trailing_emoji, normalize_emoji


def decode_csv_payload(payload):
    for encoding in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return payload.decode("utf-8", errors="replace")


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


def analyze_chat(csv_text):
    rows = []
    reader = csv.reader(io.StringIO(csv_text, newline=""))
    for row in iter_data_rows(reader):
        if not row or len(row) < 3:
            continue
        user = row[1].strip()
        message = row[2].strip()
        if not user or not message:
            continue
        rows.append((user, message))

    emoji_counts = {}
    emoji_order = {}
    emoji_raw = {}

    for user, message in rows:
        dates = parse_dates(message)
        if not dates:
            continue
        trailing_emoji = extract_trailing_emoji(message)
        if not trailing_emoji:
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

    user_emojis = {}
    for user, counts in emoji_counts.items():
        order = emoji_order.get(user, [])
        emoji_key = choose_assigned_emoji(counts, order)
        if not emoji_key:
            continue
        emoji_value = emoji_raw.get(user, {}).get(emoji_key, emoji_key)
        user_emojis[user] = {"emoji_key": emoji_key, "emoji": emoji_value}

    users = {}
    for user, message in rows:
        assigned = user_emojis.get(user)
        if not assigned:
            continue
        if not message_contains_emoji(message, assigned["emoji_key"], assigned["emoji"]):
            continue
        dates = parse_dates(message)
        if not dates:
            continue
        entry = users.setdefault(
            user,
            {"dates": set(), "emoji": assigned["emoji"]},
        )
        for date_value in dates:
            entry["dates"].add(date_value)

    return users


def sort_dates(dates):
    def key(value):
        try:
            month, day = value.split("/")
            return (int(month), int(day))
        except (ValueError, TypeError):
            return (99, 99)

    return sorted(dates, key=key)


def build_output_csv(users):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    user_dates = {}
    max_dates = 0

    for user, entry in users.items():
        if not entry["dates"]:
            continue
        dates = sort_dates(entry["dates"])
        user_dates[user] = dates
        if len(dates) > max_dates:
            max_dates = len(dates)

    header = ["이름", "이모티콘"]
    header.extend([f"day{index}" for index in range(1, max_dates + 1)])
    writer.writerow(header)

    for user in sorted(user_dates.keys()):
        entry = users[user]
        dates = user_dates[user]
        row = [user, entry.get("emoji", "")] + dates
        if len(dates) < max_dates:
            row.extend([""] * (max_dates - len(dates)))
        writer.writerow(row)

    return output.getvalue().encode("utf-8-sig")
