"""本地牌桌图片渲染测试。"""

from __future__ import annotations

import random

import pytest

pytest.importorskip("PIL")

from PIL import Image  # noqa: E402

from src.board_image import render_board as render_board_image  # noqa: E402
from src.engine import BLACK, PHASE_GUESSING, WHITE, Room, Tile  # noqa: E402


def make_room() -> Room:
    room = Room("g", rng=random.Random(1))
    room.add_player("u1", "四")
    room.add_player("u2", "默然")
    room.started = True
    room.players[0].hand = [
        Tile(BLACK, 5, "b5"),
        Tile(WHITE, 11, "w11", revealed=True),
        Tile(WHITE, None, "wj"),
    ]
    room.players[1].hand = [Tile(BLACK, 7, "b7", revealed=True)]
    room.turn_index = 1
    room.phase = PHASE_GUESSING
    room.deck = [Tile(BLACK, 4, "b4")]
    return room


def test_render_board_creates_png(tmp_path) -> None:
    out = render_board_image(make_room(), tmp_path / "board.png")
    assert out is not None and out.is_file()
    with Image.open(out) as image:
        assert image.format == "PNG"
        # 2 行牌 + 标题，宽度至少容纳 3 张牌
        assert image.width > 3 * 36
        assert image.height > 2 * 54


def test_render_board_uses_local_assets(tmp_path) -> None:
    """渲染不依赖外网：即使没有字体也应能出图。"""
    out = render_board_image(
        make_room(), tmp_path / "board.png", font_path="/not/exist.ttf"
    )
    assert out is not None and out.is_file()
