"""人工审 20 条结论：打印结论、引文、所在页原文，供逐条判断真/假。

用法：
    cd 问询函预演
    python tools/audit_sample.py --n 20 --seed 7
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def pages(text: str):
    parts = re.split(r"=== 第 (\d+) 页 ===", text)
    out = {}
    for i in range(1, len(parts), 2):
        try:
            out[int(parts[i])] = parts[i + 1]
        except ValueError:
            pass
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--start", type=int, default=0)
    args = ap.parse_args()
    random.seed(args.seed)
    items = json.load(open(os.path.join(ROOT, "data", "dataset.json"), encoding="utf-8"))["items"]
    pool = []
    for it in items:
        p = os.path.join(ROOT, "data", "llm", f"{it['code']}.json")
        if not os.path.exists(p):
            continue
        for f in json.load(open(p, encoding="utf-8"))["flags"]:
            pool.append((it, f))
    random.shuffle(pool)
    sample = pool[args.start:args.start + args.n]
    for idx, (it, f) in enumerate(sample, 1):
        pg = pages(open(os.path.join(ROOT, it["dir"], "report.txt"), encoding="utf-8").read())
        txt = re.sub(r"\s+", " ", pg.get(f["page"], ""))
        print(f"\n### {idx}. {it['name']} p{f['page']} [{f.get('topic')}]")
        print("结论：", f.get("issue", "")[:160])
        print("引文：", (f.get("quote") or "")[:120])
        print("原文：", txt[:420])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
