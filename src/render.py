"""把对局状态渲染成 QQ 官方 Markdown 文本与按钮数据。"""

from __future__ import annotations

from .engine import (
    PHASE_CONTINUING,
    PHASE_ENDED,
    PHASE_GUESSING,
    PHASE_PLACING,
    PHASE_WAITING,
    GuessOutcome,
    Player,
    Room,
)


def guess_text(number: int | None) -> str:
    """猜测值的展示文字。"""
    return "百搭" if number is None else str(number)


def tile_text(tile_revealed: bool, text: str) -> str:
    return text if tile_revealed else "??"


def render_table(room: Room) -> str:
    """公开牌桌：暗牌只显示 ``??``，不泄露颜色与数字。"""
    if not room.started:
        lines = ["当前牌局："]
        lines.extend(f"{p.label} {p.name}" for p in room.players)
        lines.append("")
        lines.append(render_turn_hint(room))
        return "\n".join(lines)
    lines = [f"牌堆剩余 {len(room.deck)} 张", ""]
    for player in room.players:
        mark = "✅" if player.alive else "❌"
        cells = [
            f"{i + 1}.{tile_text(tile.revealed, tile.text)}"
            for i, tile in enumerate(player.hand)
        ]
        body = " ".join(cells) if cells else "(无牌)"
        lines.append(f"{player.label} {player.name}{mark}：{body}")
    lines.append("")
    lines.append(render_turn_hint(room))
    return "\n".join(lines)


def render_turn_hint(room: Room) -> str:
    """当前阶段的一句话提示。"""
    if room.phase == PHASE_ENDED:
        winner = next((p for p in room.players if p.user_id == room.winner), None)
        if winner is None:
            return "对局结束。"
        return f"🏁 对局结束，{winner.label} {winner.name} 获胜！"
    current = room.current
    if current is None:
        return ""
    if room.phase == PHASE_WAITING:
        return "等待房主点击「开始游戏」。"
    if room.phase == PHASE_PLACING:
        max_pos = len(current.hand) + 1
        return (
            f"轮到你（{current.label} {current.name}）：抽到百搭，"
            f"请点击「选择百搭位置」并填 1-{max_pos}。"
        )
    if room.phase == PHASE_GUESSING:
        return (
            f"轮到 {current.label} {current.name}：请点击自己的「手牌」"
            "查看本回合抽到的牌，再点击「猜牌」并补成"
            "「达芬奇密码 猜 B3 7」（数字用 - 表示百搭）。"
        )
    if room.phase == PHASE_CONTINUING:
        return (
            f"{current.label} {current.name} 猜对了！"
            "可以继续猜，或点击「收手」结束回合。"
        )
    return ""


def hand_payload(player: Player, room: Room) -> str:
    """私密按钮的 data：会被填入玩家自己的输入框，不主动发群。

    这是 QQ 官方平台下唯一可行的“私密发牌”方案：按钮用
    ``permission.specify_user_ids`` 限定只有本人可点，``enter=False``
    让内容只进入本人输入框。
    """
    tiles = " ".join(f"{i + 1}.{tile.text}" for i, tile in enumerate(player.hand))
    text = (
        f"{player.label}的手牌：{tiles}" if tiles else f"{player.label}的手牌：（空）"
    )
    if player.pending is not None and room.current is player:
        text += f"｜本回合抽到 {player.pending.text}"
    return f"{text}（看完请勿发送）"


def render_outcome(outcome: GuessOutcome) -> str:
    """播报一次猜测的结果。"""
    head = (
        f"{outcome.guesser_label}({outcome.guesser_name}) 猜 "
        f"{outcome.target_label}({outcome.target_name}) 第 {outcome.position} 张"
        f"是 {guess_text(outcome.guessed)}"
    )
    if outcome.correct:
        text = f"✅ {head}，命中！翻出「{outcome.tile.text}」"
        if outcome.target_eliminated:
            text += f"\n💥 {outcome.target_label}({outcome.target_name}) 的牌全部翻开，出局！"
    else:
        text = f"❌ {head}，猜错了"
        if outcome.no_penalty:
            text += "（牌堆已空，无需亮牌）"
        else:
            text += (
                f"\n⬆️ {outcome.guesser_label}({outcome.guesser_name}) 亮出刚抽的"
                f"「{outcome.tile.text}」"
            )
        if outcome.self_eliminated:
            text += f"\n💥 {outcome.guesser_label}({outcome.guesser_name}) 的牌全部翻开，出局！"
    if outcome.finished:
        text += f"\n🏁 对局结束，{outcome.winner_label}({outcome.winner_name}) 获胜！"
    return text


def render_help() -> str:
    """指令与按钮说明。"""
    return (
        "达芬奇密码 · 指令\n"
        "创建牌局 / 加入牌局：开一局或入座（2-4 人）\n"
        "开始游戏：房主开局\n"
        "牌桌状态：查看公开牌面\n"
        "我的牌：点自己的「手牌」按钮，内容只进本人输入框\n"
        "猜牌：点击后补成「达芬奇密码 猜 B3 7」\n"
        "  · 猜百搭写成「达芬奇密码 猜 B3 -」\n"
        "选择百搭位置：抽到百搭时点击并填 1-N\n"
        "收手：猜中后结束回合\n"
        "退出牌局 / 解散牌局\n"
        "玩法规则：查看完整规则"
    )


def render_rules() -> str:
    """完整规则说明。"""
    return (
        "达芬奇密码 · 规则\n"
        "1. 牌堆：黑 0-11、白 0-11，各一张百搭，共 26 张。\n"
        "2. 每人 4 张（4 人局每人 3 张），按数字从小到大排列，"
        "同数字黑色在左，百搭可放任意位置。\n"
        "3. 轮到你时自动抽 1 张线索牌，只有你能看到。\n"
        "4. 你必须猜一名对手某张暗牌的数字：\n"
        "   · 猜中：对方翻开该牌，你可以继续猜或收手；"
        "收手时把线索牌暗扣进自己的牌列。\n"
        "   · 猜错：把刚抽的线索牌亮出并放进自己的牌列，回合结束。\n"
        "5. 全部牌被翻开的玩家出局，坚持到最后的人获胜。\n"
        "6. 牌堆抽空后仍要猜牌，猜错不再有亮牌惩罚。"
    )
