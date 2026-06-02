"""분석결과 시트 생성 및 진행 통계 계산."""

import datetime
from dataclasses import dataclass
from statistics import median

from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from app.completion import expected_dates, is_complete, normalize_part, single_track_for_user
from app.schedule import get_part_books
from app.style_constants import COL_PAD, ROW_PAD

GROUP_ALL = "전체"
GROUP_BIBLE = "성경일독"
GROUP_NT = "신약일독"
GROUP_DUAL = "투트랙"
GROUPS = [GROUP_ALL, GROUP_BIBLE, GROUP_NT, GROUP_DUAL]

PROGRESS_BUCKETS = ["0%", "1~25%", "26~50%", "51~75%", "76~99%", "100%"]


@dataclass(frozen=True)
class AnalysisRecord:
    group: str
    name: str
    emoji: str
    leader: str
    read_count: int
    expected_count: int
    complete: bool
    last_date: str
    last_track: str
    last_position: str
    status: str
    activity_dates: frozenset

    @property
    def progress_rate(self):
        if self.expected_count == 0:
            return 0.0
        return min(1.0, self.read_count / self.expected_count)


def _date_key(value):
    try:
        month, day = str(value).split("/")
        return int(month), int(day)
    except (ValueError, TypeError):
        return 99, 99


def _date_value(value):
    try:
        month, day = str(value).split("/")
        return datetime.date(2026, int(month), int(day))
    except (ValueError, TypeError):
        return None


def _week_bucket(value):
    date_value = _date_value(value)
    if date_value is None:
        return datetime.date(9999, 12, 31), "미확인"
    week_start = date_value - datetime.timedelta(days=date_value.weekday())
    week_end = week_start + datetime.timedelta(days=6)
    return week_start, f"{week_start.month}/{week_start.day}~{week_end.month}/{week_end.day}"


def _sort_dates(dates):
    return sorted((d for d in dates if d), key=_date_key)


def _latest_date(dates):
    sorted_dates = _sort_dates(dates)
    return sorted_dates[-1] if sorted_dates else ""


def _count_valid_dates(dates, expected):
    return len(set(dates or ()) & set(expected or ()))


def _position_for_date(date_value, track, part):
    if not date_value:
        return "미시작"

    expected = _sort_dates(expected_dates(track, part))
    if not expected:
        return "진도 미확인"

    target_key = _date_key(date_value)
    index = None
    for i, expected_date in enumerate(expected):
        if _date_key(expected_date) <= target_key:
            index = i
        else:
            break
    if index is None:
        index = 0

    books = get_part_books("nt" if track == "nt" else "bible", part)
    if not books:
        return f"PART {normalize_part(part)} {index + 1}일차"

    ratio = index / max(1, len(expected) - 1)
    book_index = min(len(books) - 1, int(ratio * len(books)))
    return f"{books[book_index]} 부근"


def _status(read_count, complete):
    if complete:
        return "완독"
    if read_count == 0:
        return "미시작"
    return "하차 추정"


def _single_record(name, data, group, track, part, leader=""):
    expected = expected_dates(track, part)
    dates = set(data.get("dates", set()))
    read_count = _count_valid_dates(dates, expected)
    complete = is_complete(dates, expected)
    last_date = _latest_date(dates)
    return AnalysisRecord(
        group=group,
        name=name,
        emoji=data.get("emoji", ""),
        leader=leader or data.get("leader", ""),
        read_count=read_count,
        expected_count=len(expected),
        complete=complete,
        last_date=last_date,
        last_track=group,
        last_position=_position_for_date(last_date, track, part),
        status=_status(read_count, complete),
        activity_dates=frozenset(dates),
    )


def _dual_record(name, data, part, leader=""):
    old_expected = expected_dates("old", part)
    new_expected = expected_dates("new", part)
    old_dates = set(data.get("dates_old", set()))
    new_dates = set(data.get("dates_new", set()))
    old_read_count = _count_valid_dates(old_dates, old_expected)
    new_read_count = _count_valid_dates(new_dates, new_expected)
    old_complete = is_complete(old_dates, old_expected)
    new_complete = is_complete(new_dates, new_expected)

    old_last = _latest_date(old_dates)
    new_last = _latest_date(new_dates)
    old_key = _date_key(old_last) if old_last else None
    new_key = _date_key(new_last) if new_last else None

    if old_last and new_last and old_key == new_key:
        last_date = old_last
        last_track = "구약/신약"
        last_position = (
            f"구약: {_position_for_date(old_last, 'old', part)} / "
            f"신약: {_position_for_date(new_last, 'new', part)}"
        )
    elif new_last and (not old_last or new_key > old_key):
        last_date = new_last
        last_track = "신약"
        last_position = _position_for_date(new_last, "new", part)
    elif old_last:
        last_date = old_last
        last_track = "구약"
        last_position = _position_for_date(old_last, "old", part)
    else:
        last_date = ""
        last_track = ""
        last_position = "미시작"

    read_count = old_read_count + new_read_count
    complete = old_complete and new_complete
    return AnalysisRecord(
        group=GROUP_DUAL,
        name=name,
        emoji=data.get("emoji", ""),
        leader=leader or data.get("leader", ""),
        read_count=read_count,
        expected_count=len(old_expected) + len(new_expected),
        complete=complete,
        last_date=last_date,
        last_track=last_track,
        last_position=last_position,
        status=_status(read_count, complete),
        activity_dates=frozenset(old_dates | new_dates),
    )


