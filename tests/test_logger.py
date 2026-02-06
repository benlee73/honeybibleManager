import logging

from app.logger import get_logger, setup_logging


class TestSetupLogging:
    """setup_logging 함수 테스트."""

    def test_루트_로거_반환(self):
        root = setup_logging()
        assert root.name == "honeybible"

    def test_로그_레벨_설정(self):
        root = setup_logging(level=logging.DEBUG)
        assert root.level == logging.DEBUG

    def test_핸들러_등록(self):
        root = setup_logging()
        handler_types = [type(h) for h in root.handlers]
        assert logging.StreamHandler in handler_types
        assert logging.FileHandler in handler_types

    def test_중복_호출_시_핸들러_추가되지_않음(self):
        root = setup_logging()
        handler_count = len(root.handlers)
        setup_logging()
        assert len(root.handlers) == handler_count


class TestGetLogger:
    """get_logger 함수 테스트."""

    def test_모듈별_로거_이름(self):
        logger = get_logger("server")
        assert logger.name == "honeybible.server"

    def test_다른_모듈_로거_이름(self):
        logger = get_logger("handler")
        assert logger.name == "honeybible.handler"

    def test_로거_로그_기록(self, caplog):
        setup_logging()
        logger = get_logger("test")
        with caplog.at_level(logging.INFO, logger="honeybible.test"):
            logger.info("테스트 메시지")
        assert "테스트 메시지" in caplog.text
