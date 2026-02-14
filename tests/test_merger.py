import io
import json
import os
from unittest.mock import MagicMock, patch

import pytest
from openpyxl import load_workbook

from app.analyzer import build_output_xlsx
from app.merger import (
    _classify_education_users,
    _extract_room_from_filename,
    _load_education_config,
    build_merged_preview,
    build_merged_xlsx,
    merge_files,
    read_meta_from_xlsx,
    read_users_from_xlsx,
    select_latest_per_room,
)


class TestExtractRoomFromFilename:
    def test_정상_파일명__방이름_추출(self):
        name = "꿀성경_방장_20260210_1050_2026 성경일독 part1.xlsx"
        assert _extract_room_from_filename(name) == "2026 성경일독 part1"

    def test_방이름에_언더스코어__재결합(self):
        name = "꿀성경_방장_20260210_1050_교육국_방.xlsx"
        assert _extract_room_from_filename(name) == "교육국_방"

    def test_패턴_불일치__파일명_그대로(self):
        name = "기타파일.xlsx"
        assert _extract_room_from_filename(name) == "기타파일.xlsx"

    def test_None__None_반환(self):
        assert _extract_room_from_filename(None) is None

    def test_빈_문자열__빈_문자열_반환(self):
        assert _extract_room_from_filename("") == ""

    def test_꿀성경_접두사_없음__파일명_그대로(self):
        name = "결과_방장_20260210_1050_방이름.xlsx"
        assert _extract_room_from_filename(name) == "결과_방장_20260210_1050_방이름.xlsx"

    def test_날짜_형식_불일치__파일명_그대로(self):
        name = "꿀성경_방장_2026_1050_방이름.xlsx"
        assert _extract_room_from_filename(name) == "꿀성경_방장_2026_1050_방이름.xlsx"


class TestSelectLatestPerRoom:
    def test_같은_방_여러_파일__최신만_선택(self):
        files = [
            {"id": "1", "name": "꿀성경_방장_20260210_1050_방1.xlsx", "modifiedTime": "2026-02-10T10:50:00Z"},
            {"id": "2", "name": "꿀성경_방장_20260211_1050_방1.xlsx", "modifiedTime": "2026-02-11T10:50:00Z"},
            {"id": "3", "name": "꿀성경_방장_20260210_1050_방2.xlsx", "modifiedTime": "2026-02-10T10:50:00Z"},
        ]
        result = select_latest_per_room(files)
        assert len(result) == 2
        ids = {f["id"] for f in result}
        assert "2" in ids  # 방1의 최신
        assert "3" in ids  # 방2

    def test_방_하나__그대로(self):
        files = [
            {"id": "1", "name": "꿀성경_방장_20260210_1050_방1.xlsx", "modifiedTime": "2026-02-10T10:50:00Z"},
        ]
        result = select_latest_per_room(files)
        assert len(result) == 1

    def test_빈_리스트__빈_결과(self):
        assert select_latest_per_room([]) == []


class TestReadMetaFromXlsx:
    def test_메타_시트_있음__dict_반환(self):
        users = {"user1": {"dates": {"2/2"}, "emoji": "😀"}}
        meta = {"room_name": "테스트방", "track_mode": "single", "schedule_type": "bible", "leader": "방장"}
        xlsx_bytes = build_output_xlsx(users, track_mode="single", meta=meta)

        result = read_meta_from_xlsx(xlsx_bytes)
        assert result is not None
        assert result["room_name"] == "테스트방"
        assert result["track_mode"] == "single"
        assert result["schedule_type"] == "bible"
        assert result["leader"] == "방장"

    def test_메타_시트_없음__None_반환(self):
        users = {"user1": {"dates": {"2/2"}, "emoji": "😀"}}
        xlsx_bytes = build_output_xlsx(users, track_mode="single")

        result = read_meta_from_xlsx(xlsx_bytes)
        assert result is None

    def test_잘못된_바이트__None_반환(self):
        result = read_meta_from_xlsx(b"not an xlsx file")
        assert result is None