def _dedupe_records(records, dedupe_names=None):
    """지정된 이름만 여러 그룹에 있을 때 대표 레코드 하나로 줄인다."""
    dedupe_names = set(dedupe_names or [])
    priority = {
        GROUP_DUAL: 3,
        GROUP_BIBLE: 2,
        GROUP_NT: 1,
    }

    def score(record):
        return (
            1 if record.complete else 0,
            record.progress_rate,
            record.read_count,
            priority.get(record.group, 0),
        )

    selected = {}
    kept = []
    for record in records:
        if record.name not in dedupe_names:
            kept.append(record)
            continue
        existing = selected.get(record.name)
        if existing is None or score(record) > score(existing):
            selected[record.name] = record
    kept.extend(selected.values())
    return kept


def build_output_analysis_records(users, track_mode="single", meta=None):
    """개별 분석 결과 XLSX용 사용자별 분석 레코드를 생성한다."""
    part = normalize_part((meta or {}).get("part", 1))
    if track_mode == "dual":
        return [
            _dual_record(name, users[name], part)
            for name in sorted(users.keys())
        ]

    schedule_type = (meta or {}).get("schedule_type", "bible")
    records = []
    for name in sorted(users.keys()):
        track = single_track_for_user(name, schedule_type)
        if not track:
            continue
        group = GROUP_NT if track == "nt" else GROUP_BIBLE
        records.append(_single_record(name, users[name], group, track, part))
    return records


def build_merged_analysis_records(bible_users, nt_users, dual_users=None, part=1, dedupe_names=None):
    """통합 XLSX용 사용자별 분석 레코드를 생성한다."""
    part = normalize_part(part)
    records = []

    for name in sorted(bible_users.keys(), key=lambda u: (bible_users[u].get("leader", ""), u)):
        records.append(_single_record(name, bible_users[name], GROUP_BIBLE, "bible", part))

    for name in sorted(nt_users.keys(), key=lambda u: (nt_users[u].get("leader", ""), u)):
        records.append(_single_record(name, nt_users[name], GROUP_NT, "nt", part))

    for name in sorted((dual_users or {}).keys(), key=lambda u: ((dual_users or {})[u].get("leader", ""), u)):
        records.append(_dual_record(name, dual_users[name], part))

    return sorted(_dedupe_records(records, dedupe_names), key=lambda r: (r.group, r.leader, r.name))


def dedupe_record_count(records, dedupe_names=None):
    """지정된 dedupe 대상 기준의 분석 레코드 인원 수를 반환한다."""
    return len(_dedupe_records(records, dedupe_names))


def dual_record_count(records):
    """투트랙 분석 레코드 수를 반환한다."""
    return sum(1 for record in records if record.group == GROUP_DUAL)


def summarize_records(records):
    """전체/그룹별 요약 행을 생성한다."""
    summary = []
    for group in GROUPS:
        selected = list(records) if group == GROUP_ALL else [r for r in records if r.group == group]
        total = len(selected)
        complete_count = sum(1 for r in selected if r.complete)
        not_started = sum(1 for r in selected if r.status == "미시작")
        dropout = sum(1 for r in selected if r.status == "하차 추정")
        rates = [r.progress_rate for r in selected]
        avg_rate = sum(rates) / total if total else 0.0
        median_rate = median(rates) if rates else 0.0
        summary.append({
            "group": group,
            "total": total,
            "complete": complete_count,
            "complete_rate": complete_count / total if total else 0.0,
            "avg_progress": avg_rate,
            "median_progress": median_rate,
            "not_started": not_started,
            "dropout": dropout,
        })
    return summary


