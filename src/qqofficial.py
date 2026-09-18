"""QQ 官方机器人（qq_official / qq_official_webhook）适配工具。

私密发牌依赖 QQ 官方 inline keyboard：

* ``permission.type=0`` + ``specify_user_ids`` 限定只有本人可点击；
* ``action.enter=False`` 让按钮内容只填入本人输入框，不会直接发到群里。

这套“私密发牌”方案参考自 ``astrbot_plugin_official_TexasHoldem``。
"""

from __future__ import annotations

import itertools
import random
from dataclasses import dataclass
from typing import Any

try:  # 允许在未安装 AstrBot 的环境下单独导入本模块做测试
    from astrbot.api import logger
except ImportError:  # pragma: no cover
    import logging

    logger = logging.getLogger("astrbot_plugin_davinci_code")

QQOFFICIAL_PLATFORMS = {"qq_official", "qq_official_webhook"}
QQOFFICIAL_EVENT_NAMES = {
    "QQOfficialMessageEvent",
    "QQOfficialWebhookMessageEvent",
}
QQOFFICIAL_EVENT_MODULE_PREFIXES = (
    "astrbot.core.platform.sources.qqofficial.",
    "astrbot.core.platform.sources.qqofficial_webhook.",
)

# 同一条用户消息的多次回复必须用不同的 msg_seq，改用递增计数器避免撞车
_SEQ_COUNTER = itertools.count(random.randint(1, 5000))

MAX_BUTTONS = 25
BUTTONS_PER_ROW = 3
CROWDED_BUTTONS_PER_ROW = 5
MAX_ROWS = 5


@dataclass(frozen=True)
class Button:
    """一个 QQ 官方 inline keyboard 按钮。"""

    button_id: str
    label: str
    data: str
    only_for: str | None = None


@dataclass(frozen=True)
class GroupContext:
    """从 QQ 官方群事件中提取的可信身份信息。"""

    group_openid: str
    member_openid: str
    display_name: str
    message_id: str = ""
    msg_seq: int | None = None


def is_qqofficial_event(event: Any) -> bool:
    """判断事件是否为 QQ 官方适配器产生（不依赖 AstrBot 平台实现）。"""
    event_type = type(event)
    module_name = event_type.__module__.lower()
    return event_type.__name__ in QQOFFICIAL_EVENT_NAMES and module_name.startswith(
        QQOFFICIAL_EVENT_MODULE_PREFIXES
    )


def extract_group_context(event: Any) -> GroupContext | None:
    """读取群/成员身份，优先使用平台下发的可信 openid 字段。"""
    raw = getattr(getattr(event, "message_obj", None), "raw_message", None)
    author = getattr(raw, "author", None)
    group_openid = _first_str(
        getattr(raw, "group_openid", None),
        _safe_call(event, "get_group_id"),
    )
    member_openid = _first_str(
        getattr(author, "member_openid", None),
        getattr(raw, "member_openid", None),
        _safe_call(event, "get_sender_id"),
    )
    if not group_openid or not member_openid:
        return None
    message_id = _first_str(
        getattr(raw, "id", None),
        getattr(getattr(event, "message_obj", None), "message_id", None),
    )
    display_name = _first_str(
        _safe_call(event, "get_sender_name"),
        getattr(author, "username", None),
    )
    return GroupContext(
        group_openid=str(group_openid),
        member_openid=str(member_openid),
        display_name=display_name or f"玩家_{str(member_openid)[-6:]}",
        message_id=str(message_id or ""),
        msg_seq=_as_int(getattr(raw, "msg_seq", None)),
    )


def build_button(button: Button) -> dict[str, Any]:
    """构造单个指令按钮。

    ``only_for`` 使用 ``permission.type=0`` 限定可点击用户；``enter=False``
    保证点击后内容只进入输入框，不直接发送。
    """
    if button.only_for:
        permission: dict[str, Any] = {
            "type": 0,
            "specify_user_ids": [button.only_for],
        }
    else:
        permission = {"type": 2}
    return {
        "id": button.button_id,
        "render_data": {
            "label": button.label,
            "visited_label": button.label,
            "style": 1,
        },
        "action": {
            "type": 2,
            "permission": permission,
            "data": button.data,
            "reply": True,
            "enter": False,
            "unsupport_tips": "当前客户端暂不支持该按钮",
        },
    }


