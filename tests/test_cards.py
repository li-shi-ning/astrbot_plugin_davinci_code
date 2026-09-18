"""牌面图片与牌桌渲染测试。"""

from __future__ import annotations

import random

from src import cards
from src.engine import BLACK, PHASE_GUESSING, WHITE, Room, Tile
from src.render import hand_payload, render_board


def test_tile_image_url_and_alt() -> None:
    cards.reset()
    black = cards.tile_md(Tile(BLACK, 7, "b7", revealed=True))
    white = cards.tile_md(Tile(WHITE, 0, "w0", revealed=True))
    joker = cards.tile_md(Tile(WHITE, None, "wj", revealed=True))
    assert (
        black
        == "![黑7 #32px #48px](https://placehold.co/72x108/000000/FFFFFF.png?text=7)"
    )
    assert (
        white
        == "![白0 #32px #48px](https://placehold.co/72x108/FFFFFF/000000.png?text=0)"
    )
    assert (
        joker
        == "![百搭 #32px #48px](https://placehold.co/72x108/FFFFFF/000000.png?text=-)"
    )
    assert cards.back_md() == (
        "![暗牌 #32px #48px](https://placehold.co/72x108/2563EB/2563EB.png?text=)"
    )


def test_configure_changes_base_and_size() -> None:
    cards.configure("https://cdn.example.com/cards/", 32, 48)
    assert cards.back_md() == (
        "![暗牌 #32px #48px](https://cdn.example.com/cards/2563EB/2563EB.png?text=)"
    )
    cards.reset()
    assert "placehold.co" in cards.back_md()


def test_table_uses_images_without_index() -> None:
    room = Room("g", rng=random.Random(1))
    room.add_player("u1", "四")
    room.add_player("u2", "默然")
    room.started = True
    room.players[0].hand = [Tile(BLACK, 1, "b1"), Tile(WHITE, 3, "w3")]
    room.players[1].hand = [Tile(BLACK, 5, "b5", revealed=True)]
    room.phase = PHASE_GUESSING

    table = render_board(room)
    assert "1." not in table and "2." not in table
    assert cards.back_md() in table
    assert "![黑5" in table
    assert "b1" not in table  # 暗牌不泄露牌面


def test_hand_payload_keeps_plain_text() -> None:
    room = Room("g", rng=random.Random(1))
    room.add_player("u1", "四")
    room.add_player("u2", "默然")
    room.started = True
    room.players[0].hand = [Tile(BLACK, 1, "b1"), Tile(WHITE, None, "wj")]
    room.phase = PHASE_GUESSING
    payload = hand_payload(room.players[0], room)
    assert payload.startswith("A手牌 黑1 百搭")
    assert "placehold" not in payload
    assert "1." not in payload


def test_long_table_falls_back_to_text() -> None:
    """牌局后期图片过多时应退回纯文字，避免超过 Markdown 长度。"""
    from src.render import MAX_IMAGE_TABLE_CHARS

    room = Room("g", rng=random.Random(1))
    room.add_player("u1", "四")
    room.players[0].hand = [Tile(BLACK, i, f"b{i}", revealed=True) for i in range(24)]
    room.started = True
    room.phase = PHASE_GUESSING

    table = render_board(room)
    assert len(table) <= MAX_IMAGE_TABLE_CHARS
    assert "placehold.co" not in table
    assert "黑11" in table


def test_parse_size_validation() -> None:
    from src.cards import DEFAULT_HEIGHT, DEFAULT_WIDTH, parse_size

    assert parse_size("24x36") == (24, 36)
    assert parse_size("24×36") == (24, 36)
    assert parse_size("24 * 36") == (24, 36)
    assert parse_size("") == (DEFAULT_WIDTH, DEFAULT_HEIGHT)
    assert parse_size("bad") == (DEFAULT_WIDTH, DEFAULT_HEIGHT)
    assert parse_size("1x1") == (DEFAULT_WIDTH, DEFAULT_HEIGHT)
    assert parse_size("999x999") == (DEFAULT_WIDTH, DEFAULT_HEIGHT)
