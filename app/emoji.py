import re

TEXT_EMOTICON_PATTERN = re.compile(r"\(([가-힣]+)\)\s*$")

EMOJI_RANGES = [
    (0x1F300, 0x1F5FF),
    (0x1F600, 0x1F64F),
    (0x1F680, 0x1F6FF),
    (0x1F700, 0x1F77F),
    (0x1F780, 0x1F7FF),
    (0x1F800, 0x1F8FF),
    (0x1F900, 0x1F9FF),
    (0x1FA00, 0x1FA6F),
    (0x1FA70, 0x1FAFF),
    (0x2600, 0x26FF),
    (0x2700, 0x27BF),
    (0x2300, 0x23FF),
    (0x2B00, 0x2BFF),
    (0x1F1E6, 0x1F1FF),
]

EMOJI_MODIFIER_RANGE = (0x1F3FB, 0x1F3FF)
ZWJ = 0x200D
VARIATION_SELECTOR = 0xFE0F


def is_emoji_char(char):
    codepoint = ord(char)
    for start, end in EMOJI_RANGES:
        if start <= codepoint <= end:
            return True
    return False


def is_emoji_modifier(char):
    codepoint = ord(char)
    return EMOJI_MODIFIER_RANGE[0] <= codepoint <= EMOJI_MODIFIER_RANGE[1]


def is_emoji_component(char):
    codepoint = ord(char)
    return (
        is_emoji_char(char)
        or is_emoji_modifier(char)
        or codepoint == VARIATION_SELECTOR
        or codepoint == ZWJ
    )


def extract_emoji_sequence(text, start_index):
    if start_index >= len(text):
        return None, start_index
    if not is_emoji_char(text[start_index]):
        return None, start_index

    end_index = start_index + 1
    while end_index < len(text) and is_emoji_component(text[end_index]):
        end_index += 1
    return text[start_index:end_index], end_index


def normalize_emoji(emoji_text):
    return emoji_text.replace("\ufe0f", "")


def extract_trailing_emoji(text):
    trimmed = text.rstrip()
    if not trimmed:
        return None

    # 텍스트 이모티콘 검사: (한글) 패턴이 메시지 끝에 있으면 반환
    m = TEXT_EMOTICON_PATTERN.search(trimmed)
    if m:
        return m.group(0)

    index = 0
    last_emoji = None
    last_end = 0
    while index < len(trimmed):
        if is_emoji_char(trimmed[index]):
            emoji, end_index = extract_emoji_sequence(trimmed, index)
            if emoji:
                last_emoji = emoji
                last_end = end_index
                index = end_index
                continue
        index += 1

    if last_emoji and last_end == len(trimmed):
        return last_emoji
    return None
