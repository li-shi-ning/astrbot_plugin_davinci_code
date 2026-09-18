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
from astrbot.api.star import Context, Star

try:  # AstrBot 以包形式加载插件时走相对导入
    from .src import cards
    from .src.buttons import build_buttons
    from .src.qqofficial import (
        extract_group_context,
        is_qqofficial_event,
        send_group_message,
    )
    from .src.service import GameError, GameService
except ImportError:  # pragma: no cover - 兼容以顶层模块加载
    plugin_dir = Path(__file__).resolve().parent
    if str(plugin_dir) not in sys.path:
        sys.path.insert(0, str(plugin_dir))
    from src import cards
    from src.buttons import build_buttons
    from src.qqofficial import (
        extract_group_context,
        is_qqofficial_event,
        send_group_message,
    )
    from src.service import GameError, GameService


COMMAND_NAMES = ("达芬奇密码", "达芬奇")


class DavinciCodePlugin(Star):
    """QQ 官方机器人群聊《达芬奇密码》推理桌游。"""

    def __init__(self, context: Context, config: Any = None):
        super().__init__(context)
        self.config = dict(config) if config else {}
        self.with_jokers = self._config_bool("with_jokers", True)
        self.card_image_base = self._config_str("card_image_base", cards.DEFAULT_BASE)
        size_text = self._config_str("card_image_size", "32x48")
        cards.configure(self.card_image_base, *cards.parse_size(size_text))
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
            buttons = build_buttons(
                self.service.room(context.group_openid), context.member_openid
            )

        if not await send_group_message(event, context, text, buttons):
            yield event.plain_result(text)
        event.stop_event()

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

    def _config_str(self, key: str, default: str) -> str:
        value = (
            self.config.get(key, default) if hasattr(self.config, "get") else default
        )
        text = str(value).strip() if value else ""
        return text or default

    def _config_bool(self, key: str, default: bool) -> bool:
        value = (
            self.config.get(key, default) if hasattr(self.config, "get") else default
        )
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on", "是"}
        return bool(value)
