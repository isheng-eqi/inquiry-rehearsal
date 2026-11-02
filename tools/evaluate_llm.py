"""评估 LLM 判断层（B2）的结果：支撑率、引用通过率、问题覆盖。

用法：
    cd 问询函预演
    python tools/evaluate_llm.py
"""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOPIC_KEY = {
    "收入": ["收入", "营收"],
    "应收": ["应收", "坏账", "账龄"],
    "预付": ["预付"],
    "存货": ["存货", "跌价"],
    "在建工程": ["在建", "转固"],
    "毛利率": ["毛利"],
    "关联交易": ["关联", "资金占用", "占用"],
    "资金占用": ["资金占用", "占用"],
    "持续经营": ["持续经营", "亏损", "偿债"],
    "商誉": ["商誉", "减值"],
    "内控": ["内控", "内部控制"],
    "募集资金": ["募集"],
}


def topics(text: str) -> set:
    return {t for t, kws in TOPIC_KEY.items() if any(k in text for k in kws)}


def main() -> int:
    qs = json.load(open(os.path.join(ROOT, "data", "questions.json"), encoding="utf-8"))["items"]
    rows = []
    for item in qs:
        p = os.path.join(ROOT, "data", "llm", f"{item['code']}.json")
        if not os.path.exists(p):
            continue
        flags = json.load(open(p, encoding="utf-8"))["flags"]
        qsets = [topics(q) for q in item["questions"]]
        fsets = [topics(f.get("topic", "") + " " + f.get("issue", "")) for f in flags]
        qtop = set().union(*qsets) if qsets else set()
        ftop = set().union(*fsets) if fsets else set()
        supported = sum(1 for s in fsets if s & qtop)
        hit = sum(1 for s in qsets if s & ftop)
        cit = sum(1 for f in flags if f.get("citation_ok"))
        rows.append({"code": item["code"], "name": item["name"], "questions": len(item["questions"]),
                     "flags": len(flags), "supported": supported, "hit": hit, "citation_ok": cit})
        print(f"   {item['name']:8} 问题 {len(item['questions']):2} 命中 {hit:2} | 结论 {len(flags)} 支撑 {supported} 引用 {cit}")
    nf = sum(r["flags"] for r in rows)
    ns = sum(r["supported"] for r in rows)
    nc = sum(r["citation_ok"] for r in rows)
    nq = sum(r["questions"] for r in rows)
    nh = sum(r["hit"] for r in rows)
    print(f"\n合计：结论 {nf}，支撑 {ns}（{ns/max(nf,1):.0%}），引用通过 {nc}（{nc/max(nf,1):.0%}），问题覆盖 {nh}/{nq}")
    json.dump({"rows": rows, "total_flags": nf, "supported": ns, "citation_ok": nc,
               "questions": nq, "hit": nh},
              open(os.path.join(ROOT, "data", "eval_llm.json"), "w", encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
