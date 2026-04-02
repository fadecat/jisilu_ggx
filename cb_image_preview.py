import os
from html import unescape

from PIL import Image, ImageDraw, ImageFont

IMAGE_WIDTH = 1080
PAGE_PADDING = 36
CARD_PADDING_X = 28
CARD_PADDING_Y = 24
CARD_GAP = 24
LINE_GAP = 10
QUOTE_BAR_WIDTH = 4
QUOTE_GAP = 14

BG_COLOR = "#F3F6FB"
CARD_COLOR = "#FFFFFF"
BORDER_COLOR = "#D9E2F2"
TEXT_COLOR = "#1F2937"
SUBTLE_COLOR = "#6B7280"
INFO_COLOR = "#16A34A"
WARNING_COLOR = "#F97316"

FONT_CANDIDATES = {
    False: [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ],
    True: [
        r"C:\Windows\Fonts\msyhbd.ttc",
        r"C:\Windows\Fonts\simsunb.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ],
}


def load_font(size, bold=False):
    for path in FONT_CANDIDATES[bold]:
        if os.path.exists(path):
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


TITLE_FONT = load_font(28, bold=True)
NAME_FONT = load_font(25, bold=True)
BODY_FONT = load_font(22)
BODY_BOLD_FONT = load_font(22, bold=True)
SMALL_FONT = load_font(18)


def map_color(name):
    return {
        "info": INFO_COLOR,
        "warning": WARNING_COLOR,
        "comment": SUBTLE_COLOR,
    }.get(name, TEXT_COLOR)


def parse_styled_text(text):
    """解析有限的 markdown/font 标签，只处理当前消息里会出现的格式。"""
    spans = []
    buffer = []
    color = TEXT_COLOR
    bold = False
    i = 0

    def flush():
        if buffer:
            spans.append({
                "text": unescape("".join(buffer)),
                "color": color,
                "bold": bold,
            })
            buffer.clear()

    while i < len(text):
        if text.startswith("**", i):
            flush()
            bold = not bold
            i += 2
            continue
        if text.startswith("<font color=\"", i):
            flush()
            j = text.find("\">", i)
            color_name = text[i + len("<font color=\""):j]
            color = map_color(color_name)
            i = j + 2
            continue
        if text.startswith("</font>", i):
            flush()
            color = TEXT_COLOR
            i += len("</font>")
            continue
        buffer.append(text[i])
        i += 1

    flush()
    return spans


def get_font(bold=False, size="body"):
    if size == "title":
        return TITLE_FONT
    if size == "name":
        return NAME_FONT
    if size == "small":
        return SMALL_FONT
    return BODY_BOLD_FONT if bold else BODY_FONT


def split_line_type(line):
    stripped = line.strip()
    if not stripped:
        return "blank", ""
    if stripped == "---":
        return "separator", ""
    if stripped.startswith("> "):
        return "quote", stripped[2:]
    return "normal", stripped


def classify_font_size(line_type, content):
    if line_type == "normal" and content.startswith("**📋"):
        return "title"
    if line_type == "normal" and content.startswith("**📈"):
        return "title"
    if line_type == "normal" and content.startswith("**集思录可转债筛选**"):
        return "title"
    if line_type == "normal" and content.startswith("**续("):
        return "title"
    if line_type == "normal" and content.startswith("**") and "📌" in content:
        return "name"
    return "body"


def text_width(draw, text, font):
    if not text:
        return 0
    return int(draw.textlength(text, font=font))


def wrap_spans(draw, spans, max_width, size="body"):
    lines = []
    current = []
    current_width = 0

    for span in spans:
        font = get_font(span["bold"], size=size)
        for ch in span["text"]:
            piece_width = text_width(draw, ch, font)
            if current and current_width + piece_width > max_width:
                lines.append(current)
                current = []
                current_width = 0
            current.append({
                "text": ch,
                "color": span["color"],
                "bold": span["bold"],
            })
            current_width += piece_width

    if current or not lines:
        lines.append(current)
    return lines


def measure_line_height(line_spans, size="body"):
    max_height = 0
    for span in line_spans:
        font = get_font(span.get("bold", False), size=size)
        bbox = font.getbbox(span.get("text", "中") or "中")
        max_height = max(max_height, bbox[3] - bbox[1])
    return max_height or 24


def prepare_blocks(messages):
    probe = Image.new("RGB", (IMAGE_WIDTH, 200), BG_COLOR)
    draw = ImageDraw.Draw(probe)
    blocks = []

    for message in messages:
        rows = []
        for raw_line in message.splitlines():
            line_type, content = split_line_type(raw_line)
            if line_type == "blank":
                rows.append({"type": "blank", "height": 14})
                continue
            if line_type == "separator":
                rows.append({"type": "separator", "height": 20})
                continue

            font_size = classify_font_size(line_type, content)
            spans = parse_styled_text(content)
            max_width = IMAGE_WIDTH - PAGE_PADDING * 2 - CARD_PADDING_X * 2
            if line_type == "quote":
                max_width -= QUOTE_BAR_WIDTH + QUOTE_GAP

            wrapped = wrap_spans(draw, spans, max_width, size=font_size)
            for wrapped_line in wrapped:
                rows.append({
                    "type": line_type,
                    "spans": wrapped_line,
                    "font_size": font_size,
                    "height": measure_line_height(wrapped_line, size=font_size),
                })

        block_height = CARD_PADDING_Y * 2
        for row in rows:
            block_height += row["height"]
            if row["type"] != "separator":
                block_height += LINE_GAP
        blocks.append({"rows": rows, "height": block_height})

    return blocks


def draw_spans(draw, x, y, spans, size="body"):
    cursor_x = x
    for span in spans:
        text = span.get("text", "")
        if not text:
            continue
        font = get_font(span.get("bold", False), size=size)
        draw.text((cursor_x, y), text, font=font, fill=span.get("color", TEXT_COLOR))
        cursor_x += text_width(draw, text, font)


def render_messages_to_image(messages, output_path="cb_preview.png"):
    blocks = prepare_blocks(messages)
    total_height = PAGE_PADDING * 2 + sum(block["height"] for block in blocks)
    total_height += CARD_GAP * max(len(blocks) - 1, 0)

    image = Image.new("RGB", (IMAGE_WIDTH, total_height), BG_COLOR)
    draw = ImageDraw.Draw(image)

    y = PAGE_PADDING
    for block in blocks:
        card_box = (
            PAGE_PADDING,
            y,
            IMAGE_WIDTH - PAGE_PADDING,
            y + block["height"],
        )
        draw.rounded_rectangle(card_box, radius=18, fill=CARD_COLOR, outline=BORDER_COLOR, width=2)

        inner_x = PAGE_PADDING + CARD_PADDING_X
        inner_y = y + CARD_PADDING_Y
        for row in block["rows"]:
            if row["type"] == "blank":
                inner_y += row["height"]
                continue
            if row["type"] == "separator":
                line_y = inner_y + row["height"] // 2
                draw.line(
                    (inner_x, line_y, IMAGE_WIDTH - PAGE_PADDING - CARD_PADDING_X, line_y),
                    fill=BORDER_COLOR,
                    width=2,
                )
                inner_y += row["height"]
                continue

            text_x = inner_x
            if row["type"] == "quote":
                draw.rounded_rectangle(
                    (
                        inner_x,
                        inner_y + 2,
                        inner_x + QUOTE_BAR_WIDTH,
                        inner_y + row["height"] - 2,
                    ),
                    radius=2,
                    fill=BORDER_COLOR,
                )
                text_x += QUOTE_BAR_WIDTH + QUOTE_GAP

            draw_spans(draw, text_x, inner_y, row["spans"], size=row["font_size"])
            inner_y += row["height"] + LINE_GAP

        y += block["height"] + CARD_GAP

    image.save(output_path, format="PNG", optimize=True)
    if os.path.getsize(output_path) > 1900 * 1024:
        compressed = image.convert("P", palette=Image.Palette.ADAPTIVE, colors=256)
        compressed.save(output_path, format="PNG", optimize=True)
    return output_path
