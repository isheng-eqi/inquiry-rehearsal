"""从问询函回复里抽出"监管问了什么"，作为判定真值。

回复函通常以「问题一：」「问题 1：」「一、关于……」开头。
这里抽标题行 + 前 300 字，写成 questions.json。

用法：
    cd 问询函预演
    python tools/extract_questions.py
输出：
    data/questions.json
"""
from __future__ import annotations

import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "dataset.json")
OUT = os.path.join(ROOT, "data", "questions.json")

HEAD = re.compile(
    r"(?:问题\s*[一二三四五六七八九十\d]+"
    r"|问题\s*[：:]\s*(?=关于|公司|年报|货币|应收|存货|收入|资金|关联|商誉|在建)"
    r"|第[一二三四五六七八九十]+问"
    r"|^\s*[一二三四五六七八九十]+\s*[、.．]\s*(?=关于|请|你公司|公司|年报))", re.M)

def main() -> int:
    items = json.load(open(DATA, encoding="utf-8"))["items"]
    out = []
    for it in items:
        p = os.path.join(ROOT, it["dir"], "reply.txt")
        if not os.path.exists(p):
            continue
        text = open(p, encoding="utf-8").read()
        marks = list(HEAD.finditer(text))
        qs = []
        for i, m in enumerate(marks):
            end = marks[i + 1].start() if i + 1 < len(marks) else min(len(text), m.start() + 800)
            seg = text[m.start():end]
            seg = re.sub(r"\s+", " ", seg).strip()
            if len(seg) < 15:
                continue
            if "......" in seg or "……" in seg[:80]:
                continue
            head40 = seg[:40]
            if any(k in head40 for k in ["回复如下", "回复：", "核查程序", "会计师回复", "公司回复", "【回复】"]):
                continue
            qs.append(seg[:300])
        out.append({"code": it["code"], "name": it["name"], "dir": it["dir"], "questions": qs})
        print(f"   {it['code']} {it['name']}: {len(qs)} 个问题")
    json.dump({"generated_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"), "items": out},
              open(OUT, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
    total = sum(len(x["questions"]) for x in out)
    print(f"\n合计 {total} 个问题 -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
