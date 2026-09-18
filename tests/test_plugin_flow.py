"""插件入口集成测试（需要 AstrBot 运行环境）。"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

pytest.importorskip("astrbot")

import main as plugin_main  # noqa: E402


class FakeAPI:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def post_group_message(self, **kwargs):
        self.calls.append(kwargs)
        return {"id": "fake"}


class FakeEvent:
    def __init__(self, text: str, user_id: str, name: str) -> None:
        raw = SimpleNamespace(
            group_openid="g1",
            id="msg1",
            msg_seq=1,
            author=SimpleNamespace(member_openid=user_id, username=name),
        )
        self.message_str = text
        self.message_obj = SimpleNamespace(raw_message=raw, message_id="msg1")
        self.bot = SimpleNamespace(api=FakeAPI())
        self.stopped = False

    def get_platform_name(self) -> str:
        return "qq_official"

    def get_group_id(self) -> str:
        return "g1"

    def stop_event(self) -> None:
        self.stopped = True

    def plain_result(self, text: str) -> str:
        return text


async def _drain(plugin, event: FakeEvent) -> None:
    async for _ in plugin.davinci_code(event):
        pass


def _run(plugin, text: str, user_id: str, name: str) -> FakeEvent:
    event = FakeEvent(text, user_id, name)
    asyncio.run(_drain(plugin, event))
    return event


def _labels(call: dict) -> list[str]:
    rows = call.get("keyboard", {}).get("content", {}).get("rows", [])
    return [b["render_data"]["label"] for row in rows for b in row["buttons"]]


def test_full_setup_flow_and_private_hand_buttons() -> None:
    plugin = plugin_main.DavinciCodePlugin(context=None, config={"with_jokers": True})

    create = _run(plugin, "达芬奇密码 创建", "u1", "甲")
    assert create.stopped is True
    assert "加入牌局" in _labels(create.bot.api.calls[0])

    _run(plugin, "达芬奇密码 加入", "u2", "乙")
    started = _run(plugin, "达芬奇密码 开始", "u1", "甲")
    call = started.bot.api.calls[0]
    labels = _labels(call)
    assert "A·手牌" in labels
    assert "B·手牌" in labels

    rows = call["keyboard"]["content"]["rows"]
    hands = [
        b for row in rows for b in row["buttons"] if b["id"].startswith("dvc_hand_")
    ]
    assert hands[0]["action"]["permission"] == {
        "type": 0,
        "specify_user_ids": ["u1"],
    }
    assert hands[0]["action"]["enter"] is False
    assert "手牌" in hands[0]["action"]["data"]
