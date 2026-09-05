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
    KST,
    current_part,
    detect_schedule,
    get_part_books,
    get_part_schedule,
    get_schedule_start,
    resolve_part,
    today_kst,
    without_future,
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

    def test_get_part_books__파트별_권_목록(self):
        assert get_part_books("bible", 1)[0] == "창세기"
        assert get_part_books("nt", 1)[0] == "마태복음"
        assert get_part_books("unknown", 1) == ()


class TestDetectSchedule:
    def test_성경일독_키워드_감지(self):
        rows = [
            ("user1", "창세기 1장 읽었습니다"),
            ("user2", "출애굽기 3장 완료"),
        ]
        result = detect_schedule(rows, part=1)
        assert result is BIBLE_PART_DATES[0]

    def test_신약일독_키워드_감지(self):
        rows = [
            ("user1", "마태복음 1장"),
            ("user2", "마가복음 2장"),
        ]
        result = detect_schedule(rows, part=1)
        assert result is NT_PART_DATES[0]

    def test_둘_다_해당__성경일독_우선(self):
        rows = [
            ("user1", "창세기 1장"),
            ("user2", "출애굽기 2장"),
            ("user3", "마태복음 3장"),
            ("user4", "마가복음 4장"),
        ]
        result = detect_schedule(rows, part=1)
        assert result is BIBLE_PART_DATES[0]

    def test_날짜만_있고_책키워드_없음__날짜로_파트_감지(self):
        # 더 안정적: 책 키워드 없어도 날짜 분포로 PART 결정
        rows = [
            ("user1", "안녕하세요"),
            ("user2", "2/2 😀"),
        ]
        result = detect_schedule(rows, part=1)
        assert result is BIBLE_PART_DATES[0]

    def test_날짜와_책키워드_모두_없음__None_반환(self):
        rows = [
            ("user1", "안녕하세요"),
            ("user2", "그냥 메시지"),
        ]
        result = detect_schedule(rows, part=1)
        assert result is None

    def test_창세기만__성경일독_감지(self):
        rows = [
            ("user1", "창세기 1장"),
        ]
        result = detect_schedule(rows, part=1)
        assert result is BIBLE_PART_DATES[0]

    def test_마태복음만__신약일독_감지(self):
        rows = [
            ("user1", "마태복음 1장"),
        ]
        result = detect_schedule(rows, part=1)
        assert result is NT_PART_DATES[0]

    def test_빈_rows__None_반환(self):
        result = detect_schedule([], part=1)
        assert result is None


class TestCurrentPart:
    def test_파트1_기간(self):
        assert current_part(datetime.date(2026, 2, 2)) == 1
        assert current_part(datetime.date(2026, 5, 30)) == 1

    def test_파트2_기간(self):
        assert current_part(datetime.date(2026, 6, 8)) == 2
        assert current_part(datetime.date(2026, 9, 5)) == 2

    def test_파트3_기간(self):
        assert current_part(datetime.date(2026, 10, 5)) == 3
        assert current_part(datetime.date(2026, 12, 19)) == 3

    def test_파트_간_쉬는_기간__직전_파트_유지(self):
        # 5/31~6/7은 PART 1 종료 후 PART 2 시작 전
        assert current_part(datetime.date(2026, 6, 1)) == 1
        # 9/27~10/4는 PART 2 종료 후 PART 3 시작 전
        assert current_part(datetime.date(2026, 9, 30)) == 2

    def test_첫_파트_시작_전__파트1(self):
        assert current_part(datetime.date(2026, 1, 15)) == 1

    def test_전체_종료_후__파트3_유지(self):
        assert current_part(datetime.date(2026, 12, 31)) == 3


class TestTodayKst:
    def test_UTC_밤_시간대__한국은_다음날(self):
        # UTC 2026-09-05 15:10 = KST 2026-09-06 00:10
        utc_now = datetime.datetime(2026, 9, 5, 15, 10, tzinfo=datetime.timezone.utc)

        assert utc_now.astimezone(KST).date() == datetime.date(2026, 9, 6)

    def test_오늘_날짜__KST_기준(self):
        expected = datetime.datetime.now(KST).date()

        assert today_kst() == expected


class TestResolvePart:
    def test_명시된_파트_우선(self):
        assert resolve_part(1, today=datetime.date(2026, 9, 5)) == 1
        assert resolve_part("3", today=datetime.date(2026, 9, 5)) == 3

    def test_미지정__오늘_기준_파트(self):
        assert resolve_part(None, today=datetime.date(2026, 9, 5)) == 2
        assert resolve_part("", today=datetime.date(2026, 3, 1)) == 1

    def test_범위_밖_값__오늘_기준_파트(self):
        assert resolve_part(0, today=datetime.date(2026, 9, 5)) == 2
        assert resolve_part(4, today=datetime.date(2026, 9, 5)) == 2


