import pytest

from app.date_parser import expand_range, is_valid_date, normalize_date, parse_date_or_day, parse_dates


class TestIsValidDate:
    def test_is_valid_date__normal_date__returns_true(self):
        assert is_valid_date(3, 15) is True

    def test_is_valid_date__month_exceeds_range__returns_false(self):
        assert is_valid_date(13, 1) is False

    def test_is_valid_date__month_zero__returns_false(self):
        assert is_valid_date(0, 1) is False

    def test_is_valid_date__day_exceeds_range__returns_false(self):
        assert is_valid_date(1, 32) is False

    def test_is_valid_date__day_zero__returns_false(self):
        assert is_valid_date(1, 0) is False

    def test_is_valid_date__feb_28__returns_true(self):
        assert is_valid_date(2, 28) is True

    def test_is_valid_date__feb_29__returns_false(self):
        assert is_valid_date(2, 29) is False

    def test_is_valid_date__jan_31__returns_true(self):
        assert is_valid_date(1, 31) is True

    def test_is_valid_date__apr_30__returns_true(self):
        assert is_valid_date(4, 30) is True

    def test_is_valid_date__apr_31__returns_false(self):
        assert is_valid_date(4, 31) is False


class TestNormalizeDate:
    def test_normalize_date__valid_match__returns_formatted(self):
        import re
        match = re.match(r"(\d{1,2})/(\d{1,2})", "3/15")
        assert normalize_date(match) == "3/15"

    def test_normalize_date__month_out_of_range__returns_none(self):
        import re
        match = re.match(r"(\d{1,2})/(\d{1,2})", "13/1")
        assert normalize_date(match) is None

    def test_normalize_date__day_out_of_range__returns_none(self):
        import re
        match = re.match(r"(\d{1,2})/(\d{1,2})", "1/32")
        assert normalize_date(match) is None

    def test_normalize_date__zero_month__returns_none(self):
        import re
        match = re.match(r"(\d{1,2})/(\d{1,2})", "0/15")
        assert normalize_date(match) is None


class TestParseDateOrDay:
    def test_parse_date_or_day__full_date_format__returns_month_day(self):
        result = parse_date_or_day("3/15", 0, 1)
        assert result == (3, 15, 4)

    def test_parse_date_or_day__day_only__uses_current_month(self):
        result = parse_date_or_day("15", 0, 5)
        assert result == (5, 15, 2)

    def test_parse_date_or_day__invalid_full_date__returns_none(self):
        result = parse_date_or_day("13/1", 0, 1)
        assert result is None

    def test_parse_date_or_day__invalid_day_only__returns_none(self):
        result = parse_date_or_day("32", 0, 1)
        assert result is None

    def test_parse_date_or_day__with_offset__parses_from_index(self):
        result = parse_date_or_day("xx3/15", 2, 1)
        assert result == (3, 15, 6)


class TestExpandRange:
    def test_expand_range__same_month__returns_dates_in_between(self):
        result = expand_range(3, 1, 3, 3)
        assert result == ["3/2", "3/3"]

    def test_expand_range__across_months__includes_month_boundary(self):
        result = expand_range(1, 30, 2, 2)
        assert result == ["1/31", "2/1", "2/2"]

    def test_expand_range__reverse_order__returns_empty(self):
        result = expand_range(3, 5, 3, 1)
        assert result == []

    def test_expand_range__same_date__returns_empty(self):
        result = expand_range(3, 5, 3, 5)
        assert result == []

    def test_expand_range__single_day_diff__returns_one(self):
        result = expand_range(3, 5, 3, 6)
        assert result == ["3/6"]


class TestParseDates:
    def test_parse_dates__single_date__returns_one(self):
        assert parse_dates("3/15") == ["3/15"]

    def test_parse_dates__comma_separated__returns_all(self):
        assert parse_dates("3/15,3/16") == ["3/15", "3/16"]

    def test_parse_dates__range_with_tilde__expands(self):
        result = parse_dates("3/1~3/3")
        assert result == ["3/1", "3/2", "3/3"]

    def test_parse_dates__mixed_comma_and_range__returns_all(self):
        result = parse_dates("3/1,3/5~3/7")
        assert result == ["3/1", "3/5", "3/6", "3/7"]

    def test_parse_dates__with_spaces__handles_correctly(self):
        result = parse_dates("3 / 15")
        assert result == ["3/15"]

    def test_parse_dates__empty_string__returns_empty(self):
        assert parse_dates("") == []

    def test_parse_dates__none__returns_empty(self):
        assert parse_dates(None) == []

    def test_parse_dates__invalid_date__skips_it(self):
        assert parse_dates("13/1") == []

    def test_parse_dates__day_only_after_comma__uses_current_month(self):
        result = parse_dates("3/15,16")
        assert result == ["3/15", "3/16"]

    def test_parse_dates__text_with_embedded_date__extracts_date(self):
        result = parse_dates("오늘은 3/15 입니다")
        assert "3/15" in result


class TestParseDatesLeadingTilde:
    def test_선행_틸드__기본_확장(self):
        result = parse_dates("~2/7", last_date=(2, 4))
        assert result == ["2/5", "2/6", "2/7"]

    def test_선행_틸드__last_date_없으면_기존_동작(self):
        result = parse_dates("~2/7")
        assert result == ["2/7"]

    def test_선행_틸드__콤마_조합(self):
        result = parse_dates("~2/7,2/10", last_date=(2, 4))
        assert result == ["2/5", "2/6", "2/7", "2/10"]

    def test_선행_틸드__월_경계(self):
        result = parse_dates("~2/2", last_date=(1, 30))
        assert result == ["1/31", "2/1", "2/2"]

    def test_선행_틸드__같은_날짜__빈_결과(self):
        result = parse_dates("~2/4", last_date=(2, 4))
        assert result == []

    def test_선행_틸드__역순__빈_결과(self):
        result = parse_dates("~2/3", last_date=(2, 5))
        assert result == []

    def test_선행_틸드__1일_차이(self):
        result = parse_dates("~2/5", last_date=(2, 4))
        assert result == ["2/5"]

    def test_선행_틸드__공백_포함(self):
        result = parse_dates("~ 2/7", last_date=(2, 4))
        assert result == ["2/5", "2/6", "2/7"]

    def test_틸드_없는_메시지에_last_date_전달__무시(self):
        result = parse_dates("2/7", last_date=(2, 4))
        assert result == ["2/7"]

    def test_중간_틸드__last_date_전달__기존_범위_확장_유지(self):
        result = parse_dates("2/4~2/7", last_date=(2, 1))
        assert result == ["2/4", "2/5", "2/6", "2/7"]
