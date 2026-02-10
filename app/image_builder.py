import io
import os

from PIL import Image, ImageDraw, ImageFont

from app.analyzer import build_dual_preview_data, build_preview_data

_FONTS_DIR = os.path.join(os.path.dirname(__file__), "fonts")

_THEMES = {
    "honey": {
        "bg": (255, 246, 226),           # #FFF6E2
        "title": (74, 45, 20),           # #4A2D14
        "header_bg": (227, 155, 47),     # #E39B2F
        "header_text": (255, 255, 255),
        "body_text": (42, 26, 8),        # #2A1A08
        "mark": (227, 155, 47),          # #E39B2F
        "line": (212, 196, 168),         # #D4C4A8
        "card_bg": (255, 241, 211),      # #FFF1D3
        "card_value": (227, 155, 47),    # #E39B2F
        "card_label": (74, 45, 20),      # #4A2D14
        "subtitle": (122, 61, 18),       # #7A3D12
    },
    "bw": {
        "bg": (17, 17, 17),             # #111
        "title": (255, 255, 255),        # #fff
        "header_bg": (102, 102, 102),    # #666
        "header_text": (255, 255, 255),
        "body_text": (255, 255, 255),    # #fff
        "mark": (255, 255, 255),         # #fff
        "line": (60, 60, 60),            # rgba(255,255,255,0.15) on #111
        "card_bg": (26, 26, 26),         # #1a1a1a
        "card_value": (255, 255, 255),   # #fff
        "card_label": (204, 204, 204),   # #ccc
        "subtitle": (204, 204, 204),     # #ccc
    },
    "brew": {
        "bg": (53, 47, 39),             # #352f27
        "title": (249, 208, 148),        # #f9d094
        "header_bg": (139, 94, 42),      # #8b5e2a
        "header_text": (249, 208, 148),  # #f9d094
        "body_text": (249, 208, 148),    # #f9d094
        "mark": (211, 164, 89),          # #d3a459
        "line": (80, 68, 50),            # rgba(190,134,45,0.25) on bg
        "card_bg": (58, 50, 40),         # #3a3228
        "card_value": (211, 164, 89),    # #d3a459
        "card_label": (211, 164, 89),    # #d3a459
        "subtitle": (190, 134, 45),      # #be862d
    },
    "neon": {
        "bg": (15, 15, 26),             # #0f0f1a
        "title": (238, 238, 238),        # #eee
        "header_bg": (255, 0, 229),      # #ff00e5
        "header_text": (238, 238, 238),  # #eee
        "body_text": (238, 238, 238),    # #eee
        "mark": (0, 229, 255),           # #00e5ff
        "line": (40, 40, 60),            # rgba(57,255,20,0.2) on bg
        "card_bg": (26, 26, 46),         # #1a1a2e
        "card_value": (0, 229, 255),     # #00e5ff
        "card_label": (170, 170, 170),   # #aaa
        "subtitle": (57, 255, 20),       # #39ff14
    },
}


def _get_theme(theme_id):
    return _THEMES.get(theme_id, _THEMES["honey"])


def _load_font(size, bold=False):
    """번들 폰트 → 시스템 폰트 → 기본 폰트 순으로 탐색."""
    candidates = [
        os.path.join(_FONTS_DIR, "Jua-Regular.ttf"),
    ]
    if bold:
        candidates.append(os.path.join(_FONTS_DIR, "NanumGothicBold.ttf"))
    candidates.append(os.path.join(_FONTS_DIR, "NanumGothic.ttf"))
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


