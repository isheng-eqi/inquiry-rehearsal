"""构建数据集：20 家公司，2025 年年报 + 年报问询函回复（含问题原文）。

数据源：巨潮资讯网公开接口。
路线：先搜"2025年年度报告 问询函"拿到有回复的公司，再按公司代码 + orgId
逐家查公告，挑出年报与回复函。

产出：
    data/raw/<代码>_<简称>/{report,reply}.pdf/.txt
    data/dataset.json
"""
from __future__ import annotations

import json
import os
import re
import time

import fitz
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
OUT = os.path.join(ROOT, "data", "dataset.json")
UA = {"User-Agent": "Mozilla/5.0 Chrome/124.0", "Referer": "http://www.cninfo.com.cn/"}
API = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
STATIC = "http://static.cninfo.com.cn/"
LIMIT = 20


def clean(t: str) -> str:
    return re.sub(r"<[^>]+>", "", t or "")


def safe(name: str) -> str:
    return re.sub(r'[*?"<>|\\/:]', "", name or "").strip()


def post(payload: dict):
    try:
        r = requests.post(API, data=payload, headers=UA, timeout=30)
        return r.json()
    except Exception:  # noqa: BLE001
        return {}


def search(key: str, page: int, column: str = "sse", stock: str = ""):
    return post({"pageNum": page, "pageSize": 30, "column": column, "tabName": "fulltext",
                 "plate": "", "stock": stock, "searchkey": key, "secdate": "", "tdate": "",
                 "type": "", "isHLtitle": "true"})


def org_map() -> dict:
    r = requests.get("http://www.cninfo.com.cn/new/data/szse_stock.json", headers=UA, timeout=30)
    arr = r.json().get("stockList") or []
    return {x["code"]: x.get("orgId", "") for x in arr if x.get("code")}


def pick_report(anns):
    scored = []
    for a in anns:
        t = clean(a.get("announcementTitle"))
        if "2025年年度报告" not in t or not a.get("adjunctUrl"):
            continue
        bad = ["摘要", "问询", "回复", "英文", "半年", "专项", "说明", "审计", "制度", "延期", "公告"]
        if any(b in t for b in bad):
            continue
        score = 0
        if t.rstrip().endswith("2025年年度报告"):
            score += 5
        if "修订" in t or "更正后" in t:
            score += 3
        if t.startswith("2025年年度报告"):
            score += 2
        scored.append((score, len(t), a))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return scored[0][2] if scored else None


def pick_reply(anns):
    scored = []
    for a in anns:
        t = clean(a.get("announcementTitle"))
        if "2025年年度报告" not in t or "问询函" not in t or not a.get("adjunctUrl"):
            continue
        if not any(k in t for k in ["回复", "专项说明", "核查意见", "回复意见"]):
            continue
        score = 0
        if "回复" in t and "公司" in t:
            score += 4
        if "回复" in t:
            score += 2
        if "专项说明" in t or "核查意见" in t:
            score -= 1
        scored.append((score, len(t), a))
    scored.sort(key=lambda x: (-x[0], -x[1]))
    return scored[0][2] if scored else None


def save_pdf(url: str, pdf_path: str, txt_path: str):
    if not os.path.exists(pdf_path):
        r = requests.get(url, headers=UA, timeout=180)
        open(pdf_path, "wb").write(r.content)
        time.sleep(0.5)
    doc = fitz.open(pdf_path)
    pages = [f"=== 第 {i} 页 ===\n{pg.get_text()}" for i, pg in enumerate(doc, 1)]
    open(txt_path, "w", encoding="utf-8").write("\n".join(pages))
    return doc.page_count, sum(len(p) for p in pages)


def main() -> int:
    os.makedirs(RAW, exist_ok=True)
    print("org map...")
    om = org_map()
    print("  stocks", len(om))

    print("crawl replies...")
    codes = {}
    for p in range(1, 13):
        j = search("2025年年度报告 问询函", p)
        for a in j.get("announcements") or []:
            t = clean(a.get("announcementTitle"))
            code = a.get("secCode")
            if code and "2025年年度报告" in t and "问询函" in t and any(k in t for k in ["回复", "专项说明", "核查意见"]):
                codes.setdefault(code, clean(a.get("secName")))
        time.sleep(0.4)
    print("  companies with reply", len(codes))

    dataset = []
    for code, name in codes.items():
        if len(dataset) >= LIMIT:
            break
        org = om.get(code, "")
        if not org:
            continue
        anns = []
        for col in ("sse", "szse"):
            j = search("2025年年度报告", 1, col, f"{code},{org}")
            anns.extend(j.get("announcements") or [])
        rep = pick_report(anns)
        rep_ann = pick_reply(anns)
        if not rep or not rep_ann:
            continue
        d = os.path.join(RAW, f"{code}_{safe(name)}")
        os.makedirs(d, exist_ok=True)
        item = {"code": code, "name": name, "dir": os.path.relpath(d, ROOT).replace("\\", "/"),
                "report_title": clean(rep["announcementTitle"]),
                "reply_title": clean(rep_ann["announcementTitle"]),
                "report_url": STATIC + rep["adjunctUrl"],
                "reply_url": STATIC + rep_ann["adjunctUrl"]}
        for kind, a in (("report", rep), ("reply", rep_ann)):
            pages, chars = save_pdf(STATIC + a["adjunctUrl"],
                                    os.path.join(d, f"{kind}.pdf"),
                                    os.path.join(d, f"{kind}.txt"))
            item[f"{kind}_pages"] = pages
            item[f"{kind}_chars"] = chars
        dataset.append(item)
        print(f"   {code} {name}: 年报 {item['report_pages']}p / 回复 {item['reply_pages']}p")
        time.sleep(0.3)

    json.dump({"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "items": dataset},
              open(OUT, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
    print(f"\n{len(dataset)} companies -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
