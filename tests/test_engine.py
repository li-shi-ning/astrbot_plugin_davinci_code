"""规则引擎单元测试。"""

from __future__ import annotations

import random

import pytest

from src.engine import (
    BLACK,
    PHASE_CONTINUING,
    PHASE_ENDED,
    PHASE_GUESSING,
    PHASE_PLACING,
    WHITE,
    GameError,
    Room,
    Tile,
    build_deck,
    insert_index,
)


def black(number: int, revealed: bool = False) -> Tile:
    return Tile(BLACK, number, f"b{number}", revealed)


def white(number: int, revealed: bool = False) -> Tile:
    return Tile(WHITE, number, f"w{number}", revealed)


def joker(color: str = BLACK, revealed: bool = False) -> Tile:
    return Tile(color, None, f"{color[0]}j", revealed)


def make_room(players: int = 2, with_jokers: bool = True, seed: int = 7) -> Room:
    room = Room("s1", with_jokers=with_jokers, rng=random.Random(seed))
    for index in range(players):
        room.add_player(f"u{index + 1}", f"玩家{index + 1}")
    return room


def test_build_deck_counts() -> None:
    deck = build_deck()
    assert len(deck) == 26
    assert sum(1 for tile in deck if tile.color == BLACK) == 13
    assert sum(1 for tile in deck if tile.color == WHITE) == 13
    assert sum(1 for tile in deck if tile.is_joker) == 2
    assert len(build_deck(with_jokers=False)) == 24


def test_insert_index_orders_numbers_and_colors() -> None:
    hand = [black(1), joker(), white(4)]
    assert insert_index(hand, black(0)) == 0
    assert insert_index(hand, white(1)) == 2
    assert insert_index(hand, black(5)) == 3


def test_start_deals_sorted_hands() -> None:
    room = make_room(2)
    room.start("u1")
    assert len(room.deck) == 26 - 8 - 1  # 开局后先手已自动抽牌
    for player in room.players:
        numbers = [t.number for t in player.hand if not t.is_joker]
        assert numbers == sorted(numbers)
    four = make_room(4)
    four.start("u1")
    assert all(len(player.hand) == 3 for player in four.players)
    assert len(four.deck) == 26 - 12 - 1


def test_start_requires_host_and_enough_players() -> None:
    with pytest.raises(GameError):
        make_room(1).start("u1")
    room = make_room(2)
    with pytest.raises(GameError):
        room.start("u2")


def _ready_room() -> Room:
    room = make_room(2)
    room.started = True
    room.players[0].hand = [black(1), white(3)]
    room.players[1].hand = [black(5), white(8)]
    room.turn_index = 0
    room.phase = PHASE_GUESSING
    room.deck = [black(4), white(6)]
    room._begin_turn()
    return room


def test_wrong_guess_reveals_clue_tile_and_passes_turn() -> None:
    room = _ready_room()
    drawn = room.players[0].pending
    assert drawn is not None

    outcome = room.guess("u1", "B", 1, 9)

    assert outcome.correct is False
    assert any(tile is drawn and tile.revealed for tile in room.players[0].hand)
    assert room.players[0].hand[2] is drawn  # 白6 插到 白3 之后
    assert room.current is not None and room.current.user_id == "u2"
    assert room.players[1].pending is not None


def test_correct_guess_continues_then_stop_hides_clue_tile() -> None:
    room = _ready_room()
    drawn = room.players[0].pending
    assert drawn is not None

    outcome = room.guess("u1", "B", 1, 5)
    assert outcome.correct is True
    assert room.players[1].hand[0].revealed is True
    assert room.phase == PHASE_CONTINUING

    room.stop("u1")
    assert drawn.revealed is False
    assert room.players[0].pending is None
    assert room.current is not None and room.current.user_id == "u2"


def test_guess_rejects_self_and_revealed_tiles() -> None:
    room = _ready_room()
    with pytest.raises(GameError):
        room.guess("u1", "A", 1, 1)
    room.players[1].hand[0].revealed = True
    with pytest.raises(GameError):
        room.guess("u1", "B", 1, 5)


def test_joker_guess_and_placement() -> None:
    room = _ready_room()
    room.players[1].hand = [joker(WHITE)]

    outcome = room.guess("u1", "B", 1, None)
    assert outcome.correct is True
    assert outcome.tile.is_joker

    room.players[0].pending = joker()
    room.players[0].pending_pos = None
    room.phase = PHASE_PLACING
    room.place_joker("u1", 2)
    assert room.players[0].pending_pos == 1
    assert room.phase == PHASE_GUESSING


def test_deck_exhausted_has_no_penalty() -> None:
    room = _ready_room()
    room.players[0].pending = None
    room.players[0].pending_pos = None
    room.deck = []
    room._begin_turn()
    assert room.players[0].pending is None

    outcome = room.guess("u1", "B", 1, 9)
    assert outcome.correct is False
    assert outcome.no_penalty is True
    assert room.players[0].hand == [black(1), white(3)]
    assert room.current is not None and room.current.user_id == "u2"


def test_elimination_ends_game() -> None:
    room = make_room(2)
    room.started = True
    room.players[0].hand = [black(1)]
    room.players[1].hand = [black(5)]
    room.turn_index = 0
    room.phase = PHASE_GUESSING
    room.deck = []

    outcome = room.guess("u1", "B", 1, 5)

    assert outcome.finished is True
    assert outcome.target_eliminated is True
    assert room.winner == "u1"
    assert room.phase == PHASE_ENDED


def test_self_elimination_by_wrong_guess() -> None:
    room = make_room(2)
    room.started = True
    room.players[0].hand = [black(1, revealed=True)]
    room.players[0].pending = black(2)
    room.players[0].pending_pos = None
    room.players[1].hand = [white(5)]
    room.turn_index = 0
    room.phase = PHASE_GUESSING
    room.deck = []

    outcome = room.guess("u1", "B", 1, 9)

    assert outcome.self_eliminated is True
    assert room.winner == "u2"
    assert room.phase == PHASE_ENDED


def test_random_game_terminates_with_one_winner() -> None:
    room = make_room(3, seed=42)
    room.start("u1")
    rng = random.Random(2024)
    for _ in range(5000):
        if room.phase == PHASE_ENDED:
            break
        current = room.current
        assert current is not None
        if room.phase == PHASE_PLACING:
            room.place_joker(current.user_id, 1)
            continue
        if room.phase == PHASE_CONTINUING:
            room.stop(current.user_id)
            continue
        targets = [p for p in room.players if p.alive and p is not current]
        hidden = [
            (p, index + 1, tile)
            for p in targets
            for index, tile in enumerate(p.hand)
            if not tile.revealed
        ]
        assert hidden, "仍有存活对手时必然存在暗牌"
        target, position, tile = rng.choice(hidden)
        number = None if tile.is_joker else tile.number
        room.guess(current.user_id, target.label, position, number)

    assert room.phase == PHASE_ENDED
    assert room.winner is not None
    assert len(room.alive_players()) == 1
