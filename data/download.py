"""下载全唐诗语料（数据不进 git，队友拉代码后跑这一条）。

用法：
    python data/download.py                 # 下到 data/raw/tang
    python data/download.py --out data/raw/tang

来源：https://github.com/chinese-poetry/chinese-poetry（全唐诗，约 5.7 万首 / 25MB）
已下载的文件会跳过，中断了重跑即可。
"""

from __future__ import annotations

import argparse
import sys
import urllib.parse
import urllib.request
from pathlib import Path

BASE = ("https://raw.githubusercontent.com/chinese-poetry/chinese-poetry/master/"
        + urllib.parse.quote("全唐诗") + "/")
FILES = [f"poet.tang.{i}.json" for i in range(0, 58000, 1000)]
EXTRA = {"tang300.json": "唐诗三百首.json"}
TIMEOUT = 60


def fetch(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        return
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "poem-gpt/0.1"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp, tmp.open("wb") as fh:
        fh.write(resp.read())
    tmp.replace(dest)


def main() -> int:
    parser = argparse.ArgumentParser(description="下载全唐诗")
    parser.add_argument("--out", default="data/raw/tang")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    for name, remote in [(n, n) for n in FILES] + list(EXTRA.items()):
        dest = out / name
        try:
            fetch(BASE + urllib.parse.quote(remote), dest)
        except Exception as exc:                      # noqa: BLE001 - 单文件失败不该中断整批
            print(f"!! {name}: {exc}", file=sys.stderr)
            return 1
        print(f"ok {dest}", file=sys.stderr)

    total = sum(p.stat().st_size for p in out.glob("*.json"))
    print(f"{len(list(out.glob('*.json')))} 个文件 / {total / 1e6:.1f} MB → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