class TestReadUsersFromXlsx:
    def test_single_모드__사용자_데이터_추출(self):
        users = {
            "user1": {"dates": {"2/2", "2/3"}, "emoji": "😀"},
            "user2": {"dates": {"2/2"}, "emoji": "🔥"},
        }
        xlsx_bytes = build_output_xlsx(users, track_mode="single")

        result = read_users_from_xlsx(xlsx_bytes, "single")
        assert "user1" in result
        assert result["user1"]["dates"] == {"2/2", "2/3"}
        assert result["user1"]["emoji"] == "😀"
        assert "user2" in result
        assert result["user2"]["dates"] == {"2/2"}

    def test_dual_모드__사용자_데이터_추출(self):
        users = {
            "user1": {"dates_old": {"2/2"}, "dates_new": {"2/3"}, "emoji": "😀"},
        }
        xlsx_bytes = build_output_xlsx(users, track_mode="dual")

        result = read_users_from_xlsx(xlsx_bytes, "dual")
        assert "user1" in result
        assert result["user1"]["dates_old"] == {"2/2"}
        assert result["user1"]["dates_new"] == {"2/3"}

    def test_빈_xlsx__빈_결과(self):
        users = {}
        xlsx_bytes = build_output_xlsx(users, track_mode="single")

        result = read_users_from_xlsx(xlsx_bytes, "single")
        assert result == {}


class TestClassifyEducationUsers:
    def test_정상_분류(self):
        users = {
            "김철수": {"dates": {"2/2"}, "emoji": "😀"},
            "지혜": {"dates": {"2/3"}, "emoji": "🔥"},
            "찬영": {"dates": {"2/4"}, "emoji": "🎉"},
            "지혁": {"dates": {"2/5"}, "emoji": "💀"},
        }
        config = {"nt_members": ["지혜", "찬영"], "excluded_members": ["지혁"]}

        result = _classify_education_users(users, config)
        assert "김철수" in result["bible"]
        assert "지혜" in result["nt"]
        assert "찬영" in result["nt"]
        assert "지혁" not in result["bible"]
        assert "지혁" not in result["nt"]

    def test_빈_설정__모두_성경일독(self):
        users = {
            "김철수": {"dates": {"2/2"}, "emoji": "😀"},
            "이영희": {"dates": {"2/3"}, "emoji": "🔥"},
        }
        config = {"nt_members": [], "excluded_members": []}

        result = _classify_education_users(users, config)
        assert len(result["bible"]) == 2
        assert len(result["nt"]) == 0

    def test_모두_제외__빈_결과(self):
        users = {
            "지혁": {"dates": {"2/2"}, "emoji": "😀"},
        }
        config = {"nt_members": [], "excluded_members": ["지혁"]}

        result = _classify_education_users(users, config)
        assert len(result["bible"]) == 0
        assert len(result["nt"]) == 0

    def test_부분_일치__닉네임에_키워드_포함(self):
        users = {
            "김철수": {"dates": {"2/2"}, "emoji": "😀"},
            "김지혜": {"dates": {"2/3"}, "emoji": "🔥"},
            "이찬영": {"dates": {"2/4"}, "emoji": "🎉"},
            "박지혁": {"dates": {"2/5"}, "emoji": "💀"},
        }
        config = {"nt_members": ["지혜", "찬영"], "excluded_members": ["지혁"]}

        result = _classify_education_users(users, config)
        assert "김철수" in result["bible"]
        assert "김지혜" in result["nt"]
        assert "이찬영" in result["nt"]
        assert "박지혁" not in result["bible"]
        assert "박지혁" not in result["nt"]


class TestBuildMergedXlsx:
    def test_양쪽_시트_생성(self):
        bible_users = {
            "user1": {"dates": {"2/2", "2/3"}, "emoji": "😀", "leader": "방장A"},
        }
        nt_users = {
            "user2": {"dates": {"2/4"}, "emoji": "🔥", "leader": "방장B"},
        }
        xlsx_bytes = build_merged_xlsx(bible_users, nt_users)
        wb = load_workbook(io.BytesIO(xlsx_bytes))

        assert "성경일독 진도표" in wb.sheetnames
        assert "신약일독 진도표" in wb.sheetnames

    def test_담당_컬럼_포함(self):
        bible_users = {
            "user1": {"dates": {"2/2"}, "emoji": "😀", "leader": "방장A"},
        }
        nt_users = {}
        xlsx_bytes = build_merged_xlsx(bible_users, nt_users)
        wb = load_workbook(io.BytesIO(xlsx_bytes))
        ws = wb["성경일독 진도표"]

        assert ws.cell(1, 1).value == "이름"
        assert ws.cell(1, 2).value == "이모티콘"
        assert ws.cell(1, 3).value == "담당"
        assert ws.cell(2, 1).value == "user1"
        assert ws.cell(2, 3).value == "방장A"

    def test_담당별_정렬(self):
        bible_users = {
            "user_z": {"dates": {"2/2"}, "emoji": "😀", "leader": "방장B"},
            "user_a": {"dates": {"2/2"}, "emoji": "🔥", "leader": "방장A"},
        }
        xlsx_bytes = build_merged_xlsx(bible_users, {})
        wb = load_workbook(io.BytesIO(xlsx_bytes))
        ws = wb["성경일독 진도표"]

        # 방장A가 먼저
        assert ws.cell(2, 3).value == "방장A"
        assert ws.cell(3, 3).value == "방장B"

    def test_빈_사용자__헤더만(self):
        xlsx_bytes = build_merged_xlsx({}, {})
        wb = load_workbook(io.BytesIO(xlsx_bytes))
        ws = wb["성경일독 진도표"]
        assert ws.cell(1, 1).value == "이름"
        assert ws.cell(2, 1).value is None


