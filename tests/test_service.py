"""指令解析与会话管理测试。"""

from __future__ import annotations

import pytest

from src.engine import GameError
from src.service import GameService, Reply


def flat(reply: Reply) -> str:
    """把 Reply 的三段拼起来，便于做子串断言。"""
    return "\n\n".join(p for p in (reply.text, reply.table, reply.hint) if p)


def test_parse_action_variants() -> None:
    assert GameService._parse_action("创建") == ("create", "")
    assert GameService._parse_action("猜 B3 7") == ("guess", "B3 7")
    assert GameService._parse_action("结束回合") == ("stop", "")
    assert GameService._parse_action("结束") == ("dissolve", "")
    assert GameService._parse_action("规则") == ("rules", "")
    assert GameService._parse_action("随便说点什么")[0] is None


def test_create_join_start_flow() -> None:
    service = GameService()
    text = flat(service.dispatch("g1", "u1", "甲", "创建"))
    assert "创建了牌局" in text
    assert service.room("g1") is not None

    text = flat(service.dispatch("g1", "u2", "乙", "加入"))
    assert "加入" in text

    with pytest.raises(GameError):
        service.dispatch("g1", "u2", "乙", "开始")

    text = flat(service.dispatch("g1", "u1", "甲", "开始"))
    assert "轮到" in text
    room = service.room("g1")
    assert room is not None and room.started


def test_dispatch_without_room_hints_create() -> None:
    service = GameService()
    with pytest.raises(GameError):
        service.dispatch("g1", "u1", "甲", "状态")
    menu_text = flat(service.dispatch("g1", "u1", "甲", ""))
    assert "达芬奇密码" in menu_text
    help_text = flat(service.dispatch("g1", "u1", "甲", "帮助"))
    assert "猜 B3 7" in help_text


def test_duplicate_create_rejected() -> None:
    service = GameService()
    service.dispatch("g1", "u1", "甲", "创建")
    with pytest.raises(GameError):
        service.dispatch("g1", "u2", "乙", "创建")


def test_guess_parsing_and_resolution() -> None:
    service = GameService()
    service.dispatch("g1", "u1", "甲", "创建")
    service.dispatch("g1", "u2", "乙", "加入")
    room = service.room("g1")
    assert room is not None
    room.started = True
    room.players[0].hand = []
    room.players[1].hand = []

    assert service._parse_guess(room, "B3 7") == ("B", 3, 7)
    assert service._parse_guess(room, "B 3 -") == ("B", 3, None)
    assert service._parse_guess(room, "乙 2 万能") == ("B", 2, None)
    with pytest.raises(GameError):
        service._parse_guess(room, "B3 99")
    with pytest.raises(GameError):
        service._parse_guess(room, "B3")


def test_dissolve_requires_host() -> None:
    service = GameService()
    service.dispatch("g1", "u1", "甲", "创建")
    service.dispatch("g1", "u2", "乙", "加入")
    with pytest.raises(GameError):
        service.dispatch("g1", "u2", "乙", "解散")
    assert "解散" in flat(service.dispatch("g1", "u1", "甲", "解散"))
    assert service.room("g1") is None


def test_leave_relabels_players() -> None:
    service = GameService()
    service.dispatch("g1", "u1", "甲", "创建")
    service.dispatch("g1", "u2", "乙", "加入")
    service.dispatch("g1", "u3", "丙", "加入")
    service.dispatch("g1", "u1", "甲", "退出")
    room = service.room("g1")
    assert room is not None
    assert [p.label for p in room.players] == ["A", "B"]
    assert room.players[0].user_id == "u2"
