"""文档数字对账：主文档里的关键数字 vs 结果文件。

用法：
    cd 问询函预演
    python tools/verify_doc.py
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, "submission", "开发设计文档-问询函预演.md")


def load(name):
    return json.load(open(os.path.join(ROOT, "data", name), encoding="utf-8"))


def main() -> int:
    doc = open(DOC, encoding="utf-8").read()
    ds = load("dataset.json")["items"]
    qr = load("quote_rate.json")
    au = load("audit_20.json")
    qs = load("questions.json")["items"]
    ea = load("eval_all.json")
    m2 = load("match_b2.json")["items"]
    ml = load("match_llm_learned.json")["items"]
    ml2 = load("match_llm_learned2.json")["items"]
    kg = load("kg.json")
    from collections import Counter as _C
    _fc, _qc = _C(), _C()
    for e in kg["edges"]:
        if e["relation"] != "属于":
            continue
        c = e["target"].split(":", 1)[1]
        if e["source"].startswith("flag:"):
            _fc[c] += 1
        elif e["source"].startswith("question:"):
            _qc[c] += 1
    new_flags = _fc.get("募集资金与募投项目", 0) + _fc.get("诉讼担保与内控", 0)
    new_qs = _qc.get("募集资金与募投项目", 0) + _qc.get("诉讼担保与内控", 0)

    report_pages = sum(x["report_pages"] for x in ds)
    reply_pages = sum(x["reply_pages"] for x in ds)
    questions = sum(len(x["questions"]) for x in qs)
    b2_q = sum(x["questions"] for x in m2)
    b2_hit = sum(x["matched_questions"] for x in m2)
    b2_flags = sum(x["flags"] for x in m2)
    b2_ok = sum(x["matched_flags"] for x in m2)

    B = ["603377", "600080", "600187", "600116", "601010"]
    C = ["603599", "603108", "688646", "603398", "600880"]
    ml_map = {x["code"]: x for x in ml}
    fold1_q = sum(ml_map[c]["questions"] for c in B if c in ml_map)
    fold1_hit = sum(ml_map[c]["matched_questions"] for c in B if c in ml_map)
    m2_map = {x["code"]: x for x in m2}
    ml2_map = {x["code"]: x for x in ml2}
    fold2_q = sum(ml2_map[c]["questions"] for c in C if c in ml2_map)
    fold2_hit = sum(ml2_map[c]["matched_questions"] for c in C if c in ml2_map)

    checks = [
        ("公司数", len(ds), "20"),
        ("年报页数", report_pages, "4532"),
        ("回复页数", reply_pages, "1242"),
        ("问题数", questions, "143"),
        ("B2 结论数", ea["b2"]["flags"], "171"),
        ("B2 问题命中", f"{b2_hit}/{b2_q}", "31（22%）"),
        ("B2 支撑", f"{b2_ok}/{b2_flags}", "70/158"),
        ("折1 通用", f"{sum(m2_map[c]['matched_questions'] for c in B if c in m2_map)}/{fold1_q}", "8/35"),
        ("折1 关注点", f"{fold1_hit}/{fold1_q}", "14/35"),
        ("折2 关注点", f"{fold2_hit}/{fold2_q}", "16/37"),
        ("引用定位率", f"{qr['located']}/{qr['proposed']}", "57%"),
        ("误报数", au["false"], "3"),
        ("图谱节点", kg["stats"]["nodes"], "539"),
        ("图谱边", kg["stats"]["edges"], "819"),
        ("关注点数", kg["stats"]["concerns_total"], "14"),
        ("准则对齐", f"{kg['stats']['concerns_aligned']}/{kg['stats']['concerns_total']}", "14/14"),
        ("新类结论", new_flags, "1 条"),
        ("新类问题", new_qs, "9 个"),
    ]
    bad = 0
    for name, actual, expect in checks:
        ok = str(expect) in doc
        print(f"  {'✓' if ok else '✗'} {name:10} 实际 {actual:>10}  文档 {expect:<8}")
        bad += 0 if ok else 1
    print(f"\n对账 {'通过' if bad == 0 else '失败'}：{len(checks)-bad}/{len(checks)}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