def _draw_stat_cards(draw, stats, x, y, width, font_value, font_label, scale=1, theme=None):
    """통계 카드 4개를 가로 배치한다."""
    t = theme or _THEMES["honey"]
    s = scale
    cards = [
        (str(stats["members"]), "참여 멤버"),
        (f"{stats['perfect_count']}명", "완독자 수"),
        (str(stats["dates"]), "인증 날짜"),
        (f"{stats['avg_rate']}%", "평균 달성률"),
    ]
    card_gap = 10 * s
    card_count = len(cards)
    card_w = (width - card_gap * (card_count - 1)) // card_count
    card_h = 60 * s

    inner_gap = 6 * s
    for i, (value, label) in enumerate(cards):
        cx = x + i * (card_w + card_gap)
        draw.rounded_rectangle(
            [cx, y, cx + card_w, y + card_h],
            radius=10 * s,
            fill=t["card_bg"],
        )
        vw, vh = _measure_text(draw, value, font_value)
        lw, lh = _measure_text(draw, label, font_label)
        total_h = vh + inner_gap + lh
        top_y = y + (card_h - total_h) // 2
        draw.text(
            (cx + (card_w - vw) // 2, top_y),
            value,
            fill=t["card_value"],
            font=font_value,
        )
        draw.text(
            (cx + (card_w - lw) // 2, top_y + vh + inner_gap),
            label,
            fill=t["card_label"],
            font=font_label,
        )

    return card_h


def _draw_table(draw, headers, rows, x, y, col_widths, row_height, font, font_bold, font_emoji=None, scale=1, theme=None):
    """진도표 테이블을 렌더링한다. 렌더링 후 다음 y 좌표를 반환."""
    t = theme or _THEMES["honey"]
    s = scale
    # 헤더 행
    cx = x
    for i, header in enumerate(headers):
        w = col_widths[i]
        draw.rounded_rectangle(
            [cx, y, cx + w, y + row_height],
            radius=4 * s,
            fill=t["header_bg"],
        )
        tw, th = _measure_text(draw, header, font_bold)
        text_x = cx + (w - tw) // 2
        text_y = y + (row_height - th) // 2
        draw.text((text_x, text_y), header, fill=t["header_text"], font=font_bold)
        cx += w

    y += row_height

    # 데이터 행
    for row_data in rows:
        cx = x
        for i, cell in enumerate(row_data):
            w = col_widths[i]
            draw.line([(cx, y + row_height - 1), (cx + w, y + row_height - 1)], fill=t["line"])
            cell_font = font_bold if cell == "O" else font
            cell_color = t["mark"] if cell == "O" else t["body_text"]
            if i == 1 and font_emoji and _has_unicode_emoji(cell):
                tw, th = _measure_emoji_text(draw, cell, cell_font, font_emoji)
                text_x = cx + (w - tw) // 2
                text_y = y + (row_height - th) // 2
                _draw_emoji_text(draw, (text_x, text_y), cell, cell_font, font_emoji, cell_color)
            else:
                tw, th = _measure_text(draw, cell, cell_font)
                text_x = cx + (w - tw) // 2
                text_y = y + (row_height - th) // 2
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


def build_output_image(users, track_mode="single", scale=2, theme="honey"):
    """분석 결과를 PNG 이미지(bytes)로 생성한다. scale=2로 Retina 대응."""
    t = _get_theme(theme)
    s = scale
    font_title = _load_font(22 * s, bold=True)
    font_subtitle = _load_font(15 * s, bold=True)
    font_stat_value = _load_font(19 * s, bold=True)
    font_stat_label = _load_font(10 * s)
    font_table = _load_font(11 * s)
    font_table_bold = _load_font(11 * s, bold=True)
    font_emoji = _load_emoji_font(11 * s)

    padding = 26 * s
    row_height = 28 * s

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

    col_min = (88 * s, 52 * s, 38 * s)

    if track_mode == "dual":
        old_col_widths = _calc_col_widths(tmp_draw, old_headers, old_rows, font_table, font_table_bold, font_emoji, *col_min)
        new_col_widths = _calc_col_widths(tmp_draw, new_headers, new_rows, font_table, font_table_bold, font_emoji, *col_min)
        old_table_w = sum(old_col_widths)
        new_table_w = sum(new_col_widths)
        table_w = max(old_table_w, new_table_w)
    else:
        col_widths = _calc_col_widths(tmp_draw, headers, rows, font_table, font_table_bold, font_emoji, *col_min)
        table_w = sum(col_widths)

    content_w = max(table_w, 400 * s)
    img_w = content_w + padding * 2

    # 높이 계산
    title_h = 30 * s
    gap_title = 16 * s
    card_h_est = 60 * s
    gap_card = 20 * s
    subtitle_h = 24 * s
    gap_subtitle = 6 * s
    gap_tables = 20 * s

    y = padding
    y += title_h + gap_title + card_h_est + gap_card

    if track_mode == "dual":
        y += subtitle_h + gap_subtitle
        y += row_height * (1 + len(old_rows))
        y += gap_tables
        y += subtitle_h + gap_subtitle
        y += row_height * (1 + len(new_rows))
    else:
        y += row_height * (1 + len(rows))

    y += padding
    img_h = y

    # 본 이미지 생성
    img = Image.new("RGB", (img_w, img_h), t["bg"])
    draw = ImageDraw.Draw(img)

    y = padding

    # 타이틀
    title = "꿀성경 진도표"
    tw, _ = _measure_text(draw, title, font_title)
    draw.text(((img_w - tw) // 2, y), title, fill=t["title"], font=font_title)
    y += title_h + gap_title

    # 통계 카드
    card_h = _draw_stat_cards(draw, stats, padding, y, content_w, font_stat_value, font_stat_label, scale=s, theme=t)
    y += card_h + gap_card

    if track_mode == "dual":
        subtitle = "구약 진도표"
        draw.text((padding, y), subtitle, fill=t["subtitle"], font=font_subtitle)
        y += subtitle_h + gap_subtitle
        y = _draw_table(draw, old_headers, old_rows, padding, y, old_col_widths, row_height, font_table, font_table_bold, font_emoji, scale=s, theme=t)
        y += gap_tables

        subtitle = "신약 진도표"
        draw.text((padding, y), subtitle, fill=t["subtitle"], font=font_subtitle)
        y += subtitle_h + gap_subtitle
        y = _draw_table(draw, new_headers, new_rows, padding, y, new_col_widths, row_height, font_table, font_table_bold, font_emoji, scale=s, theme=t)
    else:
        y = _draw_table(draw, headers, rows, padding, y, col_widths, row_height, font_table, font_table_bold, font_emoji, scale=s, theme=t)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
