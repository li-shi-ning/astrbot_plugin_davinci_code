"""牌局会话管理：解析指令、驱动规则引擎、拼装文本回复。

本模块不直接与 AstrBot 交互，私密信息（手牌）由 ``main.py`` 通过
QQ 官方 ``only_for`` 按钮下发。
"""

from __future__ import annotations

import asyncio
import re

from .engine import (
    MAX_PLAYERS,
    GameError,
    Room,
)
from .render import render_help, render_outcome, render_rules, render_table

ACTION_ALIASES = {
    "创建": "create",
    "新建": "create",
    "开房": "create",
    "加入": "join",
    "参加": "join",
    "开始": "start",
    "开局": "start",
    "状态": "state",
    "牌桌": "state",
    "局势": "state",
    "我的牌": "hand",
    "手牌": "hand",
    "看牌": "hand",
    "猜": "guess",
    "猜测": "guess",
    "收手": "stop",
    "结束回合": "stop",
    "不猜了": "stop",
    "放": "place",
    "放置": "place",
    "退出": "leave",
    "离开": "leave",
    "解散": "dissolve",
    "结束": "dissolve",
    "帮助": "help",
    "菜单": "help",
    "指令": "help",
    "规则": "rules",
    "玩法": "rules",
}

JOKER_WORDS = {"-", "－", "—", "百搭", "万能", "赖子", "joker", "j", "*"}


