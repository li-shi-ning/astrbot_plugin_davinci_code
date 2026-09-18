"""《达芬奇密码》AstrBot 插件入口（QQ 官方机器人）。

本文件只做三件事：注册插件、把 QQ 官方群消息路由到
:class:`~src.service.GameService`、把回复连同 ``only_for`` 私密按钮发出。
规则逻辑在 :mod:`src.engine`，消息渲染在 :mod:`src.render`。

私密发牌方案参考 ``astrbot_plugin_official_TexasHoldem``。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

try:  # AstrBot 以包形式加载插件时走相对导入
    from .src.engine import MIN_PLAYERS, PHASE_CONTINUING, PHASE_GUESSING, PHASE_PLACING
    from .src.qqofficial import (
        Button,
        extract_group_context,
        is_qqofficial_event,
        send_group_message,
    )
    from .src.render import hand_payload
    from .src.service import GameError, GameService
except ImportError:  # pragma: no cover - 兼容以顶层模块加载
    plugin_dir = Path(__file__).resolve().parent
    if str(plugin_dir) not in sys.path:
        sys.path.insert(0, str(plugin_dir))
    from src.engine import MIN_PLAYERS, PHASE_CONTINUING, PHASE_GUESSING, PHASE_PLACING
    from src.qqofficial import (
        Button,
        extract_group_context,
        is_qqofficial_event,
        send_group_message,
    )
    from src.render import hand_payload
    from src.service import GameError, GameService


PLUGIN_NAME = "astrbot_plugin_davinci_code"
COMMAND_NAMES = ("达芬奇密码", "达芬奇")


@register(
    PLUGIN_NAME,
    "lishining",
    "QQ 官方机器人群聊《达芬奇密码》推理桌游",
    "1.0.0",
)
class DavinciCodePlugin(Star):
    def __init__(self, context: Context, config: Any = None):
        super().__init__(context)
        self.config = dict(config) if config else {}
        self.with_jokers = self._config_bool("with_jokers", True)
        self.service = GameService(with_jokers=self.with_jokers)

    async def initialize(self) -> None:
        logger.info("[DavinciCode] initialized: with_jokers=%s", self.with_jokers)

    async def terminate(self) -> None:
        self.service.rooms.clear()
        self.service.locks.clear()
        logger.info("[DavinciCode] terminated")

    # ------------------------------------------------------------------
    # 指令入口
    # ------------------------------------------------------------------
    @filter.platform_adapter_type(
        filter.PlatformAdapterType.QQOFFICIAL
        | filter.PlatformAdapterType.QQOFFICIAL_WEBHOOK
    )
    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    @filter.command("达芬奇密码", alias={"达芬奇", "达芬奇密码帮助", "达芬奇菜单"})
    async def davinci_code(self, event: AstrMessageEvent):
        """《达芬奇密码》主指令，按子指令分发。"""
        guard = self._guard(event)
        if guard:
            yield event.plain_result(guard)
            event.stop_event()
            return

        context = extract_group_context(event)
        if context is None:
            yield event.plain_result("无法识别 QQ 官方群聊身份，请稍后重试。")
            event.stop_event()
            return

        action_text = self._strip_prefix(event.message_str)
        lock = self.service.lock(context.group_openid)
        async with lock:
            try:
                text = self.service.dispatch(
                    context.group_openid,
                    context.member_openid,
                    context.display_name,
                    action_text,
                )
            except GameError as exc:
                text = f"⚠️ {exc}"
            except Exception as exc:  # noqa: BLE001 - 单条指令失败不影响其他群
                logger.exception("[DavinciCode] dispatch failed: %s", exc)
                text = "达芬奇密码处理失败，请稍后重试。"
            buttons = self._build_buttons(context.group_openid, context.member_openid)

        if not await send_group_message(event, context, text, buttons):
            yield event.plain_result(text)
        event.stop_event()

    # ------------------------------------------------------------------
    # 按钮布局
    # ------------------------------------------------------------------
    def _build_buttons(self, session_id: str, requester_id: str) -> list[Button]:
        """根据牌局状态生成键盘；私密手牌按钮只对该玩家可点。"""
        room = self.service.room(session_id)
        if room is None:
            return [
                Button("dvc_create", "创建牌局", "达芬奇密码 创建"),
                Button("dvc_rules", "玩法规则", "达芬奇密码 规则"),
            ]
        if not room.started:
            return self._waiting_buttons(room, requester_id)
        return self._playing_buttons(room, requester_id)

    @staticmethod
    def _waiting_buttons(room: Any, requester_id: str) -> list[Button]:
        buttons = [Button("dvc_join", "加入牌局", "达芬奇密码 加入")]
        host = room.players[0] if room.players else None
        if host is not None and len(room.players) >= MIN_PLAYERS:
            buttons.append(
                Button(
                    "dvc_start",
                    "开始游戏",
                    "达芬奇密码 开始",
                    only_for=host.user_id,
                )
            )
        if room.find(requester_id) is not None:
            buttons.append(Button("dvc_leave", "退出牌局", "达芬奇密码 退出"))
        buttons.append(Button("dvc_rules", "玩法规则", "达芬奇密码 规则"))
        return buttons

    @staticmethod
    def _playing_buttons(room: Any, requester_id: str) -> list[Button]:
        buttons: list[Button] = []
        # 私密手牌：每个按钮只有本人能点，内容只进本人输入框
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
        if current is not None and current.user_id == requester_id:
            if room.phase == PHASE_PLACING:
                buttons.append(
                    Button(
                        "dvc_place",
                        "选择百搭位置",
                        "达芬奇密码 放 ",
                        only_for=requester_id,
                    )
                )
            elif room.phase == PHASE_GUESSING:
                buttons.append(
                    Button(
                        "dvc_guess",
                        "猜牌",
                        "达芬奇密码 猜 ",
                        only_for=requester_id,
                    )
                )
            elif room.phase == PHASE_CONTINUING:
                buttons.append(
                    Button(
                        "dvc_guess",
                        "继续猜",
                        "达芬奇密码 猜 ",
                        only_for=requester_id,
                    )
                )
                buttons.append(
                    Button(
                        "dvc_stop",
                        "收手",
                        "达芬奇密码 收手",
                        only_for=requester_id,
                    )
                )

        buttons.append(Button("dvc_state", "牌桌状态", "达芬奇密码 状态"))
        buttons.append(Button("dvc_rules", "玩法规则", "达芬奇密码 规则"))
        if room.players and room.players[0].user_id == requester_id:
            buttons.append(Button("dvc_dissolve", "解散牌局", "达芬奇密码 解散"))
        return buttons

    # ------------------------------------------------------------------
    # 工具
    # ------------------------------------------------------------------
    def _guard(self, event: AstrMessageEvent) -> str | None:
        platform_name = (
            event.get_platform_name() if hasattr(event, "get_platform_name") else ""
        )
        if platform_name not in {"qq_official", "qq_official_webhook"} and not (
            is_qqofficial_event(event)
        ):
            return "达芬奇密码目前仅支持 QQ 官方机器人群聊。"
        return None

    @staticmethod
    def _strip_prefix(raw: str) -> str:
        text = raw.strip()
        for prefix in COMMAND_NAMES:
            if text.startswith(prefix):
                return text[len(prefix) :].strip()
        return text

    def _config_bool(self, key: str, default: bool) -> bool:
        value = (
            self.config.get(key, default) if hasattr(self.config, "get") else default
        )
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on", "是"}
        return bool(value)
