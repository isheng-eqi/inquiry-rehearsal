"""问询函预演：B1（裸模型）与 B2（检索 + 模型）两种基线。

B1：把年报前 3 万字一次性给模型，让它自己找 6 条最值得关注的异常。
B2：按话题检索 6 页（每页 1500 字），每个话题让模型找 1-2 条。

两者共同点：模型只负责"引原文"，页码由系统在全文里匹配定位；
引文在全文里找不到的结论直接丢弃（防编造）。

用法：
    cd 问询函预演
    set DS_KEY=...
    python tools/llm_judge.py --mode b1
    python tools/llm_judge.py --mode b2 --code 600491
输出：
    data/llm_b1/<code>.json
    data/llm/<code>.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "dataset.json")
KEY = os.environ.get("DS_KEY", "")
API = "https://api.deepseek.com/v1/chat/completions"
MODEL = os.environ.get("DS_MODEL", "deepseek-chat")

TOPICS = {
    "应收": ["应收账款", "坏账", "账龄", "合同资产"],
    "预付": ["预付款项", "预付款"],
    "收入": ["营业收入", "收入确认"],
    "存货": ["存货", "跌价"],
    "关联交易": ["关联交易", "关联方", "资金占用", "非经营性占用"],
    "商誉": ["商誉", "减值"],
    "在建工程": ["在建工程", "转固"],
}


def pages(report: str):
    parts = re.split(r"=== 第 (\d+) 页 ===", report)
    out = []
    for i in range(1, len(parts), 2):
        try:
            n = int(parts[i])
        except ValueError:
            continue
        out.append((n, parts[i + 1] if i + 1 < len(parts) else ""))
    return out


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def locate(pgs, quote: str):
    qn = norm(quote)[:40]
    if not qn:
        return None
    for n, txt in pgs:
        if qn in norm(txt):
            return n
    return None


def retrieve(pgs, kws, k=6, per_page=1500, max_chars=9000):
    scored = []
    for n, txt in pgs:
        score = sum(txt.count(kw) for kw in kws)
        if score:
            scored.append((score, n, txt))
    scored.sort(key=lambda x: -x[0])
    buf, used = [], 0
    for _, n, txt in scored[:k]:
        seg = f"=== 第 {n} 页 ===\n{txt.strip()[:per_page]}"
        if used + len(seg) > max_chars:
            break
        buf.append(seg)
        used += len(seg)
    return "\n".join(buf)


def ask(prompt: str, max_tokens=4000) -> dict:
    body = {"model": MODEL, "messages": [{"role": "user", "content": prompt}],
            "temperature": 0, "max_tokens": max_tokens,
            "response_format": {"type": "json_object"}}
    for _ in range(3):
        try:
            r = requests.post(API, json=body, headers={"Authorization": "Bearer " + KEY}, timeout=150)
            if r.status_code == 200:
                return json.loads(r.json()["choices"][0]["message"]["content"])
        except Exception:  # noqa: BLE001
            pass
        time.sleep(2)
    return {}


def run_b2(pgs, topic: str):
    ctx = retrieve(pgs, TOPICS[topic])
    if not ctx:
        return []
    prompt = f"""你在做年报预检，话题：{topic}。
只根据下面的年报原文判断，不要用外部知识。找出该话题下最值得关注的 1-2 条异常：
数字异常、文字与数字矛盾、披露不充分（账龄/集中度/关联方/减值依据缺失）。
每条必须引用原文（不超过 120 字），没有把握就不要写。
输出 JSON：{{"issues": [{{"issue": "一句话", "quote": "原文摘录", "confidence": 0到1}}]}}
原文：
{ctx}"""
    res = ask(prompt)
    out = []
    for it in res.get("issues", [])[:2]:
        q = (it.get("quote") or "").strip()
        n = locate(pgs, q)
        if n is None:
            continue
        out.append({"topic": topic, "issue": (it.get("issue") or "")[:120], "quote": q[:160],
                    "page": n, "confidence": it.get("confidence"), "citation_ok": True})
    return out


def run_b1(pgs, report_text: str):
    head = report_text[:30000]
    prompt = """下面是一家上市公司年报的开头 3 万字。请找出这份年报中最值得关注的 6 个异常或矛盾
（数字异常、文字与数字打架、披露不充分）。只根据给定原文，不要用外部知识。
每条必须引用原文（不超过 120 字），没有把握就不要写。
输出 JSON：{"issues": [{"issue": "一句话", "quote": "原文摘录", "confidence": 0到1}]}
原文：
""" + head
    res = ask(prompt, 5000)
    out = []
    for it in res.get("issues", [])[:6]:
        q = (it.get("quote") or "").strip()
        n = locate(pgs, q)
        if n is None:
            continue
        out.append({"topic": "综合", "issue": (it.get("issue") or "")[:120], "quote": q[:160],
                    "page": n, "confidence": it.get("confidence"), "citation_ok": True})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["b1", "b2"], default="b2")
    ap.add_argument("--code", default="")
    ap.add_argument("--topics", default="")
    args = ap.parse_args()
    if not KEY:
        print("缺少 DS_KEY")
        return 1
    items = json.load(open(DATA, encoding="utf-8"))["items"]
    targets = [x for x in items if not args.code or x["code"] == args.code]
    outdir = os.path.join(ROOT, "data", "llm_b1" if args.mode == "b1" else "llm")
    os.makedirs(outdir, exist_ok=True)
    for it in targets:
        report = open(os.path.join(ROOT, it["dir"], "report.txt"), encoding="utf-8").read()
        pgs = pages(report)
        flags = []
        if args.mode == "b1":
            flags = run_b1(pgs, report)
        else:
            topics = [t.strip() for t in args.topics.split(",") if t.strip()] or list(TOPICS)
            for t in topics:
                flags += run_b2(pgs, t)
        json.dump({"code": it["code"], "name": it["name"], "flags": flags},
                  open(os.path.join(outdir, f"{it['code']}.json"), "w", encoding="utf-8", newline="\n"),
                  ensure_ascii=False, indent=1)
        print(f"== {it['name']} 结论 {len(flags)}")
        time.sleep(0.3)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
