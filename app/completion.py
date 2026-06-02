"""완독자 판정 공통 헬퍼."""

import json
import os
from functools import lru_cache

from app.schedule import BIBLE_PART_DATES, NT_PART_DATES

TRACK_LABELS = {
    "bible": "성경일독",
    "nt": "신약일독",
    "old": "구약",
    "new": "신약",
}

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "education_config.json")


def normalize_part(part):
    """파트 값을 1~3 정수로 정규화한다."""
    try:
        value = int(part)
    except (TypeError, ValueError):
        return 1
    if 1 <= value <= len(BIBLE_PART_DATES):
        return value
    return 1


def expected_dates(track, part=1):
    """트랙/파트에 맞는 고정 완독 기준 날짜 집합을 반환한다."""
    part_idx = normalize_part(part) - 1
    if track in ("bible", "old", "education"):
        return BIBLE_PART_DATES[part_idx]
    if track in ("nt", "new"):
        return NT_PART_DATES[part_idx]
    return frozenset()


def is_complete(dates, expected):
    """인증 날짜가 고정 기준 전체를 포함하면 완독으로 본다."""
    expected_set = set(expected or ())
    return bool(expected_set) and set(dates or ()) >= expected_set


def completion_row(track_label, user, emoji, dates, expected, leader=None):
    """완독자인 경우 완독자 시트 행을 반환한다. 미완독이면 None."""
    if not is_complete(dates, expected):
        return None
    if leader is None:
        return [track_label, user, emoji]
    return [leader, track_label, user, emoji]


@lru_cache(maxsize=1)
def _load_education_config():
    try:
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"nt_members": [], "excluded_members": []}


def single_track_for_user(user, schedule_type):
    """싱글 분석 파일에서 사용자별 완독 기준 트랙을 결정한다."""
    if schedule_type == "nt":
        return "nt"
    if schedule_type == "education":
        config = _load_education_config()
        if any(keyword in user for keyword in config.get("excluded_members", [])):
            return None
        if any(keyword in user for keyword in config.get("nt_members", [])):
            return "nt"
        return "bible"
    return "bible"