def _bucket_for_rate(rate):
    if rate <= 0:
        return "0%"
    if rate >= 1:
        return "100%"
    percent = rate * 100
    if percent <= 25:
        return "1~25%"
    if percent <= 50:
        return "26~50%"
    if percent <= 75:
        return "51~75%"
    return "76~99%"


def progress_distribution(records):
    """진행률 구간별 인원 분포를 반환한다."""
    rows = []
    for bucket in PROGRESS_BUCKETS:
        row = {"bucket": bucket}
        for group in GROUPS:
            selected = records if group == GROUP_ALL else [r for r in records if r.group == group]
            row[group] = sum(1 for r in selected if _bucket_for_rate(r.progress_rate) == bucket)
        rows.append(row)
    return rows


def dropout_distribution(records, group=GROUP_ALL):
    """하차 추정자의 마지막 인증 주+진행 위치 분포를 반환한다."""
    selected = records if group == GROUP_ALL else [r for r in records if r.group == group]
    buckets = {}
    for record in selected:
        if record.status != "하차 추정":
            continue
        week_start, week_label = _week_bucket(record.last_date)
        key = (week_start, week_label, record.last_position)
        item = buckets.setdefault(key, {
            "week_start": week_start,
            "week": week_label,
            "position": record.last_position,
            "last_dates": set(),
            "names": [],
        })
        item["last_dates"].add(record.last_date)
        item["names"].append(record.name)

    rows = []
    for (_, week_label, position), item in sorted(buckets.items(), key=lambda entry: entry[0][0]):
        last_dates = _sort_dates(item["last_dates"])
        rows.append({
            "label": f"{week_label} | {position}",
            "week": week_label,
            "date": ", ".join(last_dates),
            "position": position,
            "count": len(item["names"]),
            "names": ", ".join(sorted(item["names"])),
        })
    return rows


def activity_trend(records, group=GROUP_ALL):
    """날짜별 인증 인원 추이를 반환한다."""
    selected = records if group == GROUP_ALL else [r for r in records if r.group == group]
    all_dates = set()
    for record in selected:
        all_dates.update(record.activity_dates)

    rows = []
    for date_value in _sort_dates(all_dates):
        rows.append({
            "date": date_value,
            "count": sum(1 for r in selected if date_value in r.activity_dates),
        })
    return rows


def detail_rows(records):
    """상세 명단 행을 반환한다."""
    rows = []
    for record in sorted(records, key=lambda r: (r.group, r.leader, r.name)):
        rows.append([
            record.group,
            record.leader,
            record.name,
            record.emoji,
            record.progress_rate,
            record.read_count,
            record.expected_count,
            record.last_date,
            record.last_track,
            record.last_position,
            record.status,
        ])
    return rows


def _style_table(ws, start_row, start_col, headers, rows, percent_cols=None):
    header_fill = PatternFill(start_color="D6E4F0", end_color="D6E4F0", fill_type="solid")
    thin = Side(style="thin")
    border = Border(top=thin, bottom=thin, left=thin, right=thin)
    center = Alignment(horizontal="center", vertical="center")
    percent_cols = set(percent_cols or [])

    for col_offset, header in enumerate(headers):
        cell = ws.cell(start_row, start_col + col_offset, header)
        cell.fill = header_fill
        cell.font = Font(name="맑은 고딕", size=11)
        cell.alignment = center
        cell.border = border

    for row_offset, row in enumerate(rows, start=1):
        for col_offset, value in enumerate(row):
            cell = ws.cell(start_row + row_offset, start_col + col_offset, value)
            cell.font = Font(name="맑은 고딕", size=11)
            cell.alignment = center
            cell.border = border
            if col_offset in percent_cols:
                cell.number_format = "0.0%"


def _section_title(ws, row, col, title):
    cell = ws.cell(row, col, title)
    cell.font = Font(name="맑은 고딕", size=13, bold=True)
    cell.fill = PatternFill(start_color="BDD7EE", end_color="BDD7EE", fill_type="solid")
    cell.alignment = Alignment(horizontal="center", vertical="center")


def _set_widths(ws):
    widths = {
        "A": 2,
        "B": 14,
        "C": 12,
        "D": 16,
        "E": 10,
        "F": 12,
        "G": 12,
        "H": 12,
        "I": 14,
        "J": 20,
        "K": 14,
        "L": 26,
    }
    for col, width in widths.items():
        ws.column_dimensions[col].width = width
    ws.row_dimensions[1].height = 6


