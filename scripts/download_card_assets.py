"""下载牌面素材到 assets/cards/（开发时执行一次，产物会提交进仓库）。

用法::

    python scripts/download_card_assets.py
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

BASE = "https://placehold.co/{w}x{h}/{bg}/{fg}.png?text={text}"
BLACK_STYLE = "000000/FFFFFF"
WHITE_STYLE = "FFFFFF/000000"
BACK_STYLE = "2563EB/2563EB"
WIDTH, HEIGHT = 144, 216
ASSET_DIR = Path(__file__).resolve().parent.parent / "assets" / "cards"


def download(name: str, style: str, text: str) -> None:
    url = BASE.format(
        w=WIDTH, h=HEIGHT, bg=style.split("/")[0], fg=style.split("/")[1], text=text
    )
    target = ASSET_DIR / name
    with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310 - 固定 https 素材源
        data = resp.read()
    target.write_bytes(data)
    print(f"{name:18} {len(data):>6} bytes  <- {url}")


def main() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    for color, style in (("black", BLACK_STYLE), ("white", WHITE_STYLE)):
        for number in range(12):
            download(f"{color}-{number}.png", style, str(number))
        download(f"{color}-joker.png", style, "-")
    download("back.png", BACK_STYLE, "")


if __name__ == "__main__":
    main()