class GameService:
    """按会话（群）维护若干牌局。"""

    def __init__(self, with_jokers: bool = True) -> None:
        self.with_jokers = with_jokers
        self.rooms: dict[str, Room] = {}
        self.locks: dict[str, asyncio.Lock] = {}

    def lock(self, session_id: str) -> asyncio.Lock:
        return self.locks.setdefault(session_id, asyncio.Lock())

    def room(self, session_id: str) -> Room | None:
        return self.rooms.get(session_id)

    def dispatch(self, session_id: str, user_id: str, name: str, text: str) -> str:
        """解析并执行一条指令，返回应展示的文本。"""
        action, rest = self._parse_action(text)
        if action in (None, "help"):
            return render_help()
        if action == "rules":
            return render_rules()
        if action == "create":
            return self._create(session_id, user_id, name)
        if action == "join":
            return self._join(session_id, user_id, name)
        if action == "start":
            return self._start(session_id, user_id)
        if action == "state":
            return render_table(self._require_room(session_id))
        if action == "hand":
            return self._hand(session_id, user_id)
        if action == "guess":
            return self._guess(session_id, user_id, rest)
        if action == "stop":
            return self._stop(session_id, user_id, name)
        if action == "place":
            return self._place(session_id, user_id, rest)
        if action == "leave":
            return self._leave(session_id, user_id, name)
        if action == "dissolve":
            return self._dissolve(session_id, user_id)
        raise GameError("无法识别的指令，点击「玩法规则」或发送「达芬奇密码 帮助」")

    # ------------------------------------------------------------------
    # 指令实现
    # ------------------------------------------------------------------
    def _create(self, session_id: str, user_id: str, name: str) -> str:
        if session_id in self.rooms:
            raise GameError("本群已经有一个牌局了，发送「达芬奇密码 状态」查看")
        room = Room(session_id, with_jokers=self.with_jokers)
        room.add_player(user_id, name)
        self.rooms[session_id] = room
        flavor = "含百搭" if self.with_jokers else "不含百搭"
        return (
            f"🎲 {name} 创建了达芬奇密码牌局（{flavor}）\n\n"
            f"{render_table(room)}\n\n"
            "其他玩家点击「加入牌局」，房主点击「开始游戏」（2-4 人）。"
        )

    def _join(self, session_id: str, user_id: str, name: str) -> str:
        room = self._require_room(session_id)
        room.add_player(user_id, name)
        return (
            f"👋 {name} 加入牌局（{len(room.players)}/{MAX_PLAYERS}）\n\n"
            f"{render_table(room)}"
        )

    def _start(self, session_id: str, user_id: str) -> str:
        room = self._require_room(session_id)
        room.start(user_id)
        return render_table(room)

    def _hand(self, session_id: str, user_id: str) -> str:
        room = self._require_room(session_id)
        player = room.find(user_id)
        if player is None:
            raise GameError("你不在牌局中")
        return (
            f"📩 {player.label} {player.name}，点击下方属于你的「手牌」按钮查看。"
            "内容只会填入你自己的输入框，看完请勿发送。"
        )

    def _guess(self, session_id: str, user_id: str, rest: str) -> str:
        room = self._require_room(session_id)
        label, position, number = self._parse_guess(room, rest)
        outcome = room.guess(user_id, label, position, number)
        return f"{render_outcome(outcome)}\n\n{render_table(room)}"

    def _stop(self, session_id: str, user_id: str, name: str) -> str:
        room = self._require_room(session_id)
        room.stop(user_id)
        return f"🛑 {name} 收手，线索牌暗扣入列\n\n{render_table(room)}"

    def _place(self, session_id: str, user_id: str, rest: str) -> str:
        room = self._require_room(session_id)
        token = rest.strip()
        if not token.isdigit():
            raise GameError("用法：达芬奇密码 放 <位置>，例如「达芬奇密码 放 2」")
        room.place_joker(user_id, int(token))
        return render_table(room)

    def _leave(self, session_id: str, user_id: str, name: str) -> str:
        room = self._require_room(session_id)
        room.remove_player(user_id)
        if not room.players:
            self.rooms.pop(session_id, None)
            return "牌局已随最后一名玩家退出而解散。"
        return f"👋 {name} 退出了牌局\n\n{render_table(room)}"

    def _dissolve(self, session_id: str, user_id: str) -> str:
        room = self._require_room(session_id)
        if room.players and room.players[0].user_id != user_id:
            raise GameError("只有房主可以解散牌局")
        self.rooms.pop(session_id, None)
        return "🧹 牌局已解散。"

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------
    def _require_room(self, session_id: str) -> Room:
        room = self.rooms.get(session_id)
        if room is None:
            raise GameError("本群还没有牌局，点击「创建牌局」开一局吧")
        return room

    @staticmethod
    def _parse_action(text: str) -> tuple[str | None, str]:
        text = text.strip()
        if not text:
            return None, ""
        for alias in sorted(ACTION_ALIASES, key=len, reverse=True):
            if text.startswith(alias):
                return ACTION_ALIASES[alias], text[len(alias) :].strip()
        return None, text

    def _parse_guess(self, room: Room, rest: str) -> tuple[str, int, int | None]:
        parts = [p for p in re.split(r"[\s,，]+", rest.strip()) if p]
        if len(parts) == 2:
            target_token, number_token = parts
            match = re.fullmatch(r"([A-Za-z])(\d+)", target_token)
            if match is None:
                raise GameError("用法：达芬奇密码 猜 <玩家字母><位置> <数字>")
            label, position = match.group(1).upper(), int(match.group(2))
        elif len(parts) == 3:
            label = self._resolve_target(room, parts[0])
            position = int(parts[1])
            number_token = parts[2]
        else:
            raise GameError("用法：达芬奇密码 猜 <玩家字母><位置> <数字>")
        if len(parts) == 2:
            label = self._resolve_target(room, label)
        return label, position, self._parse_number(number_token)

    @staticmethod
    def _resolve_target(room: Room, token: str) -> str:
        token = token.lstrip("@")
        if len(token) == 1 and token.upper() in {"A", "B", "C", "D"}:
            return token.upper()
        matches = [p for p in room.players if p.name == token]
        if not matches:
            matches = [p for p in room.players if token in p.name]
        if len(matches) == 1:
            return matches[0].label
        if len(matches) > 1:
            raise GameError("玩家昵称不唯一，请改用字母 A/B/C/D")
        raise GameError(f"找不到玩家「{token}」，可用字母 A/B/C/D 指定")

    @staticmethod
    def _parse_number(token: str) -> int | None:
        lowered = token.strip().lower()
        if lowered in JOKER_WORDS:
            return None
        if lowered.isdigit():
            number = int(lowered)
            if 0 <= number <= 11:
                return number
        raise GameError("猜测的数字需要在 0-11 之间，猜百搭请用 -")
