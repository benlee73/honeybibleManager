from app.txt_parser import extract_chat_meta, parse_txt


class TestParseTxt:
    def test_사용자_메시지_파싱(self):
        text = "2026. 2. 2. 오전 7:33, 홍길동 : 2/2🐷\r\n"
        rows = parse_txt(text)
        assert len(rows) == 1
        assert rows[0] == ("홍길동", "2/2🐷")

    def test_시스템_메시지_스킵(self):
        text = (
            "2026. 2. 1. 오후 8:26: 홍길동님이 김철수님을 초대했습니다.\r\n"
            "2026. 2. 2. 오전 7:33, 홍길동 : 2/2🐷\r\n"
        )
        rows = parse_txt(text)
        assert len(rows) == 1
        assert rows[0][0] == "홍길동"

    def test_날짜_헤더_스킵(self):
        text = (
            "2026년 2월 1일 일요일\r\n"
            "2026. 2. 2. 오전 7:33, 홍길동 : 2/2🐷\r\n"
        )
        rows = parse_txt(text)
        assert len(rows) == 1

    def test_파일_헤더_스킵(self):
        text = (
            "Talk_2026.2.10 08:50-1.txt\r\n"
            "저장한 날짜 : 2026. 2. 10. 오후 12:16\r\n"
            "\r\n"
            "2026. 2. 2. 오전 7:33, 홍길동 : 2/2🐷\r\n"
        )
        rows = parse_txt(text)
        assert len(rows) == 1
        assert rows[0] == ("홍길동", "2/2🐷")

    def test_멀티라인_메시지(self):
        text = (
            "2026. 2. 1. 오후 8:29, 홍길동 : 첫줄\r\n"
            "둘째줄\r\n"
            "셋째줄\r\n"
            "2026. 2. 2. 오전 7:33, 김철수 : 단일줄\r\n"
        )
        rows = parse_txt(text)
        assert len(rows) == 2
        assert rows[0] == ("홍길동", "첫줄\n둘째줄\n셋째줄")
        assert rows[1] == ("김철수", "단일줄")

    def test_빈_입력(self):
        assert parse_txt("") == []

    def test_시스템_메시지만_있는_입력(self):
        text = "2026. 2. 1. 오후 8:26: 홍길동님이 방장이 되었습니다.\r\n"
        assert parse_txt(text) == []

    def test_여러_사용자_메시지(self):
        text = (
            "2026. 2. 2. 오전 7:33, 홍길동 : 2/2🐷\r\n"
            "2026. 2. 2. 오전 8:00, 김철수 : 2/2🦊\r\n"
            "2026. 2. 2. 오후 9:00, 이영희 : 2/2❄️\r\n"
        )
        rows = parse_txt(text)
        assert len(rows) == 3
        assert rows[0][0] == "홍길동"
        assert rows[1][0] == "김철수"
        assert rows[2][0] == "이영희"

    def test_공백이름_사용자(self):
        text = "2026. 2. 2. 오전 7:33, 광천 유영훈 : 2/2🐽\r\n"
        rows = parse_txt(text)
        assert rows[0] == ("광천 유영훈", "2/2🐽")

    def test_멀티라인_후_시스템_메시지(self):
        text = (
            "2026. 2. 1. 오후 8:29, 홍길동 : 첫줄\r\n"
            "둘째줄\r\n"
            "2026. 2. 1. 오후 8:30: 시스템 메시지입니다.\r\n"
        )
        rows = parse_txt(text)
        assert len(rows) == 1
        assert rows[0] == ("홍길동", "첫줄\n둘째줄")

    def test_종합_시나리오(self):
        text = (
            "Talk_2026.2.10 08:50-1.txt\r\n"
            "저장한 날짜 : 2026. 2. 10. 오후 12:16\r\n"
            "\r\n"
            "2026년 2월 1일 일요일\r\n"
            "2026. 2. 1. 오후 8:26: 홍길동님이 방장이 되었습니다.\r\n"
            "2026. 2. 1. 오후 8:29, 홍길동 : 공지사항\r\n"
            "여러 줄 안내문\r\n"
            "\r\n"
            "2026년 2월 2일 월요일\r\n"
            "2026. 2. 2. 오전 7:33, 김철수 : 2/2🐷\r\n"
            "2026. 2. 2. 오전 8:00, 이영희 : 2/2🦊\r\n"
        )
        rows = parse_txt(text)
        assert len(rows) == 3
        assert rows[0] == ("홍길동", "공지사항\n여러 줄 안내문")
        assert rows[1] == ("김철수", "2/2🐷")
        assert rows[2] == ("이영희", "2/2🦊")

    def test_LF_줄바꿈_처리(self):
        text = "2026. 2. 2. 오전 7:33, 홍길동 : 2/2🐷\n"
        rows = parse_txt(text)
        assert len(rows) == 1
        assert rows[0] == ("홍길동", "2/2🐷")

    def test_사진_메시지(self):
        text = "2026. 2. 1. 오후 8:37, 홍길동 : 사진\r\n"
        rows = parse_txt(text)
        assert len(rows) == 1
        assert rows[0] == ("홍길동", "사진")


