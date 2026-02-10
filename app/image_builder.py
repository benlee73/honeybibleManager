import io
import os

from PIL import Image, ImageDraw, ImageFont

from app.analyzer import build_dual_preview_data, build_preview_data

_FONTS_DIR = os.path.join(os.path.dirname(__file__), "fonts")

# 허니 테마 색상
_BG_COLOR = (255, 246, 226)          # #FFF6E2
_TITLE_COLOR = (74, 45, 20)          # #4A2D14
_HEADER_BG = (227, 155, 47)          # #E39B2F
_HEADER_TEXT = (255, 255, 255)       # white
_BODY_TEXT = (42, 26, 8)             # #2A1A08
_MARK_COLOR = (227, 155, 47)         # #E39B2F
_LINE_COLOR = (212, 196, 168)        # #D4C4A8
_CARD_BG = (255, 241, 211)           # #FFF1D3
_CARD_VALUE = (227, 155, 47)         # #E39B2F
_CARD_LABEL = (74, 45, 20)          # #4A2D14
_SUBTITLE_COLOR = (122, 61, 18)      # #7A3D12


def _load_font(size, bold=False):
    """번들 폰트 → 시스템 폰트 → 기본 폰트 순으로 탐색."""
    if bold:
        candidates = [
            os.path.join(_FONTS_DIR, "NanumGothicBold.ttf"),
            os.path.join(_FONTS_DIR, "NanumGothic.ttf"),
        ]
    else:
        candidates = [
            os.path.join(_FONTS_DIR, "NanumGothic.ttf"),
        ]
    # 시스템 폰트 후보 (macOS / Linux)
    candidates.extend([
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    ])
    for path in candidates:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size)
            except (OSError, IOError):
                continue
    return ImageFont.load_default()


def _load_emoji_font(size):
    """이모지 전용 폰트 로드. NotoEmoji 번들 → 시스템 폰트 → None."""
    candidates = [
        os.path.join(_FONTS_DIR, "NotoEmoji.ttf"),
        "/System/Library/Fonts/Apple Color Emoji.ttc",
        "/usr/share/fonts/truetype/noto/NotoEmoji-Regular.ttf",
    ]
    for path in candidates:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size)
            except (OSError, IOError):
                continue
    return None


def _has_unicode_emoji(text):
    """텍스트에 유니코드 이모지가 포함되어 있는지 판별한다."""
    for ch in text:
        cp = ord(ch)
        if (
            0x1F600 <= cp <= 0x1F64F      # Emoticons
            or 0x1F300 <= cp <= 0x1F5FF    # Misc Symbols and Pictographs
            or 0x1F680 <= cp <= 0x1F6FF    # Transport and Map
            or 0x1F900 <= cp <= 0x1F9FF    # Supplemental Symbols
            or 0x1FA00 <= cp <= 0x1FA6F    # Chess Symbols
            or 0x1FA70 <= cp <= 0x1FAFF    # Symbols and Pictographs Extended-A
            or 0x2600 <= cp <= 0x26FF      # Misc symbols (☀, ☁, ⚡ 등)
            or 0x2700 <= cp <= 0x27BF      # Dingbats (✂, ✅, ✨ 등)
            or 0xFE00 <= cp <= 0xFE0F      # Variation Selectors
            or 0x200D == cp                # ZWJ
            or 0x2764 == cp               # ❤
            or 0x20E3 == cp               # Combining Enclosing Keycap
        ):
            return True
    return False


def _draw_emoji_text(draw, xy, text, font_text, font_emoji, fill):
    """텍스트와 이모지를 각각 적절한 폰트로 렌더링한다."""
    if not font_emoji or not _has_unicode_emoji(text):
        draw.text(xy, text, fill=fill, font=font_text)
        return

    x, y = xy
    # 텍스트를 이모지/비이모지 구간으로 분리하여 렌더링
    segments = []
    current = []
    current_is_emoji = False

    for ch in text:
        ch_is_emoji = _has_unicode_emoji(ch)
        if current and ch_is_emoji != current_is_emoji:
            segments.append(("".join(current), current_is_emoji))
            current = []
        current_is_emoji = ch_is_emoji
        current.append(ch)
    if current:
        segments.append(("".join(current), current_is_emoji))

    for segment_text, is_emoji in segments:
        font = font_emoji if is_emoji else font_text
        draw.text((x, y), segment_text, fill=fill, font=font)
        bbox = draw.textbbox((x, y), segment_text, font=font)
        x = bbox[2]


