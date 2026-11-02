"""测真实的引用定位率：模型提出的每条引文，能不能在年报里找到。

之前报的“100%”是选择偏差（找不到的已丢弃）。这里不丢弃，全部计数。

用法：
    cd 问询函预演
    set DS_KEY=...
    python tools/quote_rate.py
输出：
    data/quote_rate.json
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import llm_judge as L  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODES = ["600363", "600491", "600825"]


def main() -> int:
    if not L.KEY:
        print("缺少 DS_KEY")
        return 1
    items = {x["code"]: x for x in json.load(open(os.path.join(ROOT, "data", "dataset.json"), encoding="utf-8"))["items"]}
    rows = []
    for code in CODES:
        it = items[code]
        report = open(os.path.join(ROOT, it["dir"], "report.txt"), encoding="utf-8").read()
        pgs = L.pages(report)
        proposed = located = 0
        for topic, kws in L.TOPICS.items():
            ctx = L.retrieve(pgs, kws, k=6, per_page=1500, max_chars=9000)
            if not ctx:
                continue
            prompt = f"""你在做年报预检，话题：{topic}。
只根据下面的年报原文判断，不要用外部知识。找出该话题下最值得关注的 1-2 条异常：
数字异常、文字与数字矛盾、披露不充分。每条必须引用原文（不超过 120 字），没有把握就不要写。
输出 JSON：{{"issues": [{{"issue": "一句话", "quote": "原文摘录", "confidence": 0到1}}]}}
原文：
{ctx}"""
            res = L.ask(prompt)
            for it2 in res.get("issues", [])[:2]:
                q = (it2.get("quote") or "").strip()
                if not q:
                    continue
                proposed += 1
                if L.locate(pgs, q) is not None:
                    located += 1
            time.sleep(0.2)
        rows.append({"code": code, "name": it["name"], "proposed": proposed, "located": located})
        print(f"   {it['name']}: 提出 {proposed}，定位 {located}")
    tp = sum(r["proposed"] for r in rows)
    tl = sum(r["located"] for r in rows)
    out = {"companies": rows, "proposed": tp, "located": tl,
           "rate": round(tl / max(tp, 1), 3)}
    json.dump(out, open(os.path.join(ROOT, "data", "quote_rate.json"), "w", encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=1)
    print(f"\n合计：提出 {tp}，定位 {tl}，定位率 {tl/max(tp,1):.0%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
