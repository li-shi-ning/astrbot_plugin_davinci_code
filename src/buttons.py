"""根据牌局状态生成 QQ 官方键盘。

私密手牌按钮的 ``only_for`` 只对该玩家可点，``data`` 会被填入本人输入框。
"""

from __future__ import annotations

from .engine import (
    MIN_PLAYERS,
    PHASE_CONTINUING,
    PHASE_GUESSING,
    Room,
)
from .qqofficial import Button
from .render import hand_payload


def build_buttons(room: Room | None, requester_id: str) -> list[Button]:
    """按当前状态返回一组按钮。"""
    if room is None:
        return [
            Button("dvc_create", "创建牌局", "达芬奇密码 创建"),
            Button("dvc_rules", "玩法规则", "达芬奇密码 规则"),
        ]
    if not room.started:
        return waiting_buttons(room, requester_id)
    return playing_buttons(room)


def waiting_buttons(room: Room, requester_id: str) -> list[Button]:
    """未开局：加入 / 开始 / 退出 / 规则。"""
    buttons = [Button("dvc_join", "加入牌局", "达芬奇密码 加入")]
    host = room.players[0] if room.players else None
    if host is not None and len(room.players) >= MIN_PLAYERS:
        buttons.append(
            Button("dvc_start", "开始游戏", "达芬奇密码 开始", only_for=host.user_id)
        )
    if room.find(requester_id) is not None:
        buttons.append(Button("dvc_leave", "退出牌局", "达芬奇密码 退出"))
    buttons.append(Button("dvc_rules", "玩法规则", "达芬奇密码 规则"))
    return buttons


def playing_buttons(room: Room) -> list[Button]:
    """进行中：私密手牌 + 当前玩家操作 + 公开操作。

    操作按钮按 **当前回合玩家** 生成（``only_for`` 只允许他点击），
    这样无论谁触发这条消息，轮到的人都能看到自己的「猜牌 / 收手」按钮。
    """
    buttons: list[Button] = []
    for index, player in enumerate(room.players):
        buttons.append(
            Button(
                f"dvc_hand_{index}",
                f"{player.label}·手牌",
                hand_payload(player, room),
                only_for=player.user_id,
            )
        )

    current = room.current
    if current is not None:
        actor = current.user_id
        if room.phase == PHASE_GUESSING:
            buttons.append(
                Button("dvc_guess", "猜牌", "达芬奇密码 猜 ", only_for=actor)
            )
        elif room.phase == PHASE_CONTINUING:
            buttons.append(
                Button("dvc_guess", "继续猜", "达芬奇密码 猜 ", only_for=actor)
            )
            buttons.append(
                Button("dvc_stop", "收手", "达芬奇密码 收手", only_for=actor)
            )

    buttons.append(Button("dvc_state", "牌桌状态", "达芬奇密码 状态"))
    buttons.append(Button("dvc_rules", "玩法规则", "达芬奇密码 规则"))
    if room.players:
        buttons.append(
            Button(
                "dvc_dissolve",
                "解散牌局",
                "达芬奇密码 解散",
                only_for=room.players[0].user_id,
            )
        )
    return buttons