def _compute_stats(headers, rows, track_mode):
    """app.js의 computeStats를 Python으로 포팅."""
    date_start = 3 if track_mode == "dual" else 2
    date_count = max(0, len(headers) - date_start)

    name_set = set()
    for row in rows:
        name_set.add(row[0])
    members = len(name_set)

    total_o = 0
    name_counts = {}
    for row in rows:
        row_o = sum(1 for cell in row[date_start:] if cell == "O")
        total_o += row_o
        name = row[0]
        name_counts[name] = name_counts.get(name, 0) + row_o

    total_cells = len(rows) * date_count
    avg_rate = round((total_o / total_cells) * 100) if total_cells > 0 else 0

    perfect_count = 0
    if track_mode == "dual":
        old_name_counts = {}
        for row in rows:
            if row[2] != "구약":
                continue
            row_o = sum(1 for cell in row[date_start:] if cell == "O")
            old_name_counts[row[0]] = old_name_counts.get(row[0], 0) + row_o
        for count in old_name_counts.values():
            if date_count > 0 and count == date_count:
                perfect_count += 1
    else:
        name_total_cells = {}
        for row in rows:
            name = row[0]
            name_total_cells[name] = name_total_cells.get(name, 0) + date_count
        for name, total in name_total_cells.items():
            if total > 0 and name_counts.get(name, 0) == total:
                perfect_count += 1

    return {
        "members": members,
        "dates": date_count,
        "avg_rate": avg_rate,
        "perfect_count": perfect_count,
    }


