"""修复回复函：有些公司发的是扫描件或"部分回复"，文本抽不出来。

做法：把该公司所有候选回复函都下下来（最多 3 份），各抽一遍文本，
选可读文字最多的那一份作为正式回复，并更新 dataset.json。

用法：
    cd 问询函预演
    python tools/repair_replies.py
"""
from __future__ import annotations

import json
import os
import re

import fitz
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "dataset.json")
UA = {"User-Agent": "Mozilla/5.0 Chrome/124.0", "Referer": "http://www.cninfo.com.cn/"}
API = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
STATIC = "http://static.cninfo.com.cn/"
TARGETS = ["603377", "600363", "600187", "688323", "601010", "603398", "600877", "603567"]


def clean(t):
    return re.sub(r"<[^>]+>", "", t or "")


def candidates(code: str):
    try:
        om = json.load(open(os.path.join(ROOT, "data", "orgmap.json"), encoding="utf-8"))
    except FileNotFoundError:
        om = {}
    org = om.get(code, "")
    if not org:
        r = requests.get("http://www.cninfo.com.cn/new/data/szse_stock.json", headers=UA, timeout=30)
        om = {x["code"]: x.get("orgId", "") for x in r.json().get("stockList") or []}
        json.dump(om, open(os.path.join(ROOT, "data", "orgmap.json"), "w", encoding="utf-8"))
        org = om.get(code, "")
    out = []
    for col in ("sse", "szse"):
        data = {"pageNum": 1, "pageSize": 30, "column": col, "tabName": "fulltext", "plate": "",
                "stock": f"{code},{org}", "searchkey": "2025年年度报告", "secdate": "", "tdate": "",
                "type": "", "isHLtitle": "true"}
        r = requests.post(API, data=data, headers=UA, timeout=30)
        for a in r.json().get("announcements") or []:
            t = clean(a.get("announcementTitle"))
            if "2025年年度报告" in t and "问询函" in t and any(k in t for k in ["回复", "专项说明", "核查意见"]):
                out.append(a)
    # 去重
    seen, uniq = set(), []
    for a in out:
        u = a.get("adjunctUrl")
        if u and u not in seen:
            seen.add(u)
            uniq.append(a)
    return uniq


def text_chars(pdf_path: str) -> int:
    try:
        d = fitz.open(pdf_path)
        return sum(len(p.get_text()) for p in d)
    except Exception:  # noqa: BLE001
        return 0


def main() -> int:
    items = json.load(open(DATA, encoding="utf-8"))["items"]
    for it in items:
        if it["code"] not in TARGETS:
            continue
        cands = candidates(it["code"])
        if not cands:
            print(f"   {it['code']} 无候选")
            continue
        best = None
        for i, a in enumerate(cands[:3]):
            p = os.path.join(ROOT, it["dir"], f"reply_cand{i}.pdf")
            if not os.path.exists(p):
                r = requests.get(STATIC + a["adjunctUrl"], headers=UA, timeout=180)
                open(p, "wb").write(r.content)
            n = text_chars(p)
            title = clean(a.get("announcementTitle"))
            print(f"   {it['code']} cand{i}: {n} 字 | {title[:40]}")
            if best is None or n > best[0]:
                best = (n, p, a, title)
        if best and best[0] > it.get("reply_chars", 0):
            os.replace(best[1], os.path.join(ROOT, it["dir"], "reply.pdf"))
            doc = fitz.open(os.path.join(ROOT, it["dir"], "reply.pdf"))
            pages = [f"=== 第 {i} 页 ===\n{pg.get_text()}" for i, pg in enumerate(doc, 1)]
            open(os.path.join(ROOT, it["dir"], "reply.txt"), "w", encoding="utf-8").write("\n".join(pages))
            it["reply_pages"] = doc.page_count
            it["reply_chars"] = sum(len(p) for p in pages)
            it["reply_title"] = best[3]
            it["reply_url"] = STATIC + best[2]["adjunctUrl"]
            print(f"   {it['code']} -> {it['reply_pages']}p / {it['reply_chars']} 字")
        for f in os.listdir(os.path.join(ROOT, it["dir"])):
            if f.startswith("reply_cand"):
                os.remove(os.path.join(ROOT, it["dir"], f))
    json.dump({"generated_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"), "items": items},
              open(DATA, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
