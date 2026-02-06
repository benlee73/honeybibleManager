import csv
import io

from app.date_parser import DATE_TIME_PATTERN, parse_dates
from app.emoji import extract_trailing_emoji, normalize_emoji

MAX_DATES_PER_MESSAGE = 14


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


def extract_tracks(message):
    tracks = set()
    if "구약" in message:
        tracks.add("old")
    if "신약" in message:
        tracks.add("new")
    return tracks


def analyze_chat(csv_text, track_mode="single"):
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
        if len(dates) > MAX_DATES_PER_MESSAGE:
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
        if len(dates) > MAX_DATES_PER_MESSAGE:
            continue

        if track_mode == "dual":
            tracks = extract_tracks(message)
            if not tracks:
                continue
            entry = users.setdefault(
                user,
                {"dates_old": set(), "dates_new": set(), "emoji": assigned["emoji"]},
            )
            for date_value in dates:
                if "old" in tracks:
                    entry["dates_old"].add(date_value)
                if "new" in tracks:
                    entry["dates_new"].add(date_value)
        else:
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


def build_output_csv(users, track_mode="single"):
    output = io.StringIO(newline="")
    writer = csv.writer(output)

    if track_mode == "dual":
        all_dates = set()
        for entry in users.values():
            all_dates.update(entry.get("dates_old", set()))
            all_dates.update(entry.get("dates_new", set()))
        all_dates_sorted = sort_dates(all_dates)

        header = ["이름", "이모티콘", "트랙"]
        header.extend(all_dates_sorted)
        writer.writerow(header)

        all_users = sorted(
            u for u, e in users.items()
            if e.get("dates_old") or e.get("dates_new")
        )
        for user in all_users:
            entry = users[user]
            if entry.get("dates_old"):
                row = [user, entry.get("emoji", ""), "구약"]
                row.extend("O" if d in entry["dates_old"] else "" for d in all_dates_sorted)
                writer.writerow(row)
            if entry.get("dates_new"):
                row = [user, entry.get("emoji", ""), "신약"]
                row.extend("O" if d in entry["dates_new"] else "" for d in all_dates_sorted)
                writer.writerow(row)
    else:
        user_dates = {}
        all_dates = set()
        for user, entry in users.items():
            if not entry["dates"]:
                continue
            user_dates[user] = entry["dates"]
            all_dates.update(entry["dates"])

        all_dates_sorted = sort_dates(all_dates)

        header = ["이름", "이모티콘"]
        header.extend(all_dates_sorted)
        writer.writerow(header)

        for user in sorted(user_dates.keys()):
            entry = users[user]
            date_set = user_dates[user]
            row = [user, entry.get("emoji", "")]
            row.extend("O" if d in date_set else "" for d in all_dates_sorted)
            writer.writerow(row)

    return output.getvalue().encode("utf-8-sig")
