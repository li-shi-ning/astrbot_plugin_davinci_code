# 达芬奇密码（AstrBot 插件）

`astrbot_plugin_davinci_code` 是桌游《达芬奇密码》（*Da Vinci Code / Coda*）的
AstrBot 群聊实现，面向 **QQ 官方机器人**（`qq_official` / `qq_official_webhook`）。

- 2-4 人同群对战，每人 4 张（4 人局 3 张）暗牌，比谁先猜穿对手的密码。
- 手牌、每回合抽到的线索牌都通过 **私密按钮** 下发，只有本人能点、只填入本人输入框。
- 公开牌桌用 **Markdown 内嵌牌图** 展示（黑底白字 / 白底黑字 / 蓝色背面），玩家自己数位置。
- 全流程按钮化：创建 / 加入 / 开始 / 猜牌 / 收手 / 牌桌状态。

## 玩法规则

26 张牌：黑色 `0-11`、白色 `0-11`，再各加一张 **百搭**。完整规则见
[`docs/rules.md`](docs/rules.md)，速览：

1. 每人按「数字从小到大」排列暗牌，同数字黑色在左；百搭可放在任意位置。
2. 轮到你时自动抽 1 张线索牌，只有你能看到。
3. 你必须猜一名对手某张暗牌的数字（报 `0-11`，猜百搭报 `-`）：
   - **猜中**：对方翻开该牌。你可以继续猜，或 **收手** 把线索牌暗扣进自己的牌列。
   - **猜错**：把刚抽的线索牌 **亮出** 并放进自己的牌列，回合结束。
4. 牌全部被翻开的玩家出局，坚持到最后的人获胜。
5. 牌堆抽空后仍要猜牌，但猜错不再有亮牌惩罚。

## 指令与按钮

所有操作都能用按钮完成（按钮内容会先填入输入框，确认后发送）：

| 按钮 / 指令 | 说明 |
| --- | --- |
| `达芬奇密码 创建` / `加入` / `开始` | 创建 / 加入 / 开局（2-4 人） |
| `达芬奇密码 状态` | 查看公开牌桌 |
| `达芬奇密码 看牌` | 点属于自己的「手牌」按钮，内容只进本人输入框 |
| `达芬奇密码 猜 B3 7` | 猜 B 玩家第 3 张牌是 `7`，猜百搭写成 `-` |
| `达芬奇密码 收手` | 猜中后结束回合 |
| `达芬奇密码 退出` / `解散` | 退出牌局 / 房主解散 |
| `达芬奇密码 规则` / `帮助` | 规则 / 指令说明 |

> 猜牌也可以写成 `达芬奇密码 猜 <玩家昵称> 3 7`。

## 私密发牌方案

QQ 官方群聊没有「仅自己可见」的消息接口，因此本插件沿用
[`astrbot_plugin_official_TexasHoldem`](https://github.com/lishining666/astrbot_plugin_official_TexasHoldem)
的私密发牌方案：

- 手牌 / 线索牌放在按钮的 `action.data` 里；
- 按钮 `permission.type=0` + `specify_user_ids` 限定 **只有本人可点击**；
- 按钮 `action.enter=False` 让内容 **只填入本人输入框**，不会直接发到群里。

因此手牌按钮的文案里都会带「（看完请勿发送）」。请勿把按钮内容发送到群里。

## 牌面展示

牌面素材随插件提供（`assets/cards/`，由 `scripts/download_card_assets.py` 生成并提交），
运行时不访问任何外网图床。

| 场景 | 形式 |
| --- | --- |
| 公开牌桌 | 本地用 Pillow 渲染成 **一张 PNG**，通过 QQ 富媒体上传接口以 `msg_type=7` 发送 |
| 文字 + 按钮 | Markdown 消息（富媒体不能带 Markdown/键盘，所以单独一条） |
| 私密手牌 | 纯文字，挂在 `only_for` 按钮上，内容只进本人输入框 |
| 兜底 | 富媒体上传/发送失败时自动退回 Markdown 内嵌牌图 |

- 牌桌图里的昵称需要中文字体：优先使用 AstrBot 数据目录下的 `font.ttf`，
  也可用 `board_font_path` 指定；找不到字体时会退化用默认字体。
- `board_image=false` 可关闭图片，只发 Markdown 牌图。

## 配置 `_conf_schema.json`

| 键 | 默认 | 说明 |
| --- | --- | --- |
| `with_jokers` | `true` | 是否加入两张百搭牌；关闭后为 24 张纯数字牌 |
| `board_image` | `true` | 是否把牌桌渲染成图片走富媒体发送 |
| `board_font_path` | `""` | 牌桌图使用的中文字体路径，留空自动查找 |
| `card_image_base` | `https://placehold.co/72x108` | 兜底用的 Markdown 牌图服务前缀 |
| `card_image_size` | `32x48` | 兜底牌图的显示尺寸（`宽x高`，px） |

## 已知限制

- 仅支持 QQ 官方机器人；其他平台（如 aiocqhttp）暂未适配。
- 牌局状态保存在内存中，插件重载 / 重启后牌局丢失。
- 没有回合超时；玩家挂机会卡住牌局，可由房主「解散牌局」。

## 致谢

- 私密发牌（`only_for` 按钮 + `enter=False`）方案来自
  [`astrbot_plugin_official_TexasHoldem`](https://github.com/lishining666/astrbot_plugin_official_TexasHoldem)。
- 规则整理参考 UltraBoardGames 官方规则页与开源实现
  [`gtoxlili/phantom-cipher`](https://github.com/gtoxlili/phantom-cipher)。

## 许可

GNU Affero General Public License v3.0，见 [LICENSE](LICENSE)。
