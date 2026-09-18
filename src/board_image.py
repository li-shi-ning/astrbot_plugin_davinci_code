"""把牌桌渲染成本地 PNG，供 QQ 富媒体消息（msg_type=7）上传发送。

只依赖 Pillow 与本地素材，不访问任何外网图床。
"""

from __future__ import annotations

from pathlib import Path

from . import cards
from .engine import Room

CARD_W, CARD_H = 36, 54
GAP = 5
PAD = 14
HEADER_H = 34
ROW_GAP = 8
LABEL_W = 108

BG = (246, 247, 250)
FG = (32, 33, 36)
MUTED = (160, 162, 170)
CURRENT_BG = (255, 243, 205)
OUT_BG = (236, 237, 240)

# AstrBot 自带 /AstrBot/data/font.ttf（文泉驿微米黑），再兜底到常见中文字体
FONT_CANDIDATES = (
    "/AstrBot/data/font.ttf",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/arphic/uming.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


def find_font() -> str | None:
    """返回第一个可用的字体路径（优先中文字体）。"""
    for path in FONT_CANDIDATES:
        if Path(path).is_file():
            return path
    return None


def render_board(room: Room, out_path: str | Path, font_path: str | None = None):
    """把当前牌桌渲染成 PNG。

    Args:
        room: 牌局。
        out_path: 输出 PNG 路径（父目录会自动创建）。
        font_path: 指定字体；为空时自动查找。

    Returns:
        输出路径；缺少 Pillow 等依赖时返回 ``None``。
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:  # pragma: no cover - AstrBot 默认自带 Pillow
        return None

    font_file = font_path or find_font()

    def font(size: int):
        if font_file:
            try:
                return ImageFont.truetype(font_file, size)
            except OSError:
                pass
        return ImageFont.load_default(size=size)

    title_font = font(19)
    label_font = font(17)

    columns = max((len(p.hand) for p in room.players), default=0)
    width = PAD * 2 + LABEL_W + max(columns, 1) * (CARD_W + GAP)
    height = PAD * 2 + HEADER_H + max(len(room.players), 1) * (CARD_H + ROW_GAP)

    image = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(image)
    draw.text((PAD, PAD + 4), f"牌堆 {len(room.deck)} 张", font=title_font, fill=FG)

    y = PAD + HEADER_H
    for player in room.players:
        if player is room.current:
            draw.rounded_rectangle(
                [PAD - 8, y - 5, width - PAD + 8, y + CARD_H + 5],
                radius=8,
                fill=CURRENT_BG,
            )
        elif not player.alive:
            draw.rounded_rectangle(
                [PAD - 8, y - 5, width - PAD + 8, y + CARD_H + 5],
                radius=8,
                fill=OUT_BG,
            )
        label = f"{player.label} {player.name}"
        if not player.alive:
            label += " 出局"
        elif player is room.current:
            label = "▶" + label
        draw.text(
            (PAD, y + CARD_H // 2 - 11),
            label[:8],
            font=label_font,
            fill=FG if player.alive else MUTED,
        )
        x = PAD + LABEL_W
        for tile in player.hand:
            card = _card_image(tile) if tile.revealed else _back_image()
            if card is not None:
                image.paste(card, (x, y), card)
            x += CARD_W + GAP
        y += CARD_H + ROW_GAP

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path, "PNG")
    return out_path


def _card_image(tile):
    """读一张明牌的本地素材并缩放到统一尺寸。"""
    return _load(cards.asset_path(tile))


def _back_image():
    """读一张暗牌背面素材。"""
    return _load(cards.back_asset_path())


def _load(path: Path):
    from PIL import Image

    try:
        with Image.open(path) as source:
            return source.convert("RGBA").resize((CARD_W, CARD_H), Image.LANCZOS)
    except (OSError, ValueError):
        return None
