import argparse
import csv
import io
import json
import mimetypes
import os
import re
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import unquote

DATE_TIME_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}")
DATE_PATTERN = re.compile(r"(?<!\d)(\d{1,2})\s*/\s*(\d{1,2})(?!\d)")
DATE_TOKEN_PATTERN = re.compile(r"(\d{1,2})/(\d{1,2})")
DAY_ONLY_PATTERN = re.compile(r"(\d{1,2})")

PUBLIC_DIR = os.path.join(os.path.dirname(__file__), "public")

EMOJI_RANGES = [
    (0x1F300, 0x1F5FF),
    (0x1F600, 0x1F64F),
    (0x1F680, 0x1F6FF),
    (0x1F700, 0x1F77F),
    (0x1F780, 0x1F7FF),
    (0x1F800, 0x1F8FF),
    (0x1F900, 0x1F9FF),
    (0x1FA00, 0x1FA6F),
    (0x1FA70, 0x1FAFF),
    (0x2600, 0x26FF),
    (0x2700, 0x27BF),
    (0x2300, 0x23FF),
    (0x2B00, 0x2BFF),
    (0x1F1E6, 0x1F1FF),
]

EMOJI_MODIFIER_RANGE = (0x1F3FB, 0x1F3FF)
ZWJ = 0x200D
VARIATION_SELECTOR = 0xFE0F
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


def is_emoji_char(char):
    codepoint = ord(char)
    for start, end in EMOJI_RANGES:
        if start <= codepoint <= end:
            return True
    return False


def is_emoji_modifier(char):
    codepoint = ord(char)
    return EMOJI_MODIFIER_RANGE[0] <= codepoint <= EMOJI_MODIFIER_RANGE[1]


def is_emoji_component(char):
    codepoint = ord(char)
    return (
        is_emoji_char(char)
        or is_emoji_modifier(char)
        or codepoint == VARIATION_SELECTOR
        or codepoint == ZWJ
    )


def extract_emoji_sequence(text, start_index):
    if start_index >= len(text):
        return None, start_index
    if not is_emoji_char(text[start_index]):
        return None, start_index

    end_index = start_index + 1
    while end_index < len(text) and is_emoji_component(text[end_index]):
        end_index += 1
    return text[start_index:end_index], end_index


def normalize_emoji(emoji_text):
    return emoji_text.replace("\ufe0f", "")


def extract_trailing_emoji(text):
    trimmed = text.rstrip()
    if not trimmed:
        return None

    index = 0
    last_emoji = None
    last_end = 0
    while index < len(trimmed):
        if is_emoji_char(trimmed[index]):
            emoji, end_index = extract_emoji_sequence(trimmed, index)
            if emoji:
                last_emoji = emoji
                last_end = end_index
                index = end_index
                continue
        index += 1

    if last_emoji and last_end == len(trimmed):
        return last_emoji
    return None


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


def parse_dates(message):
    if not message:
        return []
    cleaned = re.sub(r"\s+", "", message)
    results = []
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

        while index < len(cleaned) and cleaned[index] in ("~", ","):
            separator = cleaned[index]
            index += 1
            parsed = parse_date_or_day(cleaned, index, current_month)
            if not parsed:
                break
            next_month, next_day, index = parsed
            if separator == "~":
                results.extend(
                    expand_range(current_month, current_day, next_month, next_day)
                )
            else:
                results.append(f"{next_month}/{next_day}")
            current_month = next_month
            current_day = next_day

    return results


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


def extract_multipart_file(payload, content_type, field_name="file"):
    try:
        header = f"Content-Type: {content_type}\r\n\r\n".encode("utf-8")
        message = BytesParser(policy=default).parsebytes(header + payload)
    except Exception:
        return None, None, "Failed to parse multipart payload"

    if message.get_content_maintype() != "multipart":
        return None, None, "Expected multipart/form-data"

    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue
        name = part.get_param("name", header="content-disposition")
        if name != field_name:
            continue
        filename = part.get_filename()
        data = part.get_payload(decode=True)
        return filename, data, None

    return None, None, "CSV file is required"


class HoneyBibleHandler(BaseHTTPRequestHandler):
    server_version = "HoneyBibleServer/0.1"

    def _send_json(self, status_code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors()
        self.end_headers()
        self.wfile.write(body)

    def _send_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _resolve_public_path(self, request_path):
        clean_path = request_path.split("?", 1)[0].split("#", 1)[0]
        clean_path = unquote(clean_path or "/")
        if clean_path in ("", "/"):
            clean_path = "/index.html"
        clean_path = clean_path.lstrip("/")

        base_path = os.path.realpath(PUBLIC_DIR)
        target_path = os.path.realpath(os.path.join(base_path, clean_path))
        if not target_path.startswith(base_path + os.sep):
            return None
        return target_path

    def _send_file(self, file_path):
        if not file_path or not os.path.isfile(file_path):
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Not found")
            return

        content_type, _ = mimetypes.guess_type(file_path)
        if not content_type:
            content_type = "application/octet-stream"

        try:
            with open(file_path, "rb") as handle:
                body = handle.read()
        except OSError:
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Failed to read file")
            return

        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors()
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/analyze"):
            self._send_json(405, {"message": "Method not allowed"})
            return

        file_path = self._resolve_public_path(self.path)
        self._send_file(file_path)

    def do_POST(self):
        if self.path != "/analyze":
            self._send_json(404, {"message": "Not found"})
            return

        content_type = self.headers.get("Content-Type")
        if not content_type:
            self._send_json(400, {"message": "Missing Content-Type header"})
            return

        if "multipart/form-data" not in content_type:
            self._send_json(400, {"message": "Expected multipart/form-data"})
            return

        content_length = self.headers.get("Content-Length")
        if not content_length:
            self._send_json(411, {"message": "Missing Content-Length header"})
            return

        try:
            length = int(content_length)
        except ValueError:
            self._send_json(400, {"message": "Invalid Content-Length header"})
            return

        if length <= 0:
            self._send_json(400, {"message": "CSV file is empty"})
            return

        payload = self.rfile.read(length)
        filename, file_bytes, error_message = extract_multipart_file(
            payload,
            content_type,
        )
        if error_message:
            self._send_json(400, {"message": error_message})
            return

        if not file_bytes:
            self._send_json(400, {"message": "CSV file is empty"})
            return

        csv_text = decode_csv_payload(file_bytes)
        users = analyze_chat(csv_text)
        output_csv = build_output_csv(users)

        filename = "honeybible-results.csv"
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header(
            "Content-Disposition",
            f'attachment; filename="{filename}"',
        )
        self.send_header("Content-Length", str(len(output_csv)))
        self._send_cors()
        self.end_headers()
        self.wfile.write(output_csv)


def main():
    parser = argparse.ArgumentParser(description="Honey Bible CSV analyzer server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), HoneyBibleHandler)
    print(f"HoneyBible server running on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
