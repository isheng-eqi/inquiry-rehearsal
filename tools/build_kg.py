"""构建知识图谱：关注点本体 + 实例图。

本体（监管关注点）来自问询函归纳（data/concerns_learned.json），
每个关注点对齐一条会计准则/监管规则；
实例图把 公司 → 年报 → 结论 → 证据 → 关注点 → 问询问题 连起来。

用法：
    cd 问询函预演
    python tools/build_kg.py
输出：
    data/kg.json
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 关注点 → 准则/监管规则对齐（人工确认）
STANDARDS = {
    "投资性房地产": "《企业会计准则第3号——投资性房地产》",
    "应收账款坏账": "《企业会计准则第22号——金融工具确认和计量》",
    "其他应收款": "《企业会计准则第22号》/《上市公司监管指引第8号》",
    "资金占用与内控": "《上市公司监管指引第8号——上市公司资金往来、对外担保的监管要求》",
    "持续经营能力": "《企业会计准则第30号——财务报表列报》",
    "收入确认真实性": "《企业会计准则第14号——收入》",
    "关联交易公允性": "《企业会计准则第36号——关联方披露》",
    "货币资金与偿债": "《企业会计准则第31号——现金流量表》/审计准则1323号",
    "存货与减值": "《企业会计准则第1号——存货》",
    "募投项目与在建工程": "《企业会计准则第4号——固定资产》/《上市公司募集资金监管规则》",
    "商誉与减值": "《企业会计准则第8号——资产减值》",
    "在建工程与转固": "《企业会计准则第4号——固定资产》",
    "预付款项": "《企业会计准则第30号》/《监管规则适用指引》",
    "金融资产投资": "《企业会计准则第22号——金融工具确认和计量》",
    "收入与毛利率": "《企业会计准则第14号——收入》",
    "存货跌价准备": "《企业会计准则第1号——存货》",
    "关联交易与资金占用": "《企业会计准则第36号——关联方披露》/《上市公司监管指引第8号》",
    "其他应收款减值": "《企业会计准则第22号》/《上市公司监管指引第8号》",
    "预付款项异常": "《企业会计准则第30号》/《监管规则适用指引》",
    "其他": "未对齐",
}


def load(name):
    return json.load(open(os.path.join(ROOT, "data", name), encoding="utf-8"))


def score(text: str, keywords) -> int:
    return sum(text.count(k) for k in keywords)


def main() -> int:
    ds = {x["code"]: x for x in load("dataset.json")["items"]}
    qs = load("questions.json")["items"]
    concerns = load("concerns_learned.json")["concerns"]
    flags_by_code = {}
    for code in ds:
        p = os.path.join(ROOT, "data", "llm", f"{code}.json")
        if os.path.exists(p):
            flags_by_code[code] = json.load(open(p, encoding="utf-8"))["flags"]

    nodes, edges = [], []

    def add_node(nid, ntype, label, props=None):
        nodes.append({"id": nid, "type": ntype, "label": label, "props": props or {}})

    def add_edge(src, rel, dst, props=None):
        edges.append({"source": src, "relation": rel, "target": dst, "props": props or {}})

    def align_standard(name: str) -> str:
        if name in STANDARDS:
            return STANDARDS[name]
        for k, v in STANDARDS.items():
            if k and (k in name or name in k):
                return v
        return "未对齐"

    # 本体层
    for c in concerns:
        cid = f"concern:{c['name']}"
        add_node(cid, "Concern", c["name"],
                 {"keywords": c["keywords"], "ask": c["ask"], "standard": align_standard(c["name"])})
    # 补充 B2 有、本体未覆盖的话题（商誉、在建工程）
    for extra in ["商誉与减值", "在建工程与转固"]:
        if not any(n["id"] == f"concern:{extra}" for n in nodes):
            add_node(f"concern:{extra}", "Concern", extra,
                     {"keywords": ["商誉", "减值"] if "商誉" in extra else ["在建工程", "转固"],
                      "ask": "减值依据/转固时点", "standard": align_standard(extra)})

    concern_names = [n["label"] for n in nodes if n["type"] == "Concern"]

    def map_to_concern(text: str) -> str:
        best, best_score = "其他", 0
        for c in nodes:
            if c["type"] != "Concern":
                continue
            s = score(text, c["props"]["keywords"])
            if s > best_score:
                best, best_score = c["label"], s
        return best if best_score > 0 else "其他"

    # 实例层
    for code, it in ds.items():
        cid = f"company:{code}"
        rid = f"report:{code}"
        add_node(cid, "Company", it["name"], {"code": code})
        add_node(rid, "Report", f"{it['name']} 2025 年报", {"pages": it.get("report_pages")})
        add_edge(cid, "发布", rid)
        for i, f in enumerate(flags_by_code.get(code, [])[:40]):
            fid = f"flag:{code}:{i}"
            add_node(fid, "Flag", (f.get("issue") or "")[:60],
                     {"page": f.get("page"), "topic": f.get("topic")})
            add_edge(rid, "包含", fid)
            ev = f"evidence:{fid}"
            add_node(ev, "Evidence", (f.get("quote") or "")[:60], {"page": f.get("page")})
            add_edge(fid, "依据", ev)
            cname = map_to_concern((f.get("topic", "") + " " + f.get("issue", "")))
            add_edge(fid, "属于", f"concern:{cname}")

    for item in qs:
        code = item["code"]
        if code not in ds:
            continue
        for i, q in enumerate(item["questions"]):
            qid = f"question:{code}:{i}"
            add_node(qid, "Question", q[:60], {"text": q[:200]})
            add_edge(f"company:{code}", "被问询", qid)
            add_edge(qid, "属于", f"concern:{map_to_concern(q)}")

    # 统计
    types = Counter(n["type"] for n in nodes)
    rels = Counter(e["relation"] for e in edges)
    covered_flags = sum(1 for e in edges if e["relation"] == "属于" and e["source"].startswith("flag:"))
    total_flags = sum(1 for n in nodes if n["type"] == "Flag")
    covered_q = sum(1 for e in edges if e["relation"] == "属于" and e["source"].startswith("question:"))
    total_q = sum(1 for n in nodes if n["type"] == "Question")
    aligned = sum(1 for n in nodes if n["type"] == "Concern" and n["props"].get("standard") != "未对齐")

    out = {"ontology": {"concerns": concern_names, "standards": STANDARDS},
           "nodes": nodes, "edges": edges,
           "stats": {"nodes": len(nodes), "edges": len(edges), "types": dict(types),
                     "relations": dict(rels),
                     "flags_linked": covered_flags, "flags_total": total_flags,
                     "questions_linked": covered_q, "questions_total": total_q,
                     "concerns_aligned": aligned, "concerns_total": len(concern_names)}}
    json.dump(out, open(os.path.join(ROOT, "data", "kg.json"), "w", encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=1)
    print("节点", len(nodes), dict(types))
    print("边  ", len(edges), dict(rels))
    print(f"结论挂关注点 {covered_flags}/{total_flags}，问题挂关注点 {covered_q}/{total_q}，关注点对齐准则 {aligned}/{len(concern_names)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
