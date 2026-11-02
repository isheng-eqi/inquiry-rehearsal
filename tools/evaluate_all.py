"""三路结果统一评估：规则层 / B1 裸模型 / B2 检索+模型。

指标：
- 结论数、有问询函支撑的比例（按关注点）
- 问询问题覆盖率（按关注点）
- 引用页码核对通过率（B1/B2 由系统定位，规则层无引用）

用法：
    cd 问询函预演
    python tools/evaluate_all.py
"""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOPIC_KEY = {
    "收入": ["收入", "营收"], "应收": ["应收", "坏账", "账龄"], "预付": ["预付"],
    "存货": ["存货", "跌价"], "在建工程": ["在建", "转固"], "毛利率": ["毛利"],
    "关联交易": ["关联", "资金占用", "占用"], "持续经营": ["持续经营", "亏损", "偿债"],
    "商誉": ["商誉", "减值"], "内控": ["内控", "内部控制"], "募集资金": ["募集"],
}


def topics(text: str) -> set:
    return {t for t, kws in TOPIC_KEY.items() if any(k in text for k in kws)}


def load_flags(source: str, code: str):
    if source == "rules":
        p = os.path.join(ROOT, "data", "flags", f"{code}.json")
        if not os.path.exists(p):
            return []
        return json.load(open(p, encoding="utf-8")).get("flags", [])
    d = "llm_b1" if source == "b1" else "llm"
    p = os.path.join(ROOT, "data", d, f"{code}.json")
    if not os.path.exists(p):
        return []
    return json.load(open(p, encoding="utf-8")).get("flags", [])


def main() -> int:
    qs = json.load(open(os.path.join(ROOT, "data", "questions.json"), encoding="utf-8"))["items"]
    summary = {}
    for source in ("rules", "b1", "b2"):
        nf = ns = nc = nh = nq = 0
        for item in qs:
            flags = load_flags(source, item["code"])
            qsets = [topics(q) for q in item["questions"]]
            fsets = [topics((f.get("rule", "") + f.get("topic", "") + " " + f.get("issue", "") + " " + f.get("quote", "")))
                     for f in flags]
            qtop = set().union(*qsets) if qsets else set()
            ftop = set().union(*fsets) if fsets else set()
            nf += len(flags)
            ns += sum(1 for s in fsets if s & qtop)
            nc += sum(1 for f in flags if f.get("citation_ok"))
            nh += sum(1 for s in qsets if s & ftop)
            nq += len(item["questions"])
        summary[source] = {"flags": nf, "supported": ns, "citation_ok": nc,
                           "hit": nh, "questions": nq,
                           "support_rate": round(ns / max(nf, 1), 3),
                           "citation_rate": round(nc / max(nf, 1), 3),
                           "coverage": round(nh / max(nq, 1), 3)}
        print(f"{source:6} 结论 {nf:3} 支撑 {ns:3}（{summary[source]['support_rate']:.0%}）"
              f" 引用 {nc:3}（{summary[source]['citation_rate']:.0%}）"
              f" 覆盖 {nh}/{nq}（{summary[source]['coverage']:.0%}）")
    json.dump(summary, open(os.path.join(ROOT, "data", "eval_all.json"), "w", encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
