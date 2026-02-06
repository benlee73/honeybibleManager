import pytest

from app.emoji import (
    extract_emoji_sequence,
    extract_trailing_emoji,
    is_emoji_char,
    is_emoji_component,
    is_emoji_modifier,
    normalize_emoji,
)


class TestIsEmojiChar:
    def test_is_emoji_char__common_emoji__returns_true(self):
        assert is_emoji_char("😀") is True

    def test_is_emoji_char__sun_symbol__returns_true(self):
        assert is_emoji_char("☀") is True

    def test_is_emoji_char__ascii_letter__returns_false(self):
        assert is_emoji_char("A") is False

    def test_is_emoji_char__korean_char__returns_false(self):
        assert is_emoji_char("가") is False

    def test_is_emoji_char__digit__returns_false(self):
        assert is_emoji_char("1") is False


class TestIsEmojiModifier:
    def test_is_emoji_modifier__skin_tone_light__returns_true(self):
        assert is_emoji_modifier("\U0001F3FB") is True

    def test_is_emoji_modifier__skin_tone_dark__returns_true(self):
        assert is_emoji_modifier("\U0001F3FF") is True

    def test_is_emoji_modifier__regular_emoji__returns_false(self):
        assert is_emoji_modifier("😀") is False

    def test_is_emoji_modifier__ascii_char__returns_false(self):
        assert is_emoji_modifier("A") is False


class TestIsEmojiComponent:
    def test_is_emoji_component__emoji_char__returns_true(self):
        assert is_emoji_component("😀") is True

    def test_is_emoji_component__skin_tone_modifier__returns_true(self):
        assert is_emoji_component("\U0001F3FB") is True

    def test_is_emoji_component__zwj__returns_true(self):
        assert is_emoji_component("\u200D") is True

    def test_is_emoji_component__variation_selector__returns_true(self):
        assert is_emoji_component("\uFE0F") is True

    def test_is_emoji_component__ascii_char__returns_false(self):
        assert is_emoji_component("A") is False


class TestExtractEmojiSequence:
    def test_extract_emoji_sequence__zwj_sequence__returns_full_sequence(self):
        family = "\U0001F468\u200D\U0001F469\u200D\U0001F467"
        emoji, end = extract_emoji_sequence(family, 0)
        assert emoji == family
        assert end == len(family)

    def test_extract_emoji_sequence__single_emoji__returns_one_char(self):
        text = "😀hello"
        emoji, end = extract_emoji_sequence(text, 0)
        assert emoji == "😀"
        assert end == 1

    def test_extract_emoji_sequence__non_emoji_start__returns_none(self):
        text = "hello😀"
        emoji, end = extract_emoji_sequence(text, 0)
        assert emoji is None
        assert end == 0

    def test_extract_emoji_sequence__out_of_bounds__returns_none(self):
        emoji, end = extract_emoji_sequence("abc", 10)
        assert emoji is None
        assert end == 10

    def test_extract_emoji_sequence__emoji_with_variation_selector__includes_it(self):
        text = "☀\uFE0F"
        emoji, end = extract_emoji_sequence(text, 0)
        assert emoji == "☀\uFE0F"
        assert end == 2


class TestNormalizeEmoji:
    def test_normalize_emoji__with_variation_selector__removes_it(self):
        assert normalize_emoji("☀\uFE0F") == "☀"

    def test_normalize_emoji__without_variation_selector__unchanged(self):
        assert normalize_emoji("😀") == "😀"

    def test_normalize_emoji__multiple_variation_selectors__removes_all(self):
        assert normalize_emoji("\uFE0F😀\uFE0F") == "😀"


class TestExtractTrailingEmoji:
    def test_extract_trailing_emoji__text_ending_with_emoji__returns_emoji(self):
        assert extract_trailing_emoji("hello😀") == "😀"

    def test_extract_trailing_emoji__no_emoji__returns_none(self):
        assert extract_trailing_emoji("hello world") is None

    def test_extract_trailing_emoji__emoji_in_middle_only__returns_none(self):
        assert extract_trailing_emoji("hello😀world") is None

    def test_extract_trailing_emoji__empty_string__returns_none(self):
        assert extract_trailing_emoji("") is None

    def test_extract_trailing_emoji__only_spaces__returns_none(self):
        assert extract_trailing_emoji("   ") is None

    def test_extract_trailing_emoji__trailing_whitespace_after_emoji__returns_emoji(self):
        assert extract_trailing_emoji("hello😀  ") == "😀"

    def test_extract_trailing_emoji__consecutive_trailing_emojis__returns_combined(self):
        result = extract_trailing_emoji("hello🔥😀")
        assert result == "🔥😀"

    def test_extract_trailing_emoji__텍스트_이모티콘__괄호_포함_반환(self):
        assert extract_trailing_emoji("2/2 구약 신약 (무표정)") == "(무표정)"

    def test_extract_trailing_emoji__텍스트_이모티콘_공백없이__반환(self):
        assert extract_trailing_emoji("2/2 신약(연필)") == "(연필)"

    def test_extract_trailing_emoji__괄호_안_비한글__None_반환(self):
        assert extract_trailing_emoji("PART 1 (2/2 ~ 5/30)") is None
