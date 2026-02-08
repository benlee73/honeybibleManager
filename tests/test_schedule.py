import datetime

import pytest

from app.schedule import (
    BIBLE_DATES,
    NT_DATES,
    _BIBLE_RANGES,
    _NT_RANGES,
    _generate_dates,
    detect_schedule,
)


class TestGenerateDates:
    def test_일요일_제외__일요일_날짜_미포함(self):
        # 2026-02-08 = 일요일
        assert "2/8" not in BIBLE_DATES
        assert "2/8" not in NT_DATES

    def test_일요일_제외__토요일_포함(self):
        # 2026-02-07 = 토요일
        assert "2/7" in BIBLE_DATES
        assert "2/7" in NT_DATES

    def test_일요일_제외__월요일_포함(self):
        # 2026-02-09 = 월요일
        assert "2/9" in BIBLE_DATES
        assert "2/9" in NT_DATES

    def test_파트_간_갭_날짜__미포함(self):
        # 성경일독 파트1 종료: 5/30, 파트2 시작: 6/8
        # 5/31~6/7은 갭 기간
        assert "6/1" not in BIBLE_DATES
        assert "6/5" not in BIBLE_DATES
        assert "6/7" not in BIBLE_DATES

    def test_파트_간_갭_날짜__두번째_갭_미포함(self):
        # 성경일독 파트2 종료: 9/26, 파트3 시작: 10/5
        # 9/27~10/4는 갭 기간
        assert "9/28" not in BIBLE_DATES
        assert "10/1" not in BIBLE_DATES
        assert "10/4" not in BIBLE_DATES

    def test_시작일_포함(self):
        # 2026-02-02 = 월요일
        assert "2/2" in BIBLE_DATES
        assert "2/2" in NT_DATES

    def test_종료일_포함__성경일독(self):
        # 2026-05-30 = 토요일
        assert "5/30" in BIBLE_DATES

    def test_종료일_포함__신약일독(self):
        # 2026-05-29 = 금요일
        assert "5/29" in NT_DATES

    def test_빈_범위__빈_frozenset_반환(self):
        result = _generate_dates([])
        assert result == frozenset()

    def test_단일_날짜_범위(self):
        # 2026-02-02 = 월요일
        result = _generate_dates([(datetime.date(2026, 2, 2), datetime.date(2026, 2, 2))])
        assert result == frozenset({"2/2"})

    def test_일요일만_포함된_범위__빈_결과(self):
        # 2026-02-08 = 일요일, 하루만
        result = _generate_dates([(datetime.date(2026, 2, 8), datetime.date(2026, 2, 8))])
        assert result == frozenset()


class TestScheduleContents:
    def test_성경일독_날짜_수(self):
        # 각 파트의 총 일수에서 일요일 제외한 수
        assert len(BIBLE_DATES) > 200

    def test_신약일독_날짜_수(self):
        assert len(NT_DATES) > 200

    def test_성경일독_신약일독_크기_차이(self):
        # 성경일독이 약간 더 김 (종료일 차이)
        assert len(BIBLE_DATES) >= len(NT_DATES)

    def test_성경일독_특정_날짜_포함(self):
        # 2026-02-02 = 월요일 (파트1 시작)
        assert "2/2" in BIBLE_DATES
        # 2026-06-08 = 월요일 (파트2 시작)
        assert "6/8" in BIBLE_DATES
        # 2026-10-05 = 월요일 (파트3 시작)
        assert "10/5" in BIBLE_DATES

    def test_신약일독_종료일_다름(self):
        # 성경일독 파트1 종료: 5/30, 신약일독 파트1 종료: 5/29
        assert "5/30" in BIBLE_DATES
        assert "5/30" not in NT_DATES


class TestDetectSchedule:
    def test_성경일독_키워드_감지(self):
        rows = [
            ("user1", "창세기 1장 읽었습니다"),
            ("user2", "출애굽기 3장 완료"),
        ]
        result = detect_schedule(rows)
        assert result is BIBLE_DATES

    def test_신약일독_키워드_감지(self):
        rows = [
            ("user1", "마태복음 1장"),
            ("user2", "마가복음 2장"),
        ]
        result = detect_schedule(rows)
        assert result is NT_DATES

    def test_둘_다_해당__성경일독_우선(self):
        rows = [
            ("user1", "창세기 1장"),
            ("user2", "출애굽기 2장"),
            ("user3", "마태복음 3장"),
            ("user4", "마가복음 4장"),
        ]
        result = detect_schedule(rows)
        assert result is BIBLE_DATES

    def test_둘_다_미해당__None_반환(self):
        rows = [
            ("user1", "안녕하세요"),
            ("user2", "2/2 😀"),
        ]
        result = detect_schedule(rows)
        assert result is None

    def test_창세기만__미해당(self):
        rows = [
            ("user1", "창세기 1장"),
        ]
        result = detect_schedule(rows)
        assert result is None

    def test_마태복음만__미해당(self):
        rows = [
            ("user1", "마태복음 1장"),
        ]
        result = detect_schedule(rows)
        assert result is None

    def test_빈_rows__None_반환(self):
        result = detect_schedule([])
        assert result is None