class TestDetectScheduleUsesRequestedPart:
    def test_파트1_인증만_있어도_요청_파트2_진도표(self):
        # PART 1부터 이어온 방: 과거 인증이 더 많아도 요청 파트를 따른다
        rows = [("u", "2/2🍉"), ("u", "3/15🍉"), ("u", "6/8🍉")]
        assert detect_schedule(rows, part=2) is BIBLE_PART_DATES[1]

    def test_파트_미지정__오늘_기준_파트(self):
        rows = [("u", "2/2🍉"), ("u", "3/15🍉")]
        expected = BIBLE_PART_DATES[current_part() - 1]
        assert detect_schedule(rows) is expected


class TestDetectSchedulePerPart:
    def test_파트2_성경일독_감지(self):
        rows = [("u", "시편 1편 6/8🍉"), ("u", "잠언 6/9🍉")]
        result = detect_schedule(rows, part=2)
        assert result is BIBLE_PART_DATES[1]

    def test_파트2_신약일독_감지(self):
        rows = [("u", "사도행전 6/8🍉"), ("u", "로마서 6/9🍉")]
        result = detect_schedule(rows, part=2)
        assert result is NT_PART_DATES[1]

    def test_파트3_성경일독_기본(self):
        # P3 성경일독은 마태복음~요한계시록을 읽음 — 신약 일독과 책이 겹치지만
        # bible 전용 키워드(P3에는 없음)도 nt 전용 키워드(빌립보서 이후)도 보이지 않으면
        # bible 기본값
        rows = [("u", "마태복음 1장 10/5🍉"), ("u", "10/6🍉")]
        result = detect_schedule(rows, part=3)
        assert result is BIBLE_PART_DATES[2]

    def test_파트3_신약일독은_키워드만으로_구분_불가__bible_기본(self):
        # P3 성경일독·신약일독은 같은 책(빌립보서~요한계시록)을 읽으므로
        # 키워드만으로는 트랙 구분 불가 — 안전하게 bible 기본
        rows = [("u", "빌립보서 10/5🍉"), ("u", "디모데전서 10/6🍉")]
        result = detect_schedule(rows, part=3)
        assert result is BIBLE_PART_DATES[2]


class TestDetectScheduleTrackByHitCount:
    def test_신약일독_방에_성경일독_안내_한_건__신약일독_유지(self):
        # 방을 잘못 찾아 들어온 성경일독 안내 한 건이 트랙을 뒤집으면 안 된다
        rows = [("리더", f"사도행전 {n}장") for n in range(1, 21)]
        rows.append(("리더", "🗓️ 9/3 에스겔 21-24"))

        assert detect_schedule(rows, part=2) is NT_PART_DATES[1]

    def test_성경일독_방에_신약일독_안내_한_건__성경일독_유지(self):
        rows = [("리더", f"이사야 {n}장") for n in range(1, 21)]
        rows.append(("리더", "🍯 9/3 고린도후서 9"))

        assert detect_schedule(rows, part=2) is BIBLE_PART_DATES[1]

    def test_동점__성경일독_기본(self):
        rows = [("u", "시편 1편"), ("u", "사도행전 1장")]

        assert detect_schedule(rows, part=2) is BIBLE_PART_DATES[1]


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


class TestWithoutFuture:
    def test_오늘_이후_날짜_제외(self):
        schedule = frozenset({"6/8", "9/4", "9/5", "9/11", "9/12"})

        result = without_future(schedule, today=datetime.date(2026, 9, 5))

        assert result == frozenset({"6/8", "9/4", "9/5"})

    def test_오늘_날짜는_포함(self):
        result = without_future(frozenset({"9/5"}), today=datetime.date(2026, 9, 5))

        assert result == frozenset({"9/5"})

    def test_전부_과거__그대로_유지(self):
        schedule = frozenset({"2/2", "3/15", "5/30"})

        result = without_future(schedule, today=datetime.date(2026, 9, 5))

        assert result == schedule

    def test_None__None_반환(self):
        assert without_future(None, today=datetime.date(2026, 9, 5)) is None

    def test_진도표_상수는_변경되지_않음(self):
        before = set(BIBLE_PART_DATES[1])

        without_future(BIBLE_PART_DATES[1], today=datetime.date(2026, 9, 5))

        assert set(BIBLE_PART_DATES[1]) == before
