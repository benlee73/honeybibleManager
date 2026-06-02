import datetime

import pytest

from app.schedule import (
    BIBLE_DATES,
    BIBLE_PART_DATES,
    NT_DATES,
    NT_PART_DATES,
    _BIBLE_RANGES,
    _NT_RANGES,
    _generate_dates,
    detect_part,
    detect_schedule,
    get_part_schedule,
    get_schedule_start,
)


class TestGenerateDates:
    def test_일요일_제외__일요일_날짜_미포함(self):
        # 2026-02-08 = 일요일
        assert "2/8" not in BIBLE_DATES
        assert "2/8" not in NT_DATES

    def test_성경일독__토요일_포함(self):
        # 2026-02-07 = 토요일, 성경일독은 월~토
        assert "2/7" in BIBLE_DATES

    def test_신약일독__토요일_미포함(self):
        # 2026-02-07 = 토요일, 신약일독은 월~금
        assert "2/7" not in NT_DATES

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
        # 신약일독은 월~금(5일)이므로 성경일독(월~토 6일)보다 적음
        assert len(NT_DATES) > 150

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
        assert result is BIBLE_PART_DATES[0]

    def test_신약일독_키워드_감지(self):
        rows = [
            ("user1", "마태복음 1장"),
            ("user2", "마가복음 2장"),
        ]
        result = detect_schedule(rows)
        assert result is NT_PART_DATES[0]

    def test_둘_다_해당__성경일독_우선(self):
        rows = [
            ("user1", "창세기 1장"),
            ("user2", "출애굽기 2장"),
            ("user3", "마태복음 3장"),
            ("user4", "마가복음 4장"),
        ]
        result = detect_schedule(rows)
        assert result is BIBLE_PART_DATES[0]

    def test_날짜만_있고_책키워드_없음__날짜로_파트_감지(self):
        # 더 안정적: 책 키워드 없어도 날짜 분포로 PART 결정
        rows = [
            ("user1", "안녕하세요"),
            ("user2", "2/2 😀"),
        ]
        result = detect_schedule(rows)
        assert result is BIBLE_PART_DATES[0]

    def test_날짜와_책키워드_모두_없음__None_반환(self):
        rows = [
            ("user1", "안녕하세요"),
            ("user2", "그냥 메시지"),
        ]
        result = detect_schedule(rows)
        assert result is None

    def test_창세기만__성경일독_감지(self):
        rows = [
            ("user1", "창세기 1장"),
        ]
        result = detect_schedule(rows)
        assert result is BIBLE_PART_DATES[0]

    def test_마태복음만__신약일독_감지(self):
        rows = [
            ("user1", "마태복음 1장"),
        ]
        result = detect_schedule(rows)
        assert result is NT_PART_DATES[0]

    def test_빈_rows__None_반환(self):
        result = detect_schedule([])
        assert result is None


class TestDetectPart:
    def test_파트1_날짜_감지(self):
        rows = [("u", "2/2🍉"), ("u", "3/15🍉")]
        assert detect_part(rows) == 1

    def test_파트2_날짜_감지(self):
        rows = [("u", "6/8🍉"), ("u", "7/15🍉")]
        assert detect_part(rows) == 2

    def test_파트3_날짜_감지(self):
        rows = [("u", "10/5🍉"), ("u", "11/15🍉")]
        assert detect_part(rows) == 3

    def test_파트_경계_갭_날짜_미카운트(self):
        # 6/1은 P1 종료(5/30) 이후, P2 시작(6/8) 이전 갭
        rows = [("u", "6/1🍉")]
        assert detect_part(rows) is None

    def test_혼재_시_가장_많은_파트(self):
        rows = [("u", "2/2🍉"), ("u", "2/3🍉"), ("u", "11/15🍉")]
        assert detect_part(rows) == 1

    def test_빈_rows__None(self):
        assert detect_part([]) is None


class TestDetectSchedulePerPart:
    def test_파트2_성경일독_감지(self):
        rows = [("u", "시편 1편 6/8🍉"), ("u", "잠언 6/9🍉")]
        result = detect_schedule(rows)
        assert result is BIBLE_PART_DATES[1]

    def test_파트2_신약일독_감지(self):
        rows = [("u", "사도행전 6/8🍉"), ("u", "로마서 6/9🍉")]
        result = detect_schedule(rows)
        assert result is NT_PART_DATES[1]

    def test_파트3_성경일독_기본(self):
        # P3 성경일독은 마태복음~요한계시록을 읽음 — 신약 일독과 책이 겹치지만
        # bible 전용 키워드(P3에는 없음)도 nt 전용 키워드(빌립보서 이후)도 보이지 않으면
        # bible 기본값
        rows = [("u", "마태복음 1장 10/5🍉"), ("u", "10/6🍉")]
        result = detect_schedule(rows)
        assert result is BIBLE_PART_DATES[2]

    def test_파트3_신약일독은_키워드만으로_구분_불가__bible_기본(self):
        # P3 성경일독·신약일독은 같은 책(빌립보서~요한계시록)을 읽으므로
        # 키워드만으로는 트랙 구분 불가 — 안전하게 bible 기본
        rows = [("u", "빌립보서 10/5🍉"), ("u", "디모데전서 10/6🍉")]
        result = detect_schedule(rows)
        assert result is BIBLE_PART_DATES[2]


class TestGetPartSchedule:
    def test_track_part_조합(self):
        assert get_part_schedule("bible", 1) is BIBLE_PART_DATES[0]
        assert get_part_schedule("nt", 2) is NT_PART_DATES[1]
        assert get_part_schedule("bible", 3) is BIBLE_PART_DATES[2]

    def test_잘못된_입력__None(self):
        assert get_part_schedule("invalid", 1) is None
        assert get_part_schedule("bible", 0) is None
        assert get_part_schedule("bible", 4) is None
        assert get_part_schedule("bible", None) is None


class TestGetScheduleStart:
    def test_파트별_시작일(self):
        assert get_schedule_start(BIBLE_PART_DATES[0]) == (2, 2)
        assert get_schedule_start(BIBLE_PART_DATES[1]) == (6, 8)
        assert get_schedule_start(BIBLE_PART_DATES[2]) == (10, 5)
        assert get_schedule_start(NT_PART_DATES[0]) == (2, 2)

    def test_None_입력(self):
        assert get_schedule_start(None) is None