class TestExtractChatMeta:
    def test_정상_헤더__방이름_및_날짜_추출(self):
        text = (
            "꿀성경 - 교육국 님과 카카오톡 대화\r\n"
            "저장한 날짜 : 2026. 2. 9. 오전 10:50\r\n"
            "\r\n"
            "2026년 2월 1일 일요일\r\n"
        )
        meta = extract_chat_meta(text)
        assert meta["room_name"] == "꿀성경 - 교육국"
        assert meta["saved_date"] == "2026/02/09-10:50"

    def test_오후_시간__12시간_변환(self):
        text = (
            "테스트방 님과 카카오톡 대화\r\n"
            "저장한 날짜 : 2026. 2. 10. 오후 3:30\r\n"
        )
        meta = extract_chat_meta(text)
        assert meta["room_name"] == "테스트방"
        assert meta["saved_date"] == "2026/02/10-15:30"

    def test_오후_12시__12유지(self):
        text = (
            "테스트방 님과 카카오톡 대화\r\n"
            "저장한 날짜 : 2026. 2. 10. 오후 12:05\r\n"
        )
        meta = extract_chat_meta(text)
        assert meta["saved_date"] == "2026/02/10-12:05"

    def test_오전_12시__0시_변환(self):
        text = (
            "테스트방 님과 카카오톡 대화\r\n"
            "저장한 날짜 : 2026. 2. 10. 오전 12:30\r\n"
        )
        meta = extract_chat_meta(text)
        assert meta["saved_date"] == "2026/02/10-00:30"

    def test_헤더_없는_텍스트__None_반환(self):
        text = "2026. 2. 2. 오전 7:33, 홍길동 : 2/2🐷\r\n"
        meta = extract_chat_meta(text)
        assert meta["room_name"] is None
        assert meta["saved_date"] is None

    def test_빈_텍스트__None_반환(self):
        meta = extract_chat_meta("")
        assert meta["room_name"] is None
        assert meta["saved_date"] is None

    def test_Talk_헤더_포함__방이름_추출(self):
        text = (
            "Talk_2026.2.10 08:50-1.txt\r\n"
            "저장한 날짜 : 2026. 2. 10. 오후 12:16\r\n"
            "꿀성경 - 교육국 님과 카카오톡 대화\r\n"
        )
        meta = extract_chat_meta(text)
        assert meta["room_name"] == "꿀성경 - 교육국"
        assert meta["saved_date"] == "2026/02/10-12:16"


