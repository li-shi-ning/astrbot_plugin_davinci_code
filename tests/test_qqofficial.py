"""QQ 官方按钮与消息参数测试。"""

from __future__ import annotations

from types import SimpleNamespace

from src.qqofficial import (
    Button,
    build_button,
    build_keyboard,
    build_payload,
    extract_group_context,
)


def test_private_button_uses_specify_user_ids_and_enter_false() -> None:
    button = build_button(Button("id1", "A·手牌", "A的手牌：黑1", only_for="u1"))
    action = button["action"]
    assert action["type"] == 2
    assert action["enter"] is False
    assert action["permission"] == {"type": 0, "specify_user_ids": ["u1"]}
    assert action["data"] == "A的手牌：黑1"


def test_public_button_is_clickable_by_everyone() -> None:
    button = build_button(Button("id2", "牌桌状态", "达芬奇密码 状态"))
    assert button["action"]["permission"] == {"type": 2}


def test_keyboard_rows_and_limit() -> None:
    assert build_keyboard([]) is None
    buttons = [Button(f"b{i}", str(i), "x") for i in range(4)]
    keyboard = build_keyboard(buttons)
    rows = keyboard["content"]["rows"]
    assert [len(row["buttons"]) for row in rows] == [3, 1]
    many = build_keyboard([Button(f"b{i}", str(i), "x") for i in range(40)])
    assert len(many["content"]["rows"]) == 5


def test_payload_is_markdown_with_keyboard() -> None:
    payload = build_payload("测试", [Button("id", "标签", "达芬奇密码 状态")])
    assert payload["msg_type"] == 2
    assert payload["markdown"] == {"content": "测试"}
    assert "keyboard" in payload
    # 没有按钮时不附带 keyboard 字段
    assert "keyboard" not in build_payload("纯文本")


def test_extract_group_context_from_raw_message() -> None:
    raw = SimpleNamespace(
        group_openid="g1",
        member_openid=None,
        id="msg1",
        msg_seq=2,
        author=SimpleNamespace(member_openid="m1", username="甲"),
    )
    event = SimpleNamespace(
        message_obj=SimpleNamespace(raw_message=raw),
        get_group_id=lambda: "g1",
        get_sender_id=lambda: "m1",
        get_sender_name=lambda: "甲",
    )
    context = extract_group_context(event)
    assert context is not None
    assert context.group_openid == "g1"
    assert context.member_openid == "m1"
    assert context.display_name == "甲"
    assert context.message_id == "msg1"
    assert context.msg_seq == 2


def test_send_group_media_uploads_then_posts() -> None:
    import asyncio

    from src.qqofficial import GroupContext, send_group_media

    class API:
        def __init__(self):
            self.posts: list[dict] = []

        async def post_group_message(self, **kwargs):
            self.posts.append(kwargs)

    class Event:
        def __init__(self):
            self.uploads: list[dict] = []
            self.bot = SimpleNamespace(api=API())

        async def upload_group_and_c2c_media(self, **kwargs):
            self.uploads.append(kwargs)
            return {"file_info": "FILEINFO"}

    context = GroupContext(
        group_openid="g1", member_openid="u1", display_name="甲", message_id="m1"
    )
    event = Event()
    assert asyncio.run(send_group_media(event, context, "/tmp/board.png")) is True

    assert event.uploads[0]["file_type"] == 1
    assert event.uploads[0]["group_openid"] == "g1"
    post = event.bot.api.posts[0]
    assert post["msg_type"] == 7
    assert post["media"] == {"file_info": "FILEINFO"}
    assert post["msg_id"] == "m1"
    assert "msg_seq" in post


def test_send_group_media_returns_false_without_uploader() -> None:
    import asyncio

    from src.qqofficial import GroupContext, send_group_media

    context = GroupContext(group_openid="g1", member_openid="u1", display_name="甲")
    assert (
        asyncio.run(send_group_media(SimpleNamespace(), context, "/tmp/x.png")) is False
    )


def test_send_group_media_swallows_upload_error() -> None:
    import asyncio

    from src.qqofficial import GroupContext, send_group_media

    class Event:
        bot = SimpleNamespace(api=SimpleNamespace(post_group_message=lambda **kw: None))

        async def upload_group_and_c2c_media(self, **kwargs):
            raise RuntimeError("boom")

    context = GroupContext(group_openid="g1", member_openid="u1", display_name="甲")
    assert asyncio.run(send_group_media(Event(), context, "/tmp/x.png")) is False
