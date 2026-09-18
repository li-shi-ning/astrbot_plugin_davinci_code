"""把对局状态渲染成 QQ 官方 Markdown 文本与按钮数据。

文案保持精简：公开区只播报必要信息，教程类文字只在玩家主动查询时给出。
"""

from __future__ import annotations

from .engine import (
    PHASE_CONTINUING,
    PHASE_ENDED,
    PHASE_GUESSING,
    PHASE_PLACING,
    GuessOutcome,
    Player,
    Room,
)


def guess_text(number: int | None) -> str:
    """猜测值的展示文字。"""
    return "百搭" if number is None else str(number)


def render_menu() -> str:
    """默认入口：一句话 + 按钮。"""
    return "🕵️ 达芬奇密码 · 点击下方按钮开局（规则见「玩法规则」）"


def render_table(room: Room) -> str:
    """公开牌桌：暗牌只显示 ``??``，不泄露颜色与数字。"""
    if not room.started:
        lines = ["当前牌局："]
        lines.extend(f"{p.label} {p.name}" for p in room.players)
        lines.append("")
        lines.append(render_turn_hint(room))
        return "\n".join(lines)
    lines = [f"牌堆 {len(room.deck)}", ""]
    for player in room.players:
        mark = "✅" if player.alive else "❌"
        cells = [
            f"{i + 1}.{tile.text if tile.revealed else '??'}"
            for i, tile in enumerate(player.hand)
        ]
        body = " ".join(cells) if cells else "(无牌)"
        lines.append(f"{player.label} {player.name}{mark}：{body}")
    lines.append("")
    lines.append(render_turn_hint(room))
    return "\n".join(lines)


def render_turn_hint(room: Room) -> str:
    """当前阶段的一句话提示，尽量短。"""
    if room.phase == PHASE_ENDED:
        winner = next((p for p in room.players if p.user_id == room.winner), None)
        if winner is None:
            return "对局结束。"
        return f"🏁 {winner.label} {winner.name} 获胜！"
    current = room.current
    if current is None:
        return ""
    if room.phase == PHASE_PLACING:
        return (
            f"▶ 轮到 {current.label} {current.name}：抽到百搭，"
            f"点「选择百搭位置」填 1-{len(current.hand) + 1}"
        )
    if room.phase == PHASE_GUESSING:
        return f"▶ 轮到 {current.label} {current.name}：点「手牌」看牌，再点「猜牌」"
    if room.phase == PHASE_CONTINUING:
        return f"▶ {current.label} {current.name} 猜对了，继续猜或点「收手」"
    return "等待房主点击「开始游戏」"


def hand_payload(player: Player, room: Room) -> str:
    """私密按钮的 data：会被填入玩家自己的输入框，不主动发群。

    这是 QQ 官方平台下唯一可行的“私密发牌”方案：按钮用
    ``permission.specify_user_ids`` 限定只有本人可点，``enter=False``
    让内容只进入本人输入框。按钮 data 有长度上限，过长时退回紧凑写法。
    """
    suffix = "（看完请勿发送）"
    pending = ""
    if player.pending is not None and room.current is player:
        pending = f"｜抽到{player.pending.text}"
    numbered = " ".join(f"{i + 1}.{tile.text}" for i, tile in enumerate(player.hand))
    plain = " ".join(tile.text for tile in player.hand)
    for body in [item for item in (numbered, plain) if item] or ["空"]:
        data = f"{player.label}手牌 {body}{pending}{suffix}"
        if len(data) <= 96:
            return data
    return f"{player.label}手牌 {plain}{pending}{suffix}"


def render_outcome(outcome: GuessOutcome) -> str:
    """播报一次猜测的结果。

    猜中时公开被翻开的对手牌；猜错时只公开猜错者自己亮出的线索牌，
    绝不能泄露对手那张暗牌。
    """
    if outcome.correct:
        text = (
            f"✅ {outcome.guesser_label}({outcome.guesser_name}) 猜中 "
            f"{outcome.target_label}({outcome.target_name}) 第 {outcome.position} 张"
            f"「{outcome.tile.text}」"
        )
        if outcome.target_eliminated:
            text += f"\n💥 {outcome.target_label}({outcome.target_name}) 出局"
    else:
        text = (
            f"❌ {outcome.guesser_label}({outcome.guesser_name}) 猜错"
            f"（{outcome.target_label} 第 {outcome.position} 张不是 "
            f"{guess_text(outcome.guessed)}）"
        )
        if outcome.no_penalty:
            text += "，牌堆已空无需亮牌"
        elif outcome.penalty is not None:
            text += f"，亮出线索牌「{outcome.penalty.text}」"
        if outcome.self_eliminated:
            text += f"\n💥 {outcome.guesser_label}({outcome.guesser_name}) 出局"
    if outcome.finished:
        text += f"\n🏁 {outcome.winner_label}({outcome.winner_name}) 获胜！"
    return text


def render_help() -> str:
    """玩家主动查询时的指令说明。"""
    return (
        "达芬奇密码\n"
        "1. 创建/加入 → 房主「开始游戏」（2-4 人）\n"
        "2. 轮到你：点「手牌」看牌 → 点「猜牌」→ 补成「达芬奇密码 猜 B3 7」\n"
        "3. 猜中可继续或收手；猜错亮出线索牌；牌全翻开者出局\n"
        "猜百搭写 -，完整规则见「达芬奇密码 规则」"
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