class TestParseTxtEnglish:
    def test_영문_사용자_메시지_파싱(self):
        text = (
            "Date Saved : Feb 13, 2026 at 18:42\r\n"
            "Feb 1, 2026 at 20:35, 김예슬 : 2/1🐷\r\n"
        )
        rows = parse_txt(text)
        assert len(rows) == 1
        assert rows[0] == ("김예슬", "2/1🐷")

    def test_영문_시스템_메시지_스킵(self):
        text = (
            "Date Saved : Feb 13, 2026 at 18:42\r\n"
            "Feb 1, 2026 at 20:29: 홍길동 invited 김철수.\r\n"
            "Feb 1, 2026 at 20:35, 김예슬 : 2/1🐷\r\n"
        )
        rows = parse_txt(text)
        assert len(rows) == 1
        assert rows[0][0] == "김예슬"

    def test_영문_날짜_헤더_스킵(self):
        text = (
            "Date Saved : Feb 13, 2026 at 18:42\r\n"
            "Sunday, February 1, 2026\r\n"
            "Feb 2, 2026 at 7:33, 홍길동 : 2/2🐷\r\n"
        )
        rows = parse_txt(text)
        assert len(rows) == 1

    def test_영문_파일_헤더_스킵(self):
        text = (
            "Talk_2026.2.13 18:42-1.txt\r\n"
            "Date Saved : Feb 13, 2026 at 18:42\r\n"
            "\r\n"
            "Feb 2, 2026 at 7:33, 홍길동 : 2/2🐷\r\n"
        )
        rows = parse_txt(text)
        assert len(rows) == 1
        assert rows[0] == ("홍길동", "2/2🐷")

    def test_영문_멀티라인_메시지(self):
        text = (
            "Date Saved : Feb 13, 2026 at 18:42\r\n"
            "Feb 1, 2026 at 20:29, 홍길동 : 첫줄\r\n"
            "둘째줄\r\n"
            "셋째줄\r\n"
            "Feb 2, 2026 at 7:33, 김철수 : 단일줄\r\n"
        )
        rows = parse_txt(text)
        assert len(rows) == 2
        assert rows[0] == ("홍길동", "첫줄\n둘째줄\n셋째줄")
        assert rows[1] == ("김철수", "단일줄")

    def test_영문_종합_시나리오(self):
        text = (
            "Talk_2026.2.13 18:42-1.txt\r\n"
            "Date Saved : Feb 13, 2026 at 18:42\r\n"
            "\r\n"
            "Sunday, February 1, 2026\r\n"
            "Feb 1, 2026 at 20:26: 홍길동님이 방장이 되었습니다.\r\n"
            "Feb 1, 2026 at 20:29, 홍길동 : 공지사항\r\n"
            "여러 줄 안내문\r\n"
            "\r\n"
            "Monday, February 2, 2026\r\n"
            "Feb 2, 2026 at 7:33, 김철수 : 2/2🐷\r\n"
            "Feb 2, 2026 at 8:00, 이영희 : 2/2🦊\r\n"
        )
        rows = parse_txt(text)
        assert len(rows) == 3
        assert rows[0] == ("홍길동", "공지사항\n여러 줄 안내문")
        assert rows[1] == ("김철수", "2/2🐷")
        assert rows[2] == ("이영희", "2/2🦊")


class TestExtractChatMetaEnglish:
    def test_영문_저장날짜_추출(self):
        text = (
            "Date Saved : Feb 13, 2026 at 18:42\r\n"
            "\r\n"
            "Sunday, February 1, 2026\r\n"
        )
        meta = extract_chat_meta(text)
        assert meta["room_name"] is None
        assert meta["saved_date"] == "2026/02/13-18:42"

    def test_영문_방이름_없음__None_반환(self):
        text = (
            "Date Saved : Feb 13, 2026 at 18:42\r\n"
            "Feb 1, 2026 at 20:35, 김예슬 : 메시지\r\n"
        )
        meta = extract_chat_meta(text)
        assert meta["room_name"] is None

    def test_영문_오전시간_추출(self):
        text = "Date Saved : Jan 5, 2026 at 9:05\r\n"
        meta = extract_chat_meta(text)
        assert meta["saved_date"] == "2026/01/05-09:05"

    def test_영문_12월_추출(self):
        text = "Date Saved : Dec 25, 2025 at 0:00\r\n"
        meta = extract_chat_meta(text)
        assert meta["saved_date"] == "2025/12/25-00:00"
