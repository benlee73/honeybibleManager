import csv
import io

import pytest

from app.analyzer import (
    analyze_chat,
    build_output_csv,
    choose_assigned_emoji,
    decode_csv_payload,
    iter_data_rows,
    message_contains_emoji,
    sort_dates,
)


class TestDecodeCsvPayload:
    def test_decode_csv_payload__utf8_bom__decodes_correctly(self):
        text = "한글 텍스트"
        payload = b"\xef\xbb\xbf" + text.encode("utf-8")
        assert decode_csv_payload(payload) == text

    def test_decode_csv_payload__utf8__decodes_correctly(self):
        text = "hello world"
        payload = text.encode("utf-8")
        assert decode_csv_payload(payload) == text

    def test_decode_csv_payload__cp949__decodes_correctly(self):
        text = "한글 텍스트"
        payload = text.encode("cp949")
        assert decode_csv_payload(payload) == text

    def test_decode_csv_payload__invalid_bytes__replaces_errors(self):
        payload = b"\xff\xfe\xfd\x80\x81"
        result = decode_csv_payload(payload)
        assert isinstance(result, str)
        assert "\ufffd" in result


class TestIterDataRows:
    def test_iter_data_rows__with_header__skips_header(self):
        csv_text = "날짜,이름,메시지\n2024-01-01,user1,hello"
        reader = csv.reader(io.StringIO(csv_text, newline=""))
        rows = list(iter_data_rows(reader))
        assert len(rows) == 1
        assert rows[0][1] == "user1"

    def test_iter_data_rows__data_starts_with_date__yields_first_row(self):
        csv_text = "2024-01-01,user1,hello\n2024-01-02,user2,world"
        reader = csv.reader(io.StringIO(csv_text, newline=""))
        rows = list(iter_data_rows(reader))
        assert len(rows) == 2

    def test_iter_data_rows__empty_reader__yields_nothing(self):
        reader = csv.reader(io.StringIO("", newline=""))
        rows = list(iter_data_rows(reader))
        assert rows == []


class TestChooseAssignedEmoji:
    def test_choose_assigned_emoji__highest_count__returns_it(self):
        counts = {"😀": 3, "🔥": 1}
        order = ["😀", "🔥"]
        assert choose_assigned_emoji(counts, order) == "😀"

    def test_choose_assigned_emoji__tie__returns_first_in_order(self):
        counts = {"😀": 2, "🔥": 2}
        order = ["🔥", "😀"]
        assert choose_assigned_emoji(counts, order) == "🔥"

    def test_choose_assigned_emoji__empty_counts__returns_empty_string(self):
        assert choose_assigned_emoji({}, []) == ""

    def test_choose_assigned_emoji__max_not_in_order__returns_first_key(self):
        counts = {"😀": 3, "🔥": 1}
        order = ["🎉"]
        result = choose_assigned_emoji(counts, order)
        assert result == "😀"


class TestMessageContainsEmoji:
    def test_message_contains_emoji__raw_emoji_present__returns_true(self):
        assert message_contains_emoji("hello😀world", "😀", "😀") is True

    def test_message_contains_emoji__normalized_match__returns_true(self):
        assert message_contains_emoji("hello☀\uFE0Fworld", "☀", None) is True

    def test_message_contains_emoji__not_present__returns_false(self):
        assert message_contains_emoji("hello world", "😀", "😀") is False

    def test_message_contains_emoji__empty_raw__falls_through_to_normalized(self):
        assert message_contains_emoji("hello😀world", "😀", "") is True


class TestAnalyzeChat:
    def _make_csv(self, rows):
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        for row in rows:
            writer.writerow(row)
        return output.getvalue()

    def test_analyze_chat__normal_csv__assigns_emoji_and_collects_dates(self):
        csv_text = self._make_csv([
            ["날짜", "이름", "메시지"],
            ["2024-01-01", "user1", "3/15😀"],
            ["2024-01-02", "user1", "3/16😀"],
        ])
        result = analyze_chat(csv_text)
        assert "user1" in result
        assert "😀" == result["user1"]["emoji"]
        assert "3/15" in result["user1"]["dates"]
        assert "3/16" in result["user1"]["dates"]

    def test_analyze_chat__user_without_emoji__excluded(self):
        csv_text = self._make_csv([
            ["날짜", "이름", "메시지"],
            ["2024-01-01", "user1", "3/15"],
        ])
        result = analyze_chat(csv_text)
        assert "user1" not in result

    def test_analyze_chat__empty_csv__returns_empty(self):
        result = analyze_chat("")
        assert result == {}

    def test_analyze_chat__message_without_dates__not_counted(self):
        csv_text = self._make_csv([
            ["날짜", "이름", "메시지"],
            ["2024-01-01", "user1", "안녕하세요😀"],
        ])
        result = analyze_chat(csv_text)
        assert "user1" not in result


class TestSortDates:
    def test_sort_dates__unordered__sorts_by_month_then_day(self):
        dates = ["3/15", "1/5", "3/1", "2/28"]
        assert sort_dates(dates) == ["1/5", "2/28", "3/1", "3/15"]

    def test_sort_dates__empty__returns_empty(self):
        assert sort_dates([]) == []

    def test_sort_dates__single_element__returns_same(self):
        assert sort_dates(["5/10"]) == ["5/10"]


class TestBuildOutputCsv:
    def test_build_output_csv__normal_users__produces_valid_csv(self):
        users = {
            "user1": {"dates": {"3/15", "3/16"}, "emoji": "😀"},
            "user2": {"dates": {"1/5"}, "emoji": "🔥"},
        }
        output = build_output_csv(users)
        assert output[:3] == b"\xef\xbb\xbf"
        text = output.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(text, newline=""))
        rows = list(reader)
        header = rows[0]
        assert header[0] == "이름"
        assert header[1] == "이모티콘"
        assert len(rows) == 3

    def test_build_output_csv__user_with_no_dates__excluded(self):
        users = {
            "user1": {"dates": set(), "emoji": "😀"},
            "user2": {"dates": {"3/15"}, "emoji": "🔥"},
        }
        output = build_output_csv(users)
        text = output.decode("utf-8-sig")
        assert "user1" not in text
        assert "user2" in text

    def test_build_output_csv__bom_encoding__present(self):
        users = {"user1": {"dates": {"3/15"}, "emoji": "😀"}}
        output = build_output_csv(users)
        assert output.startswith(b"\xef\xbb\xbf")

    def test_build_output_csv__empty_users__header_only(self):
        output = build_output_csv({})
        text = output.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(text, newline=""))
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0][0] == "이름"
