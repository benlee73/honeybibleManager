import pytest

from app.image_builder import _compute_stats, build_output_image


class TestComputeStats:
    def test_single_모드_기본_통계(self):
        headers = ["이름", "이모티콘", "2/2", "2/3", "2/4"]
        rows = [
            ["user1", "😀", "O", "O", "O"],
            ["user2", "🔥", "O", "", "O"],
        ]
        stats = _compute_stats(headers, rows, "single")
        assert stats["members"] == 2
        assert stats["dates"] == 3
        assert stats["perfect_count"] == 1  # user1만 완독
        assert stats["avg_rate"] == 83  # 5/6 = 83%

    def test_dual_모드_기본_통계(self):
        headers = ["이름", "이모티콘", "트랙", "2/2", "2/3"]
        rows = [
            ["user1", "😀", "구약", "O", "O"],
            ["user1", "😀", "신약", "O", ""],
        ]
        stats = _compute_stats(headers, rows, "dual")
        assert stats["members"] == 1
        assert stats["dates"] == 2
        assert stats["perfect_count"] == 1  # 구약 완독
        assert stats["avg_rate"] == 75  # 3/4

    def test_빈_데이터(self):
        headers = ["이름", "이모티콘"]
        rows = []
        stats = _compute_stats(headers, rows, "single")
        assert stats["members"] == 0
        assert stats["dates"] == 0
        assert stats["avg_rate"] == 0
        assert stats["perfect_count"] == 0

    def test_완독자_없음(self):
        headers = ["이름", "이모티콘", "2/2", "2/3"]
        rows = [
            ["user1", "😀", "O", ""],
            ["user2", "🔥", "", "O"],
        ]
        stats = _compute_stats(headers, rows, "single")
        assert stats["perfect_count"] == 0

    def test_dual_모드_완독자_구약_기준(self):
        headers = ["이름", "이모티콘", "트랙", "2/2"]
        rows = [
            ["user1", "😀", "구약", "O"],
            ["user1", "😀", "신약", ""],
        ]
        stats = _compute_stats(headers, rows, "dual")
        # 구약 완독 = 1명
        assert stats["perfect_count"] == 1


class TestBuildOutputImage:
    def test_single_모드__PNG_매직바이트(self):
        users = {
            "user1": {"dates": {"3/15", "3/16"}, "emoji": "😀"},
            "user2": {"dates": {"3/15"}, "emoji": "🔥"},
        }
        result = build_output_image(users, track_mode="single")
        assert isinstance(result, bytes)
        # PNG 매직바이트: \x89PNG\r\n\x1a\n
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

    def test_dual_모드__PNG_매직바이트(self):
        users = {
            "user1": {"dates_old": {"2/2"}, "dates_new": {"2/3"}, "emoji": "😀"},
        }
        result = build_output_image(users, track_mode="dual")
        assert isinstance(result, bytes)
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

    def test_이미지_크기_적정성(self):
        from PIL import Image
        import io

        users = {
            "user1": {"dates": {"3/15"}, "emoji": "😀"},
        }
        result = build_output_image(users, track_mode="single")
        img = Image.open(io.BytesIO(result))
        # 최소 크기 확인
        assert img.width >= 200
        assert img.height >= 100

    def test_dual_모드_이미지_높이가_single보다_큼(self):
        from PIL import Image
        import io

        users_single = {
            "user1": {"dates": {"2/2", "2/3"}, "emoji": "😀"},
        }
        users_dual = {
            "user1": {"dates_old": {"2/2", "2/3"}, "dates_new": {"2/2", "2/3"}, "emoji": "😀"},
        }
        single_bytes = build_output_image(users_single, track_mode="single")
        dual_bytes = build_output_image(users_dual, track_mode="dual")

        single_img = Image.open(io.BytesIO(single_bytes))
        dual_img = Image.open(io.BytesIO(dual_bytes))

        assert dual_img.height > single_img.height

    def test_빈_사용자__에러_없이_생성(self):
        result = build_output_image({}, track_mode="single")
        assert isinstance(result, bytes)
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

    def test_빈_사용자_dual__에러_없이_생성(self):
        result = build_output_image({}, track_mode="dual")
        assert isinstance(result, bytes)
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

    def test_텍스트_이모티콘__에러_없이_생성(self):
        users = {
            "user1": {"dates": {"2/2"}, "emoji": "(무표정)"},
        }
        result = build_output_image(users, track_mode="single")
        assert isinstance(result, bytes)
        assert len(result) > 0