def build_keyboard(buttons: list[Button]) -> dict[str, Any] | None:
    """把按钮排成 QQ 官方键盘，最多 25 个、5 行。"""
    if not buttons:
        return None
    limited = buttons[:MAX_BUTTONS]
    per_row = (
        CROWDED_BUTTONS_PER_ROW
        if len(limited) > MAX_ROWS * BUTTONS_PER_ROW
        else BUTTONS_PER_ROW
    )
    rows = [
        {"buttons": [build_button(spec) for spec in limited[index : index + per_row]]}
        for index in range(0, len(limited), per_row)
    ]
    return {"content": {"rows": rows[:MAX_ROWS]}}


def build_payload(text: str, buttons: list[Button] | None = None) -> dict[str, Any]:
    """构造 ``post_group_message`` 的 Markdown + 键盘参数。"""
    payload: dict[str, Any] = {"msg_type": 2, "markdown": {"content": text}}
    keyboard = build_keyboard(buttons or [])
    if keyboard is not None:
        payload["keyboard"] = keyboard
    return payload


async def send_group_message(
    event: Any,
    context: GroupContext,
    text: str,
    buttons: list[Button] | None = None,
) -> bool:
    """发送 Markdown + 键盘消息。

    Returns:
        调用成功返回 ``True``；失败返回 ``False``，调用方应回退到纯文本。
    """
    api = getattr(getattr(event, "bot", None), "api", None)
    post_group_message = getattr(api, "post_group_message", None)
    if not callable(post_group_message):
        return False

    payload = build_payload(text, buttons)
    if context.message_id:
        payload["msg_id"] = context.message_id
        payload["msg_seq"] = (
            context.msg_seq if context.msg_seq is not None else random.randint(1, 10000)
        )
    try:
        await post_group_message(group_openid=context.group_openid, **payload)
        return True
    except Exception as exc:  # noqa: BLE001 - 平台/网络故障不应中断牌局
        logger.warning("[DavinciCode] send group markdown failed: %s", exc)
        return False


def passive_fields(context: GroupContext) -> dict[str, Any]:
    """被动回复所需的 ``msg_id`` / ``msg_seq``（同一消息需用不同 seq）。"""
    if not context.message_id:
        return {}
    return {"msg_id": context.message_id, "msg_seq": next(_SEQ_COUNTER) % 10000 + 1}


async def send_group_media(
    event: Any,
    context: GroupContext,
    file_path: Any,
) -> bool:
    """上传本地图片并用富媒体消息（``msg_type=7``）发送。

    QQ 富媒体消息不能和 Markdown 同条，因此牌桌图片单独发送，
    按钮仍由 :func:`send_group_message` 的 Markdown 消息承载。

    Args:
        event: QQ 官方消息事件（需带 ``upload_group_and_c2c_media``）。
        context: 群上下文。
        file_path: 本地图片路径。

    Returns:
        发送成功返回 ``True``，失败返回 ``False``。
    """
    uploader = getattr(event, "upload_group_and_c2c_media", None)
    api = getattr(getattr(event, "bot", None), "api", None)
    post_group_message = getattr(api, "post_group_message", None)
    if not callable(uploader) or not callable(post_group_message):
        return False

    try:
        media = await uploader(
            file_source=str(file_path),
            file_type=1,
            group_openid=context.group_openid,
        )
    except Exception as exc:  # noqa: BLE001 - 上传失败要能退回 Markdown 牌桌
        logger.warning("[DavinciCode] upload board image failed: %s", exc)
        return False

    payload: dict[str, Any] = {"msg_type": 7, "media": media}
    payload.update(passive_fields(context))
    try:
        await post_group_message(group_openid=context.group_openid, **payload)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("[DavinciCode] send board image failed: %s", exc)
        return False


def _first_str(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value)
        if text:
            return text
    return None


def _safe_call(target: Any, name: str) -> Any:
    method = getattr(target, name, None)
    if not callable(method):
        return None
    try:
        return method()
    except Exception:  # noqa: BLE001 - 事件兼容失败时不阻断
        return None


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
