from openpyxl import Workbook

from app.analytics import (
    GROUP_ALL,
    GROUP_BIBLE,
    GROUP_DUAL,
    GROUP_NT,
    add_analysis_sheet,
    activity_trend,
    build_merged_analysis_records,
    build_output_analysis_records,
    dedupe_record_count,
    dropout_distribution,
    dual_record_count,
    progress_distribution,
    summarize_records,
)
from app.schedule import BIBLE_PART_DATES, NT_PART_DATES


def test_single_성경일독_분석_레코드__완독_하차_미시작_분류():
    partial_dates = {"2/2", "2/3"}
    users = {
        "complete": {"dates": set(BIBLE_PART_DATES[0]), "emoji": "😀"},
        "partial": {"dates": partial_dates, "emoji": "🔥"},
        "none": {"dates": set(), "emoji": ""},
    }

    records = build_output_analysis_records(users, meta={"schedule_type": "bible", "part": 1})
    by_name = {record.name: record for record in records}

    assert by_name["complete"].complete is True
    assert by_name["complete"].status == "완독"
    assert by_name["partial"].status == "하차 추정"
    assert by_name["partial"].last_date == "2/3"
    assert "부근" in by_name["partial"].last_position
    assert by_name["none"].status == "미시작"


def test_dual_분석_레코드__투트랙을_한명으로_계산():
    users = {
        "dual": {
            "dates_old": {"2/2", "2/3"},
            "dates_new": {"2/2"},
            "emoji": "😀",
        },
    }

    records = build_output_analysis_records(users, track_mode="dual", meta={"part": 1})
    assert len(records) == 1
    record = records[0]
    assert record.group == GROUP_DUAL
    assert record.read_count == 3
    assert record.expected_count == len(BIBLE_PART_DATES[0]) + len(NT_PART_DATES[0])
    assert record.complete is False
    assert record.status == "하차 추정"

    summary = {row["group"]: row for row in summarize_records(records)}
    assert dual_record_count(records) == 1
    assert summary[GROUP_ALL]["total"] == 1
    assert summary[GROUP_DUAL]["total"] == 1


def test_merged_분석_레코드__전체와_3개_그룹_요약():
    bible_users = {
        "bible": {"dates": set(BIBLE_PART_DATES[0]), "emoji": "😀", "leader": "방장A"},
    }
    nt_users = {
        "nt": {"dates": {"2/2"}, "emoji": "🔥", "leader": "방장B"},
    }
    dual_users = {
        "dual": {"dates_old": {"2/2"}, "dates_new": {"2/2"}, "emoji": "✨", "leader": "방장C"},
    }

    records = build_merged_analysis_records(bible_users, nt_users, dual_users, part=1)
    summary = {row["group"]: row for row in summarize_records(records)}

    assert summary[GROUP_ALL]["total"] == 3
    assert summary[GROUP_BIBLE]["complete"] == 1
    assert summary[GROUP_DUAL]["total"] == 1
    assert summary[GROUP_DUAL]["dropout"] == 1


def test_merged_분석_레코드__교육국_dedupe_대상_이름만_중복_카운트하지_않음():
    bible_users = {
        "담당자": {"dates": {"2/2", "2/3"}, "emoji": "😀", "leader": "방장A"},
    }
    nt_users = {
        "담당자": {"dates": {"2/2"}, "emoji": "😀", "leader": "방장B"},
    }

    records = build_merged_analysis_records(
        bible_users,
        nt_users,
        {},
        part=1,
        dedupe_names={"담당자"},
    )
    summary = {row["group"]: row for row in summarize_records(records)}

    assert dedupe_record_count(records, dedupe_names={"담당자"}) == 1
    assert len(records) == 1
    assert summary[GROUP_ALL]["total"] == 1


def test_merged_분석_레코드__일반_동명이인은_각각_카운트():
    bible_users = {
        "동명이인": {"dates": {"2/2", "2/3"}, "emoji": "😀", "leader": "방장A"},
    }
    nt_users = {
        "동명이인": {"dates": {"2/2"}, "emoji": "🔥", "leader": "방장B"},
    }

    records = build_merged_analysis_records(bible_users, nt_users, {}, part=1)
    summary = {row["group"]: row for row in summarize_records(records)}

    assert len(records) == 2
    assert summary[GROUP_ALL]["total"] == 2
    assert summary[GROUP_BIBLE]["total"] == 1
    assert summary[GROUP_NT]["total"] == 1


def test_진행률_분포와_하차_분포():
    users = {
        "complete": {"dates": set(BIBLE_PART_DATES[0]), "emoji": "😀"},
        "partial": {"dates": {"2/2", "2/3"}, "emoji": "🔥"},
        "none": {"dates": set(), "emoji": ""},
    }
    records = build_output_analysis_records(users, meta={"schedule_type": "bible", "part": 1})

    progress = {row["bucket"]: row for row in progress_distribution(records)}
    assert progress["0%"][GROUP_ALL] == 1
    assert progress["1~25%"][GROUP_ALL] == 1
    assert progress["100%"][GROUP_ALL] == 1

    dropout = dropout_distribution(records)
    assert len(dropout) == 1
    assert dropout[0]["week"] == "2/2~2/8"
    assert dropout[0]["date"] == "2/3"
    assert "2/2~2/8 |" in dropout[0]["label"]
    assert dropout[0]["count"] == 1
    assert dropout[0]["names"] == "partial"


def test_하차_분포__같은_주는_하나로_묶음():
    users = {
        "user1": {"dates": {"2/2", "2/3"}, "emoji": "😀"},
        "user2": {"dates": {"2/2", "2/4"}, "emoji": "🔥"},
    }
    records = build_output_analysis_records(users, meta={"schedule_type": "bible", "part": 1})

    dropout = dropout_distribution(records)
    assert len(dropout) == 1
    assert dropout[0]["week"] == "2/2~2/8"
    assert dropout[0]["date"] == "2/3, 2/4"
    assert dropout[0]["count"] == 2
    assert dropout[0]["names"] == "user1, user2"


def test_날짜별_인증_추이__사용자별_일자_집계():
    users = {
        "user1": {"dates": {"2/2", "2/3"}, "emoji": "😀"},
        "user2": {"dates": {"2/3"}, "emoji": "🔥"},
    }
    records = build_output_analysis_records(users, meta={"schedule_type": "bible", "part": 1})

    trend = {row["date"]: row["count"] for row in activity_trend(records)}
    assert trend == {"2/2": 1, "2/3": 2}


def test_add_analysis_sheet__표와_차트_생성():
    users = {
        "complete": {"dates": set(BIBLE_PART_DATES[0]), "emoji": "😀"},
        "partial": {"dates": {"2/2", "2/3"}, "emoji": "🔥"},
    }
    records = build_output_analysis_records(users, meta={"schedule_type": "bible", "part": 1})

    wb = Workbook()
    ws = add_analysis_sheet(wb, records)

    assert ws.title == "분석결과"
    assert ws.cell(2, 2).value == "분석결과"
    assert ws.cell(5, 2).value == "그룹"
    assert ws.cell(6, 2).value == "전체"
    assert ws.cell(23, 2).value == "하차 주"
    assert ws.cell(24, 2).value == "2/2~2/8"
    assert "|" not in ws.cell(24, 2).value
    assert ws.cell(24, 4).alignment.wrap_text is True
    assert ws.cell(24, 4).alignment.horizontal == "left"
    assert ws.cell(24, 6).alignment.wrap_text is True
    assert ws.cell(24, 6).alignment.horizontal == "left"
    assert ws.column_dimensions["F"].width >= 40
    assert len(ws._charts) >= 3
