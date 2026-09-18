"""《达芬奇密码》规则引擎。

本模块是纯逻辑实现，不依赖 AstrBot，方便单元测试与复用。
规则来源与设计说明见仓库 ``docs/rules.md``。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

BLACK = "black"
WHITE = "white"

COLOR_CN = {BLACK: "黑", WHITE: "白"}

# 房间/回合阶段
PHASE_WAITING = "waiting"  # 等待开局
PHASE_PLACING = "placing"  # 抽到百搭，等待选择插入位置
PHASE_GUESSING = "guessing"  # 等待本回合第一次猜测
PHASE_CONTINUING = "continuing"  # 猜中后，等待“继续猜 / 收手”
PHASE_ENDED = "ended"  # 对局结束

LABELS = ("A", "B", "C", "D")
MIN_PLAYERS = 2
MAX_PLAYERS = 4
JOKER_GUESS = -1  # 猜测“百搭”时使用的哨兵值


class GameError(Exception):
    """玩家操作不合法时抛出，异常信息可直接展示给玩家。"""


@dataclass
class Tile:
    """一张木牌。``number`` 为 ``None`` 时代表百搭牌。"""

    color: str
    number: int | None
    uid: str
    revealed: bool = False

    @property
    def is_joker(self) -> bool:
        return self.number is None

    @property
    def text(self) -> str:
        """公开/私有场景下用于展示的牌面文字。"""
        if self.is_joker:
            return "百搭"
        return f"{COLOR_CN[self.color]}{self.number}"


@dataclass
class Player:
    """一名玩家。``hand`` 按从小到大的顺序排列。"""

    user_id: str
    name: str
    label: str
    hand: list[Tile] = field(default_factory=list)
    alive: bool = True
    # 本回合抽到、尚未放入牌列的“线索牌”
    pending: Tile | None = None
    # 插入牌列时的下标，抽到百搭时由玩家指定
    pending_pos: int | None = None


@dataclass
class GuessOutcome:
    """一次猜测的结果，用于拼装播报文案。"""

    guesser_label: str
    guesser_name: str
    target_label: str
    target_name: str
    tile: Tile
    position: int
    guessed: int | None
    correct: bool
    # 猜错时被亮出的线索牌（=猜错者本回合抽到的牌），绝不包含对手底牌
    penalty: Tile | None = None
    target_eliminated: bool = False
    finished: bool = False
    winner_label: str | None = None
    winner_name: str | None = None
    self_eliminated: bool = False
    no_penalty: bool = False  # 牌堆已空，猜错无需亮牌


def build_deck(with_jokers: bool = True) -> list[Tile]:
    """生成牌堆：黑白各 0-11，可选各加一张百搭。"""
    tiles: list[Tile] = []
    for color, prefix in ((BLACK, "b"), (WHITE, "w")):
        tiles.extend(Tile(color, n, f"{prefix}{n}") for n in range(12))
        if with_jokers:
            tiles.append(Tile(color, None, f"{prefix}j"))
    return tiles


def sort_key(tile: Tile) -> tuple[int, int]:
    """数字牌排序键：数字升序，同数字黑色在白色左边。"""
    number = tile.number if tile.number is not None else 0
    return (number, 0 if tile.color == BLACK else 1)


def insert_index(hand: list[Tile], tile: Tile) -> int:
    """计算一张数字牌插入牌列后的下标，百搭牌不参与比较。"""
    for i, current in enumerate(hand):
        if current.is_joker:
            continue
        if sort_key(current) > sort_key(tile):
            return i
    return len(hand)


class Room:
    """一局《达芬奇密码》。"""

    def __init__(
        self,
        session_id: str,
        with_jokers: bool = True,
        rng: random.Random | None = None,
    ) -> None:
        self.session_id = session_id
        self.with_jokers = with_jokers
        self.rng = rng or random.Random()
        self.players: list[Player] = []
        self.deck: list[Tile] = []
        self.turn_index = 0
        self.phase = PHASE_WAITING
        self.started = False
        self.winner: str | None = None

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------
    @property
    def current(self) -> Player | None:
        if not self.players:
            return None
        return self.players[self.turn_index]

    def find(self, user_id: str) -> Player | None:
        return next((p for p in self.players if p.user_id == user_id), None)

    def find_by_label(self, label: str) -> Player | None:
        label = label.upper()
        return next((p for p in self.players if p.label == label), None)

    def alive_players(self) -> list[Player]:
        return [p for p in self.players if p.alive]

    # ------------------------------------------------------------------
    # 房间管理
    # ------------------------------------------------------------------
    def add_player(self, user_id: str, name: str) -> Player:
        if self.started:
            raise GameError("本局已经开始了，无法加入")
        if len(self.players) >= MAX_PLAYERS:
            raise GameError(f"房间已满（最多 {MAX_PLAYERS} 人）")
        if self.find(user_id):
            raise GameError("你已经在房间里了")
        player = Player(user_id=user_id, name=name, label=LABELS[len(self.players)])
        self.players.append(player)
        return player

    def remove_player(self, user_id: str) -> None:
        if self.started:
            raise GameError("对局进行中无法退出，请让房主解散牌局")
        player = self.find(user_id)
        if player is None:
            raise GameError("你不在房间里")
        self.players.remove(player)
        for index, remaining in enumerate(self.players):
            remaining.label = LABELS[index]

    def start(self, user_id: str) -> None:
        if not self.players:
            raise GameError("房间里还没有玩家")
        if self.players[0].user_id != user_id:
            raise GameError("只有房主可以开始游戏")
        if len(self.players) < MIN_PLAYERS:
            raise GameError(f"至少需要 {MIN_PLAYERS} 名玩家才能开始")
        if self.started:
            raise GameError("本局已经开始了")

        self.deck = build_deck(self.with_jokers)
        self.rng.shuffle(self.deck)
        hand_size = 3 if len(self.players) >= 4 else 4
        for player in self.players:
            player.hand = [self.deck.pop() for _ in range(hand_size)]
            self._arrange_initial_hand(player)
            player.alive = True
            player.pending = None
            player.pending_pos = None

        self.started = True
        self.winner = None
        self.turn_index = self.rng.randrange(len(self.players))
        self._begin_turn()

    def _arrange_initial_hand(self, player: Player) -> None:
        """初始手牌排序；百搭随机插入，避免首回合泄露位置信息。"""
        numbered = sorted((t for t in player.hand if not t.is_joker), key=sort_key)
        for joker in (t for t in player.hand if t.is_joker):
            numbered.insert(self.rng.randint(0, len(numbered)), joker)
        player.hand = numbered

    # ------------------------------------------------------------------
    # 回合流程
    # ------------------------------------------------------------------
    def _begin_turn(self) -> None:
        """开始当前玩家的回合：自动抽一张线索牌。"""
        current = self.current
        if current is None:
            self.phase = PHASE_ENDED
            return
        current.pending = None
        current.pending_pos = None
        if self.deck:
            tile = self.deck.pop()
            current.pending = tile
            if tile.is_joker:
                self.phase = PHASE_PLACING
            else:
                current.pending_pos = insert_index(current.hand, tile)
                self.phase = PHASE_GUESSING
        else:
            # 牌堆抽空后仍可继续猜测，但猜错无需亮牌
            self.phase = PHASE_GUESSING

    def place_joker(self, user_id: str, position: int) -> None:
        if self.phase != PHASE_PLACING:
            raise GameError("现在不需要放置百搭")
        current = self._require_current(user_id)
        if current.pending is None or not current.pending.is_joker:
            raise GameError("当前没有待放置的百搭")
        max_pos = len(current.hand) + 1
        if not 1 <= position <= max_pos:
            raise GameError(f"位置需要在 1 到 {max_pos} 之间")
        current.pending_pos = position - 1
        self.phase = PHASE_GUESSING

    def guess(
        self,
        user_id: str,
        target_label: str,
        position: int,
        number: int | None,
    ) -> GuessOutcome:
        if self.phase not in (PHASE_GUESSING, PHASE_CONTINUING):
            raise GameError("现在不能猜牌")
        current = self._require_current(user_id)
        target = self.find_by_label(target_label)
        if target is None:
            raise GameError("找不到这名玩家")
        if target.user_id == current.user_id:
            raise GameError("不能猜自己的牌")
        if not target.alive:
            raise GameError("该玩家已经出局")
        if not 1 <= position <= len(target.hand):
            raise GameError(f"该玩家只有 {len(target.hand)} 张牌")
        tile = target.hand[position - 1]
        if tile.revealed:
            raise GameError("这张牌已经翻开了")

        correct = (tile.is_joker and number is None) or (
            not tile.is_joker and number == tile.number
        )
        outcome = GuessOutcome(
            guesser_label=current.label,
            guesser_name=current.name,
            target_label=target.label,
            target_name=target.name,
            tile=tile,
            position=position,
            guessed=number,
            correct=correct,
        )

        if correct:
            tile.revealed = True
            if all(t.revealed for t in target.hand):
                target.alive = False
                outcome.target_eliminated = True
            alive = self.alive_players()
            if len(alive) <= 1:
                self._finish(alive[0] if alive else None)
            else:
                self.phase = PHASE_CONTINUING
        else:
            outcome.no_penalty = current.pending is None
            if current.pending is not None:
                outcome.penalty = current.pending
                self._insert_pending(current, revealed=True)
                if all(t.revealed for t in current.hand):
                    current.alive = False
                    outcome.self_eliminated = True
            self._advance_turn()

        outcome.finished = self.phase == PHASE_ENDED
        winner = self.find(self.winner) if self.winner else None
        if winner is not None:
            outcome.winner_label = winner.label
            outcome.winner_name = winner.name
        return outcome

    def stop(self, user_id: str) -> None:
        """猜中后主动收手，线索牌背面朝上放入牌列。"""
        if self.phase != PHASE_CONTINUING:
            raise GameError("现在不需要结束回合")
        current = self._require_current(user_id)
        if current.pending is not None:
            self._insert_pending(current, revealed=False)
        self._advance_turn()

    def _insert_pending(self, player: Player, revealed: bool) -> None:
        tile = player.pending
        if tile is None:
            return
        tile.revealed = revealed
        position = player.pending_pos
        if position is None:
            position = len(player.hand)
        position = max(0, min(position, len(player.hand)))
        player.hand.insert(position, tile)
        player.pending = None
        player.pending_pos = None

    def _advance_turn(self) -> None:
        alive = self.alive_players()
        if len(alive) <= 1:
            self._finish(alive[0] if alive else None)
            return
        index = self.turn_index
        for _ in range(len(self.players)):
            index = (index + 1) % len(self.players)
            if self.players[index].alive:
                break
        self.turn_index = index
        self._begin_turn()

    def _finish(self, winner: Player | None) -> None:
        self.phase = PHASE_ENDED
        self.winner = winner.user_id if winner else None

    def _require_current(self, user_id: str) -> Player:
        current = self.current
        if current is None:
            raise GameError("当前没有进行中的回合")
        if current.user_id != user_id:
            raise GameError(f"现在轮到 {current.label}({current.name})")
        return current
