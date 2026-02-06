import csv
import io

import pytest

from app.analyzer import (
    analyze_chat,
    build_output_csv,
    choose_assigned_emoji,
    decode_csv_payload,
    extract_tracks,
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
        assert header[2:] == ["1/5", "3/15", "3/16"]
        assert len(rows) == 3

    def test_build_output_csv__date_columns_marked_with_o(self):
        users = {
            "user1": {"dates": {"2/2", "2/3", "2/5"}, "emoji": "😀"},
            "user2": {"dates": {"2/2", "2/4"}, "emoji": "🔥"},
        }
        output = build_output_csv(users)
        text = output.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(text, newline=""))
        rows = list(reader)
        header = rows[0]
        assert header[2:] == ["2/2", "2/3", "2/4", "2/5"]
        # user1: 2/2 O, 2/3 O, 2/4 빈칸, 2/5 O
        user1_row = rows[1]
        assert user1_row[0] == "user1"
        assert user1_row[2:] == ["O", "O", "", "O"]
        # user2: 2/2 O, 2/3 빈칸, 2/4 O, 2/5 빈칸
        user2_row = rows[2]
        assert user2_row[0] == "user2"
        assert user2_row[2:] == ["O", "", "O", ""]

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


class TestExtractTracks:
    def test_extract_tracks__구약만__old_반환(self):
        assert extract_tracks("2/2 구약 🐷") == {"old"}

    def test_extract_tracks__신약만__new_반환(self):
        assert extract_tracks("2/2 신약 🐷") == {"new"}

    def test_extract_tracks__둘_다__old_new_반환(self):
        assert extract_tracks("2/2 구약 신약 🐷") == {"old", "new"}

    def test_extract_tracks__키워드_없음__빈_set_반환(self):
        assert extract_tracks("2/2 🐷") == set()


class TestAnalyzeChatDual:
    def _make_csv(self, rows):
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        for row in rows:
            writer.writerow(row)
        return output.getvalue()

    def test_analyze_chat_dual__구약_신약_날짜_분리(self):
        csv_text = self._make_csv([
            ["날짜", "이름", "메시지"],
            ["2024-01-01", "user1", "2/2 구약 😀"],
            ["2024-01-02", "user1", "2/3 신약 😀"],
            ["2024-01-03", "user1", "2/4 구약 신약 😀"],
        ])
        result = analyze_chat(csv_text, track_mode="dual")
        assert "user1" in result
        assert result["user1"]["dates_old"] == {"2/2", "2/4"}
        assert result["user1"]["dates_new"] == {"2/3", "2/4"}

    def test_analyze_chat_dual__키워드_없는_메시지_스킵(self):
        csv_text = self._make_csv([
            ["날짜", "이름", "메시지"],
            ["2024-01-01", "user1", "2/2 구약 😀"],
            ["2024-01-02", "user1", "2/3 😀"],
        ])
        result = analyze_chat(csv_text, track_mode="dual")
        assert "user1" in result
        assert result["user1"]["dates_old"] == {"2/2"}
        assert result["user1"]["dates_new"] == set()

    def test_analyze_chat_dual__여러_사용자(self):
        csv_text = self._make_csv([
            ["날짜", "이름", "메시지"],
            ["2024-01-01", "user1", "2/2 구약 😀"],
            ["2024-01-01", "user2", "2/2 신약 🔥"],
            ["2024-01-02", "user2", "2/3 구약 신약 🔥"],
        ])
        result = analyze_chat(csv_text, track_mode="dual")
        assert result["user1"]["dates_old"] == {"2/2"}
        assert result["user1"]["dates_new"] == set()
        assert result["user2"]["dates_old"] == {"2/3"}
        assert result["user2"]["dates_new"] == {"2/2", "2/3"}

    def test_analyze_chat_single__기존_동작_유지(self):
        csv_text = self._make_csv([
            ["날짜", "이름", "메시지"],
            ["2024-01-01", "user1", "2/2😀"],
        ])
        result = analyze_chat(csv_text, track_mode="single")
        assert "dates" in result["user1"]
        assert result["user1"]["dates"] == {"2/2"}


class TestBuildOutputCsvDual:
    def test_build_output_csv_dual__트랙_컬럼_포함(self):
        users = {
            "user1": {"dates_old": {"2/2", "2/4"}, "dates_new": {"2/3"}, "emoji": "😀"},
        }
        output = build_output_csv(users, track_mode="dual")
        text = output.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(text, newline=""))
        rows = list(reader)
        header = rows[0]
        assert header[0] == "이름"
        assert header[1] == "이모티콘"
        assert header[2] == "트랙"

    def test_build_output_csv_dual__구약_먼저_신약_나중(self):
        users = {
            "user1": {"dates_old": {"2/2"}, "dates_new": {"2/3"}, "emoji": "😀"},
            "user2": {"dates_old": {"2/2"}, "dates_new": {"2/3"}, "emoji": "🔥"},
        }
        output = build_output_csv(users, track_mode="dual")
        text = output.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(text, newline=""))
        rows = list(reader)
        # 헤더 + user1구약 + user2구약 + user1신약 + user2신약 = 5행
        assert len(rows) == 5
        assert rows[1][2] == "구약"
        assert rows[2][2] == "구약"
        assert rows[3][2] == "신약"
        assert rows[4][2] == "신약"

    def test_build_output_csv_dual__빈_트랙_사용자_생략(self):
        users = {
            "user1": {"dates_old": {"2/2"}, "dates_new": set(), "emoji": "😀"},
            "user2": {"dates_old": set(), "dates_new": {"2/3"}, "emoji": "🔥"},
        }
        output = build_output_csv(users, track_mode="dual")
        text = output.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(text, newline=""))
        rows = list(reader)
        # 헤더 + user1구약 + user2신약 = 3행
        assert len(rows) == 3
        assert rows[1][0] == "user1"
        assert rows[1][2] == "구약"
        assert rows[2][0] == "user2"
        assert rows[2][2] == "신약"

    def test_build_output_csv_dual__날짜_마킹_정확(self):
        users = {
            "user1": {"dates_old": {"2/2"}, "dates_new": {"2/3"}, "emoji": "😀"},
        }
        output = build_output_csv(users, track_mode="dual")
        text = output.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(text, newline=""))
        rows = list(reader)
        header = rows[0]
        date_cols = header[3:]
        assert date_cols == ["2/2", "2/3"]
        # 구약 행: 2/2=O, 2/3=빈칸
        old_row = rows[1]
        assert old_row[3:] == ["O", ""]
        # 신약 행: 2/2=빈칸, 2/3=O
        new_row = rows[2]
        assert new_row[3:] == ["", "O"]

    def test_build_output_csv_dual__빈_사용자__헤더만(self):
        output = build_output_csv({}, track_mode="dual")
        text = output.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(text, newline=""))
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0][:3] == ["이름", "이모티콘", "트랙"]
