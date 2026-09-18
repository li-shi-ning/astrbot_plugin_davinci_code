"""键盘按钮布局测试。"""

from __future__ import annotations

import random

from src.buttons import build_buttons, playing_buttons, waiting_buttons
from src.engine import (
    BLACK,
    PHASE_CONTINUING,
    PHASE_GUESSING,
    WHITE,
    Room,
    Tile,
)


def make_room(players: int = 2, started: bool = False) -> Room:
    room = Room("g1", rng=random.Random(3))
    for index in range(players):
        room.add_player(f"u{index + 1}", f"玩家{index + 1}")
    room.started = started
    return room


def test_no_room_only_shows_create() -> None:
    labels = [b.label for b in build_buttons(None, "u1")]
    assert labels == ["创建牌局", "玩法规则"]


def test_waiting_buttons_restrict_start_to_host() -> None:
    room = make_room(2)
    buttons = waiting_buttons(room, "u1")
    labels = [b.label for b in buttons]
    assert "加入牌局" in labels
    start = next(b for b in buttons if b.label == "开始游戏")
    assert start.only_for == "u1"
    assert "退出牌局" in labels
    # 未入座的玩家看不到退出按钮
    assert "退出牌局" not in [b.label for b in waiting_buttons(room, "u9")]


def test_playing_buttons_hide_hands_behind_owner_permission() -> None:
    room = make_room(2, started=True)
    room.players[0].hand = [Tile(BLACK, 1, "b1")]
    room.players[1].hand = [Tile(WHITE, 5, "w5")]
    room.phase = PHASE_GUESSING

    view = playing_buttons(room)
    hand_buttons = [b for b in view if "手牌" in b.label]
    assert [b.only_for for b in hand_buttons] == ["u1", "u2"]
    assert "1.黑1" in hand_buttons[0].data
    assert "1.白5" in hand_buttons[1].data

    # 操作按钮永远指向当前回合玩家，而不是触发消息的玩家
    guess = next(b for b in view if b.label == "猜牌")
    assert guess.only_for == room.current.user_id
    room.turn_index = 1
    guess = next(b for b in playing_buttons(room) if b.label == "猜牌")
    assert guess.only_for == "u2"


def test_continuing_buttons_offer_guess_and_stop() -> None:
    room = make_room(2, started=True)
    room.players[0].hand = [Tile(BLACK, 1, "b1")]
    room.players[1].hand = [Tile(WHITE, 5, "w5")]
    room.phase = PHASE_CONTINUING
    labels = [b.label for b in playing_buttons(room)]
    assert "继续猜" in labels
    assert "收手" in labels


def test_guess_button_follows_turn_after_wrong_guess() -> None:
    """回归：回合交给别人后，回复里的「猜牌」按钮应属于新的当前玩家。"""
    room = make_room(2, started=True)
    room.players[0].hand = [Tile(BLACK, 1, "b1"), Tile(WHITE, 3, "w3")]
    room.players[1].hand = [Tile(BLACK, 5, "b5"), Tile(WHITE, 8, "w8")]
    room.turn_index = 0
    room.phase = PHASE_GUESSING
    room.deck = [Tile(BLACK, 4, "b4"), Tile(WHITE, 6, "w6")]
    room._begin_turn()

    assert room.current.user_id == "u1"
    room.guess("u1", "B", 1, 9)  # 猜错，回合交给 u2
    assert room.current.user_id == "u2"

    guess = next(b for b in playing_buttons(room) if b.label == "猜牌")
    assert guess.only_for == "u2"
