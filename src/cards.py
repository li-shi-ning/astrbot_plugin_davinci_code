"""牌面图片：QQ 官方 Markdown 内嵌图。

外部展示（牌桌、公开播报）用图片，私密手牌仍用纯文字（见
:func:`render.hand_payload`）。

QQ 官方 Markdown 图片语法为 ``![替代文字 #宽px #高px](公网图片直链)``，
图片必须是 QQ 服务器可直接抓取的公网 HTTPS 地址。替代文字会在图片
加载失败时显示，因此这里统一填牌面文字做兜底。
"""

from __future__ import annotations

import re
from pathlib import Path

from .engine import BLACK, Tile

# 本地牌面素材（scripts/download_card_assets.py 生成并提交进仓库）
ASSET_DIR = Path(__file__).resolve().parent.parent / "assets" / "cards"

DEFAULT_BASE = "https://placehold.co/72x108"
BLACK_STYLE = "000000/FFFFFF"  # 黑底白字
WHITE_STYLE = "FFFFFF/000000"  # 白底黑字
BACK_STYLE = "2563EB/2563EB"  # 蓝底（背面）
DEFAULT_WIDTH = 32
DEFAULT_HEIGHT = 48

_base = DEFAULT_BASE
_width = DEFAULT_WIDTH
_height = DEFAULT_HEIGHT


def configure(
    base: str | None = None,
    width: int | None = None,
    height: int | None = None,
) -> None:
    """覆盖图片服务前缀与显示尺寸，一般由插件初始化时调用。

    Args:
        base: 形如 ``https://placehold.co/72x108`` 的图片服务前缀。
        width: Markdown 中的显示宽度（px）。
        height: Markdown 中的显示高度（px）。
    """
    global _base, _width, _height
    if base:
        _base = base.strip().rstrip("/")
    if width and width > 0:
        _width = int(width)
    if height and height > 0:
        _height = int(height)


def parse_size(text: str) -> tuple[int, int]:
    """解析 ``32x48`` 形式的尺寸配置，非法时回退默认值。

    Args:
        text: 形如 ``32x48`` / ``32×48`` / ``32*48`` 的字符串。

    Returns:
        ``(宽, 高)`` 像素元组。
    """
    match = re.fullmatch(r"\s*(\d{1,3})\s*[x×*]\s*(\d{1,3})\s*", text or "")
    if match is None:
        return (DEFAULT_WIDTH, DEFAULT_HEIGHT)
    width, height = int(match.group(1)), int(match.group(2))
    if not 8 <= width <= 200 or not 8 <= height <= 300:
        return (DEFAULT_WIDTH, DEFAULT_HEIGHT)
    return (width, height)


def reset() -> None:
    """恢复默认配置（测试用）。"""
    configure(DEFAULT_BASE, DEFAULT_WIDTH, DEFAULT_HEIGHT)


def asset_path(tile: Tile) -> Path:
    """一张牌的本地素材路径。"""
    number = "joker" if tile.is_joker else tile.number
    return ASSET_DIR / f"{tile.color}-{number}.png"


def back_asset_path() -> Path:
    """暗牌背面的本地素材路径。"""
    return ASSET_DIR / "back.png"


def tile_md(tile: Tile) -> str:
    """一张明牌的 Markdown 内嵌图。"""
    style = BLACK_STYLE if tile.color == BLACK else WHITE_STYLE
    text = "-" if tile.is_joker else str(tile.number)
    return _image(tile.text, style, text)


def back_md() -> str:
    """一张暗牌的 Markdown 内嵌图。"""
    return _image("暗牌", BACK_STYLE, "")


def _image(alt: str, style: str, text: str) -> str:
    return f"![{alt} #{_width}px #{_height}px]({_base}/{style}.png?text={text})"