class TestBuildMergedPreview:
    def test_양쪽_사용자_포함(self):
        bible_users = {
            "user1": {"dates": {"2/2"}, "emoji": "😀", "leader": "방장A"},
        }
        nt_users = {
            "user2": {"dates": {"2/3"}, "emoji": "🔥", "leader": "방장B"},
        }
        headers, rows = build_merged_preview(bible_users, nt_users)

        assert "담당" in headers
        assert "트랙" in headers
        assert len(rows) == 2
        # 첫 행: 성경일독
        assert rows[0][3] == "성경일독"
        # 둘째 행: 신약일독
        assert rows[1][3] == "신약일독"

    def test_빈_사용자__행_없음(self):
        headers, rows = build_merged_preview({}, {})
        assert len(rows) == 0


class TestMergeFiles:
    @patch("app.merger.download_drive_file")
    @patch("app.merger.list_drive_files")
    def test_성경일독_파일_통합(self, mock_list, mock_download):
        # 성경일독 XLSX 생성
        users = {"user1": {"dates": {"2/2", "2/3"}, "emoji": "😀"}}
        meta = {"room_name": "part1", "track_mode": "single", "schedule_type": "bible", "leader": "방장"}
        xlsx_bytes = build_output_xlsx(users, track_mode="single", meta=meta)

        mock_list.return_value = {
            "success": True,
            "files": [{"id": "1", "name": "꿀성경_방장_20260210_1050_part1.xlsx", "modifiedTime": "2026-02-10T10:50:00Z"}],
        }
        mock_download.return_value = {"success": True, "data": xlsx_bytes, "name": "꿀성경_방장_20260210_1050_part1.xlsx"}

        result = merge_files()
        assert result["success"] is True
        assert "user1" in result["bible_users"]
        assert result["bible_users"]["user1"]["dates"] == {"2/2", "2/3"}
        assert len(result["nt_users"]) == 0

    @patch("app.merger.download_drive_file")
    @patch("app.merger.list_drive_files")
    def test_신약일독_파일_통합(self, mock_list, mock_download):
        users = {"user1": {"dates": {"2/2"}, "emoji": "😀"}}
        meta = {"room_name": "nt1", "track_mode": "single", "schedule_type": "nt", "leader": "방장"}
        xlsx_bytes = build_output_xlsx(users, track_mode="single", meta=meta)

        mock_list.return_value = {
            "success": True,
            "files": [{"id": "1", "name": "꿀성경_방장_20260210_1050_nt1.xlsx", "modifiedTime": "2026-02-10T10:50:00Z"}],
        }
        mock_download.return_value = {"success": True, "data": xlsx_bytes, "name": "test.xlsx"}

        result = merge_files()
        assert result["success"] is True
        assert "user1" in result["nt_users"]
        assert len(result["bible_users"]) == 0

    @patch("app.merger.download_drive_file")
    @patch("app.merger.list_drive_files")
    def test_듀얼_파일_양쪽_분배(self, mock_list, mock_download):
        users = {"user1": {"dates_old": {"2/2"}, "dates_new": {"2/3"}, "emoji": "😀"}}
        meta = {"room_name": "dual방", "track_mode": "dual", "schedule_type": "dual", "leader": "방장"}
        xlsx_bytes = build_output_xlsx(users, track_mode="dual", meta=meta)

        mock_list.return_value = {
            "success": True,
            "files": [{"id": "1", "name": "꿀성경_방장_20260210_1050_dual방.xlsx", "modifiedTime": "2026-02-10T10:50:00Z"}],
        }
        mock_download.return_value = {"success": True, "data": xlsx_bytes, "name": "test.xlsx"}

        result = merge_files()
        assert result["success"] is True
        assert "user1" in result["bible_users"]
        assert result["bible_users"]["user1"]["dates"] == {"2/2"}
        assert "user1" in result["nt_users"]
        assert result["nt_users"]["user1"]["dates"] == {"2/3"}

    @patch("app.merger.download_drive_file")
    @patch("app.merger.list_drive_files")
    def test_교육국_파일_분류(self, mock_list, mock_download):
        users = {
            "김철수": {"dates": {"2/2"}, "emoji": "😀"},
            "홍지혜": {"dates": {"2/3"}, "emoji": "🔥"},
            "박지혁": {"dates": {"2/4"}, "emoji": "💀"},
        }
        meta = {"room_name": "교육국", "track_mode": "single", "schedule_type": "education", "leader": "방장"}
        xlsx_bytes = build_output_xlsx(users, track_mode="single", meta=meta)

        mock_list.return_value = {
            "success": True,
            "files": [{"id": "1", "name": "꿀성경_방장_20260210_1050_교육국.xlsx", "modifiedTime": "2026-02-10T10:50:00Z"}],
        }
        mock_download.return_value = {"success": True, "data": xlsx_bytes, "name": "test.xlsx"}

        result = merge_files()
        assert result["success"] is True
        assert "김철수" in result["bible_users"]
        assert "홍지혜" in result["nt_users"]
        assert "박지혁" not in result["bible_users"]
        assert "박지혁" not in result["nt_users"]

    @patch("app.merger.download_drive_file")
    @patch("app.merger.list_drive_files")
    def test_중복_사용자_날짜_합집합(self, mock_list, mock_download):
        # 두 방에 같은 사용자가 있는 경우
        users1 = {"user1": {"dates": {"2/2", "2/3"}, "emoji": "😀"}}
        meta1 = {"room_name": "방1", "track_mode": "single", "schedule_type": "bible", "leader": "방장A"}
        xlsx1 = build_output_xlsx(users1, track_mode="single", meta=meta1)

        users2 = {"user1": {"dates": {"2/3", "2/4"}, "emoji": "😀"}}
        meta2 = {"room_name": "방2", "track_mode": "single", "schedule_type": "bible", "leader": "방장B"}
        xlsx2 = build_output_xlsx(users2, track_mode="single", meta=meta2)

        mock_list.return_value = {
            "success": True,
            "files": [
                {"id": "1", "name": "꿀성경_방장A_20260210_1050_방1.xlsx", "modifiedTime": "2026-02-10T10:50:00Z"},
                {"id": "2", "name": "꿀성경_방장B_20260210_1050_방2.xlsx", "modifiedTime": "2026-02-10T10:50:00Z"},
            ],
        }
        mock_download.side_effect = [
            {"success": True, "data": xlsx1, "name": "test1.xlsx"},
            {"success": True, "data": xlsx2, "name": "test2.xlsx"},
        ]

        result = merge_files()
        assert result["success"] is True
        assert result["bible_users"]["user1"]["dates"] == {"2/2", "2/3", "2/4"}

    @patch("app.merger.list_drive_files")
    def test_Drive_실패__에러_반환(self, mock_list):
        mock_list.return_value = {"success": False, "message": "API 오류"}
        result = merge_files()
        assert result["success"] is False

    @patch("app.merger.download_drive_file")
    @patch("app.merger.list_drive_files")
    def test_메타데이터_없는_파일__스킵(self, mock_list, mock_download):
        # 메타 없는 XLSX
        users = {"user1": {"dates": {"2/2"}, "emoji": "😀"}}
        xlsx_bytes = build_output_xlsx(users, track_mode="single")  # meta 미전달

        mock_list.return_value = {
            "success": True,
            "files": [{"id": "1", "name": "old_file.xlsx", "modifiedTime": "2026-02-10T10:50:00Z"}],
        }
        mock_download.return_value = {"success": True, "data": xlsx_bytes, "name": "old_file.xlsx"}

        result = merge_files()
        assert result["success"] is True
        assert len(result["skipped_files"]) == 1
        assert "메타데이터 없음" in result["skipped_files"][0]["reason"]
