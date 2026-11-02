"""把问询函问题与检查器结论都映射到"关注点"，算命中 / 漏检 / 无支撑。

关注点（可扩展）：
  收入、应收、预付、存货、在建工程、毛利率、关联交易、资金占用、持续经营、
  商誉、内控、募集资金、诉讼、其他

用法：
    cd 问询函预演
    python tools/evaluate.py            # 全部公司
    python tools/evaluate.py --code 600491
输出：
    data/eval.json
"""
from __future__ import annotations

import argparse
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOPICS = {
    "收入": ["营业收入", "收入", "营收", "销售"],
    "应收": ["应收账款", "应收款", "坏账", "账龄", "合同资产"],
    "预付": ["预付款", "预付"],
    "存货": ["存货", "跌价"],
    "在建工程": ["在建工程", "转固", "固定资产"],
    "毛利率": ["毛利率", "毛利"],
    "关联交易": ["关联交易", "关联方", "关联人"],
    "资金占用": ["资金占用", "非经营性占用", "占用"],
    "持续经营": ["持续经营", "亏损", "偿债", "流动性", "债务"],
    "商誉": ["商誉", "减值"],
    "内控": ["内部控制", "内控", "否定意见"],
    "募集资金": ["募集资金", "募投"],
    "诉讼": ["诉讼", "仲裁", "担保"],
}


def topic_of(text: str) -> set:
    hits = set()
    for t, kws in TOPICS.items():
        if any(k in text for k in kws):
            hits.add(t)
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", default="")
    args = ap.parse_args()
    qs = json.load(open(os.path.join(ROOT, "data", "questions.json"), encoding="utf-8"))["items"]
    rows = []
    for item in qs:
        if args.code and item["code"] != args.code:
            continue
        fp = os.path.join(ROOT, "data", "flags", f"{item['code']}.json")
        if not os.path.exists(fp):
            continue
        flags = json.load(open(fp, encoding="utf-8"))["flags"]
        qsets = [topic_of(q) for q in item["questions"]]
        fsets = [topic_of(f["rule"] + " " + f.get("quote", "")) for f in flags]
        flag_topics = set().union(*fsets) if fsets else set()
        q_topics = set().union(*qsets) if qsets else set()
        hit = sum(1 for s in qsets if s & flag_topics)
        supported = [bool(s & q_topics) for s in fsets]
        rows.append({"code": item["code"], "name": item["name"],
                     "questions": len(item["questions"]), "flags": len(flags),
                     "hit_topics": hit, "supported_flags": sum(supported),
                     "question_topics": sorted(q_topics),
                     "flag_topics": sorted(flag_topics)})
        print(f"   {item['name']:8} 问题 {len(item['questions']):2} 命中 {hit:2} | 结论 {len(flags)} 有支撑 {sum(supported)}")
    json.dump({"generated_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"), "rows": rows},
              open(os.path.join(ROOT, "data", "eval.json"), "w", encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