def add_analysis_sheet(wb, records):
    """Workbook에 분석결과 시트를 추가한다."""
    ws = wb.create_sheet(title="분석결과")
    _set_widths(ws)

    R = ROW_PAD
    C = COL_PAD
    row = 1 + R
    col = 1 + C

    ws.merge_cells(start_row=row, start_column=col, end_row=row, end_column=col + 10)
    title_cell = ws.cell(row, col, "분석결과")
    title_cell.font = Font(name="맑은 고딕", size=20)
    title_cell.fill = PatternFill(start_color="D6E4F0", end_color="D6E4F0", fill_type="solid")
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[row].height = 42

    row += 2
    _section_title(ws, row, col, "요약")
    summary_headers = ["그룹", "전체 인원", "완독자", "완독률", "평균 진행률", "중앙 진행률", "미시작", "하차 추정"]
    summary_rows = [
        [
            item["group"],
            item["total"],
            item["complete"],
            item["complete_rate"],
            item["avg_progress"],
            item["median_progress"],
            item["not_started"],
            item["dropout"],
        ]
        for item in summarize_records(records)
    ]
    _style_table(ws, row + 1, col, summary_headers, summary_rows, percent_cols={3, 4, 5})

    row += len(summary_rows) + 4
    _section_title(ws, row, col, "진행률 구간 분포")
    distribution = progress_distribution(records)
    dist_headers = ["구간"] + GROUPS
    dist_rows = [[item["bucket"]] + [item[group] for group in GROUPS] for item in distribution]
    dist_table_row = row + 1
    _style_table(ws, dist_table_row, col, dist_headers, dist_rows)

    chart = BarChart()
    chart.title = "진행률 구간 분포"
    chart.y_axis.title = "인원"
    chart.x_axis.title = "진행률"
    data = Reference(ws, min_col=col + 1, max_col=col + len(GROUPS),
                     min_row=dist_table_row, max_row=dist_table_row + len(dist_rows))
    categories = Reference(ws, min_col=col, min_row=dist_table_row + 1,
                           max_row=dist_table_row + len(dist_rows))
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(categories)
    chart.height = 7
    chart.width = 16
    ws.add_chart(chart, "H11")

    row += len(dist_rows) + 4
    _section_title(ws, row, col, "하차 추정 분포")
    dropout_rows_data = dropout_distribution(records)
    dropout_headers = ["하차 주/위치", "마지막 인증일", "진행 위치", "하차 추정 인원", "이름"]
    dropout_rows = [
        [item["label"], item["date"], item["position"], item["count"], item["names"]]
        for item in dropout_rows_data
    ]
    if not dropout_rows:
        dropout_rows = [["-", "-", "하차 추정 없음", 0, ""]]
    dropout_table_row = row + 1
    _style_table(ws, dropout_table_row, col, dropout_headers, dropout_rows)

    if any(row_data[3] for row_data in dropout_rows):
        chart = BarChart()
        chart.title = "하차 추정 분포"
        chart.y_axis.title = "인원"
        chart.x_axis.title = "마지막 인증 위치"
        data = Reference(ws, min_col=col + 3, min_row=dropout_table_row,
                         max_row=dropout_table_row + len(dropout_rows))
        categories = Reference(ws, min_col=col, min_row=dropout_table_row + 1,
                               max_row=dropout_table_row + len(dropout_rows))
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(categories)
        chart.height = 7
        chart.width = 16
        ws.add_chart(chart, "H25")

    row += len(dropout_rows) + 4
    _section_title(ws, row, col, "날짜별 인증 인원 추이")
    trend = activity_trend(records)
    trend_headers = ["날짜", "인증 인원"]
    trend_rows = [[item["date"], item["count"]] for item in trend] or [["-", 0]]
    trend_table_row = row + 1
    _style_table(ws, trend_table_row, col, trend_headers, trend_rows)

    if any(row_data[1] for row_data in trend_rows):
        chart = LineChart()
        chart.title = "날짜별 인증 인원 추이"
        chart.y_axis.title = "인원"
        chart.x_axis.title = "날짜"
        data = Reference(ws, min_col=col + 1, min_row=trend_table_row,
                         max_row=trend_table_row + len(trend_rows))
        categories = Reference(ws, min_col=col, min_row=trend_table_row + 1,
                               max_row=trend_table_row + len(trend_rows))
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(categories)
        chart.height = 7
        chart.width = 16
        ws.add_chart(chart, "H39")

    row += len(trend_rows) + 4
    _section_title(ws, row, col, "상세 명단")
    detail_headers = [
        "그룹", "담당", "이름", "이모티콘", "진행률", "인증일수", "전체일수",
        "마지막 인증일", "마지막 트랙", "마지막 위치", "상태",
    ]
    _style_table(ws, row + 1, col, detail_headers, detail_rows(records), percent_cols={4})

    ws.freeze_panes = "B3"
    return ws