def _measure_text(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _measure_emoji_text(draw, text, font_text, font_emoji):
    """이모지 혼합 텍스트의 너비와 높이를 측정한다."""
    if not font_emoji or not _has_unicode_emoji(text):
        return _measure_text(draw, text, font_text)

    total_w = 0
    max_h = 0
    segments = []
    current = []
    current_is_emoji = False

    for ch in text:
        ch_is_emoji = _has_unicode_emoji(ch)
        if current and ch_is_emoji != current_is_emoji:
            segments.append(("".join(current), current_is_emoji))
            current = []
        current_is_emoji = ch_is_emoji
        current.append(ch)
    if current:
        segments.append(("".join(current), current_is_emoji))

    for segment_text, is_emoji in segments:
        font = font_emoji if is_emoji else font_text
        w, h = _measure_text(draw, segment_text, font)
        total_w += w
        max_h = max(max_h, h)

    return total_w, max_h


def _draw_stat_cards(draw, stats, x, y, width, font_value, font_label):
    """통계 카드 4개를 가로 배치한다."""
    cards = [
        (str(stats["members"]), "참여 멤버"),
        (f"{stats['perfect_count']}명", "완독자 수"),
        (str(stats["dates"]), "인증 날짜"),
        (f"{stats['avg_rate']}%", "평균 달성률"),
    ]
    card_gap = 12
    card_count = len(cards)
    card_w = (width - card_gap * (card_count - 1)) // card_count
    card_h = 70

    for i, (value, label) in enumerate(cards):
        cx = x + i * (card_w + card_gap)
        # 카드 배경 (둥근 사각형)
        draw.rounded_rectangle(
            [cx, y, cx + card_w, y + card_h],
            radius=10,
            fill=_CARD_BG,
        )
        # 값
        vw, vh = _measure_text(draw, value, font_value)
        draw.text(
            (cx + (card_w - vw) // 2, y + 10),
            value,
            fill=_CARD_VALUE,
            font=font_value,
        )
        # 라벨
        lw, _ = _measure_text(draw, label, font_label)
        draw.text(
            (cx + (card_w - lw) // 2, y + 10 + vh + 6),
            label,
            fill=_CARD_LABEL,
            font=font_label,
        )

    return card_h


def _draw_table(draw, headers, rows, x, y, col_widths, row_height, font, font_bold, font_emoji=None):
    """진도표 테이블을 렌더링한다. 렌더링 후 다음 y 좌표를 반환."""
    # 헤더 행
    cx = x
    for i, header in enumerate(headers):
        w = col_widths[i]
        draw.rounded_rectangle(
            [cx, y, cx + w, y + row_height],
            radius=4,
            fill=_HEADER_BG,
        )
        tw, _ = _measure_text(draw, header, font_bold)
        text_x = cx + (w - tw) // 2
        text_y = y + (row_height - 16) // 2
        draw.text((text_x, text_y), header, fill=_HEADER_TEXT, font=font_bold)
        cx += w

    y += row_height

    # 데이터 행
    for row_data in rows:
        cx = x
        for i, cell in enumerate(row_data):
            w = col_widths[i]
            # 셀 하단 라인
            draw.line([(cx, y + row_height - 1), (cx + w, y + row_height - 1)], fill=_LINE_COLOR)
            # 텍스트
            cell_font = font_bold if cell == "O" else font
            cell_color = _MARK_COLOR if cell == "O" else _BODY_TEXT
            # 이모티콘 컬럼(인덱스 1)은 이모지 폰트로 렌더링
            if i == 1 and font_emoji and _has_unicode_emoji(cell):
                tw, _ = _measure_emoji_text(draw, cell, cell_font, font_emoji)
                text_x = cx + (w - tw) // 2
                text_y = y + (row_height - 14) // 2
                _draw_emoji_text(draw, (text_x, text_y), cell, cell_font, font_emoji, cell_color)
            else:
                tw, _ = _measure_text(draw, cell, cell_font)
                text_x = cx + (w - tw) // 2
                text_y = y + (row_height - 14) // 2
                draw.text((text_x, text_y), cell, fill=cell_color, font=cell_font)
            cx += w
        y += row_height

    return y


def _calc_col_widths(draw, headers, rows, font, font_bold, font_emoji=None, name_min=100, emoji_min=60, date_min=44):
    """컬럼 너비를 계산한다."""
    col_widths = []
    for i, header in enumerate(headers):
        hw, _ = _measure_text(draw, header, font_bold)
        max_w = hw + 16
        for row in rows:
            if i < len(row):
                if i == 1 and font_emoji:
                    cw, _ = _measure_emoji_text(draw, row[i], font, font_emoji)
                else:
                    cw, _ = _measure_text(draw, row[i], font)
                max_w = max(max_w, cw + 16)
        # 이름/이모티콘/날짜 최소 너비
        if i == 0:
            max_w = max(max_w, name_min)
        elif i == 1:
            max_w = max(max_w, emoji_min)
        else:
            max_w = max(max_w, date_min)
        col_widths.append(max_w)
    return col_widths


def build_output_image(users, track_mode="single"):
    """분석 결과를 PNG 이미지(bytes)로 생성한다."""
    font_title = _load_font(26, bold=True)
    font_subtitle = _load_font(18, bold=True)
    font_stat_value = _load_font(22, bold=True)
    font_stat_label = _load_font(12)
    font_table = _load_font(13)
    font_table_bold = _load_font(13, bold=True)
    font_emoji = _load_emoji_font(13)

    padding = 30
    row_height = 32

    if track_mode == "dual":
        headers, rows = build_preview_data(users, track_mode="dual")
        old_headers, old_rows, new_headers, new_rows = build_dual_preview_data(users)
    else:
        headers, rows = build_preview_data(users, track_mode="single")

    # 통계 계산
    stats = _compute_stats(headers, rows, track_mode)

    # 사이징을 위한 임시 이미지
    tmp_img = Image.new("RGB", (1, 1))
    tmp_draw = ImageDraw.Draw(tmp_img)

    if track_mode == "dual":
        old_col_widths = _calc_col_widths(tmp_draw, old_headers, old_rows, font_table, font_table_bold, font_emoji)
        new_col_widths = _calc_col_widths(tmp_draw, new_headers, new_rows, font_table, font_table_bold, font_emoji)
        old_table_w = sum(old_col_widths)
        new_table_w = sum(new_col_widths)
        table_w = max(old_table_w, new_table_w)
    else:
        col_widths = _calc_col_widths(tmp_draw, headers, rows, font_table, font_table_bold, font_emoji)
        table_w = sum(col_widths)

    content_w = max(table_w, 400)
    img_w = content_w + padding * 2

    # 높이 계산
    y = padding
    y += 36  # 타이틀
    y += 20  # 갭
    y += 70  # 통계 카드
    y += 24  # 갭

    if track_mode == "dual":
        y += 28  # "구약 진도표" 소제목
        y += 8
        y += row_height * (1 + len(old_rows))  # 헤더 + 데이터
        y += 24  # 갭
        y += 28  # "신약 진도표" 소제목
        y += 8
        y += row_height * (1 + len(new_rows))
    else:
        y += row_height * (1 + len(rows))

    y += padding
    img_h = y

    # 본 이미지 생성
    img = Image.new("RGB", (img_w, img_h), _BG_COLOR)
    draw = ImageDraw.Draw(img)

    y = padding

    # 타이틀
    title = "꿀성경 진도표"
    tw, _ = _measure_text(draw, title, font_title)
    draw.text(((img_w - tw) // 2, y), title, fill=_TITLE_COLOR, font=font_title)
    y += 36 + 20

    # 통계 카드
    card_h = _draw_stat_cards(draw, stats, padding, y, content_w, font_stat_value, font_stat_label)
    y += card_h + 24

    if track_mode == "dual":
        # 구약 진도표
        subtitle = "구약 진도표"
        draw.text((padding, y), subtitle, fill=_SUBTITLE_COLOR, font=font_subtitle)
        y += 28 + 8
        y = _draw_table(draw, old_headers, old_rows, padding, y, old_col_widths, row_height, font_table, font_table_bold, font_emoji)
        y += 24

        # 신약 진도표
        subtitle = "신약 진도표"
        draw.text((padding, y), subtitle, fill=_SUBTITLE_COLOR, font=font_subtitle)
        y += 28 + 8
        y = _draw_table(draw, new_headers, new_rows, padding, y, new_col_widths, row_height, font_table, font_table_bold, font_emoji)
    else:
        y = _draw_table(draw, headers, rows, padding, y, col_widths, row_height, font_table, font_table_bold, font_emoji)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
