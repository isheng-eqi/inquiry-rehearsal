"""用「从训练集学到的关注点」在测试集上跑检测（无泄漏版本）。

用法：
    cd 问询函预演
    set DS_KEY=...
    python tools/llm_learned.py --code 603377
输出：
    data/llm_learned/<code>.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import llm_judge as L  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "dataset.json")
CON = os.path.join(ROOT, "data", "concerns_learned.json")
TEST = ["603377", "600080", "600187", "600116", "601010", "603599", "603108", "688646", "603398", "600880"]


def run(pgs, conf):
    ctx = L.retrieve(pgs, conf.get("keywords", []), k=6, per_page=1500, max_chars=9000)
    if not ctx:
        return []
    prompt = f"""你在做年报预检，关注点：{conf['name']}。
监管在这个关注点上通常会追问：{conf.get('ask','')}。
只根据下面的年报原文判断，不要用外部知识。找出该关注点下最值得关注的 1-2 条异常：
数字异常、文字与数字矛盾、披露不充分。每条必须引用原文（不超过 120 字），没有把握就不要写。
输出 JSON：{{"issues": [{{"issue": "一句话", "quote": "原文摘录", "confidence": 0到1}}]}}
原文：
{ctx}"""
    res = L.ask(prompt)
    out = []
    for it in res.get("issues", [])[:2]:
        q = (it.get("quote") or "").strip()
        n = L.locate(pgs, q)
        if n is None:
            continue
        out.append({"topic": conf["name"], "issue": (it.get("issue") or "")[:120],
                    "quote": q[:160], "page": n, "confidence": it.get("confidence"), "citation_ok": True})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", default="")
    ap.add_argument("--concerns", default="data/concerns_learned.json")
    ap.add_argument("--outdir", default="data/llm_learned")
    args = ap.parse_args()
    if not L.KEY:
        print("缺少 DS_KEY")
        return 1
    concerns = json.load(open(os.path.join(ROOT, args.concerns), encoding="utf-8"))["concerns"]
    items = {x["code"]: x for x in json.load(open(DATA, encoding="utf-8"))["items"]}
    codes = [args.code] if args.code else TEST
    os.makedirs(os.path.join(ROOT, args.outdir), exist_ok=True)
    for code in codes:
        it = items.get(code)
        if not it:
            continue
        report = open(os.path.join(ROOT, it["dir"], "report.txt"), encoding="utf-8").read()
        pgs = L.pages(report)
        flags = []
        for c in concerns:
            flags += run(pgs, c)
            time.sleep(0.2)
        json.dump({"code": code, "name": it["name"], "flags": flags},
                  open(os.path.join(ROOT, args.outdir, f"{code}.json"), "w", encoding="utf-8", newline="\n"),
                  ensure_ascii=False, indent=1)
        print(f"== {it['name']} 结论 {len(flags)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
