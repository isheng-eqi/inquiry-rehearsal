"""生成单文件体检报告页（交互交付物）。

输入：data/llm/<code>.json、data/kg.json、data/questions.json、data/match_b2.json
输出：submission/report-<code>.html

用法：
    cd 问询函预演
    python tools/build_report_html.py --code 600363
"""
from __future__ import annotations

import argparse
import html
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "submission")


def load(name):
    with open(os.path.join(ROOT, "data", name), encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", default="600363")
    args = ap.parse_args()
    code = args.code
    ds = {x["code"]: x for x in load("dataset.json")["items"]}
    it = ds[code]
    src = os.path.join(ROOT, "data", "llm_concerns", f"{code}.json")
    if not os.path.exists(src):
        src = os.path.join(ROOT, "data", "llm", f"{code}.json")
    flags = json.load(open(src, encoding="utf-8"))["flags"]
    kg = load("kg.json")
    concerns = {n["label"]: n["props"] for n in kg["nodes"] if n["type"] == "Concern"}
    questions = next((x["questions"] for x in load("questions.json")["items"] if x["code"] == code), [])
    matches = []
    mp = os.path.join(ROOT, "data", "match_llm_concerns.json")
    if not os.path.exists(mp):
        mp = os.path.join(ROOT, "data", "match_b2.json")
    if os.path.exists(mp):
        item = next((x for x in json.load(open(mp, encoding="utf-8"))["items"] if x["code"] == code), None)
        matches = item.get("matches", []) if item else []

    ALIAS = {
        "收入确认与毛利率": "收入与毛利率", "应收账款与坏账": "应收账款坏账",
        "预付款项": "预付款项异常", "其他应收款与资金往来": "其他应收款减值",
        "存货与跌价": "存货跌价准备", "在建工程与转固": "在建工程与转固",
        "货币资金与有息负债": "货币资金与偿债", "关联交易与资金占用": "关联交易与资金占用",
        "商誉与减值": "商誉与减值", "投资性房地产": "投资性房地产",
    }
    groups = {}
    for f in flags:
        groups.setdefault(f.get("topic", "其他"), []).append(f)

    cards = []
    for topic, items in groups.items():
        c = concerns.get(topic, concerns.get(ALIAS.get(topic, ""), {}))
        rows = []
        for f in items:
            rows.append(f"""
            <div class="flag">
              <div class="issue">{html.escape(f.get('issue',''))}</div>
              <div class="meta">第 {f.get('page')} 页 · 关注点：{html.escape(topic)}</div>
              <blockquote>{html.escape((f.get('quote') or '')[:160])}</blockquote>
            </div>""")
        cards.append(f"""
        <section class="card">
          <h2>{html.escape(topic)} <span class="count">{len(items)} 条</span></h2>
          <div class="std">{html.escape(c.get('standard','未对齐'))}</div>
          {''.join(rows)}
        </section>""")

    qrows = []
    for i, q in enumerate(questions, 1):
        paired = [m for m in matches if m.get("question") == f"Q{i}"]
        tag = f"<span class='hit'>系统已提前答上（{len(paired)} 条结论）</span>" if paired else "<span class='miss'>未提前覆盖</span>"
        qrows.append(f"<li><b>Q{i}</b> {tag}<br>{html.escape(q[:160])}</li>")

    page = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>{html.escape(it['name'])} 年报预检报告</title>
<style>
 body{{font-family:"Microsoft YaHei",system-ui,sans-serif;background:#0b1220;color:#e8eefc;margin:0;padding:32px}}
 .wrap{{max-width:980px;margin:0 auto}}
 h1{{font-size:30px;margin:0 0 6px}} .sub{{color:#8fa6c8;margin-bottom:24px}}
 .stats{{display:flex;gap:12px;margin:20px 0 28px}}
 .stat{{flex:1;background:#131d33;border-radius:10px;padding:14px}}
 .stat b{{font-size:24px;display:block}}
 .card{{background:#131d33;border-radius:12px;padding:20px;margin:16px 0}}
 .card h2{{margin:0 0 4px;font-size:18px}} .count{{color:#8fa6c8;font-size:13px;font-weight:400}}
 .std{{color:#7fb0ff;font-size:13px;margin-bottom:12px}}
 .flag{{border-top:1px solid #22304d;padding:12px 0}}
 .issue{{font-size:15px;line-height:1.6}}
 .meta{{color:#8fa6c8;font-size:12px;margin:4px 0}}
 blockquote{{margin:6px 0 0;padding:8px 10px;background:#0d1628;border-left:3px solid #3b6fd4;color:#b9c9e6;font-size:13px}}
 .hit{{color:#5dd39e}} .miss{{color:#e6a23c}}
 ul{{line-height:1.9}} footer{{margin-top:28px;color:#6f86a8;font-size:12px}}
</style></head><body><div class="wrap">
 <h1>{html.escape(it['name'])} 年报预检</h1>
 <div class="sub">{code} · 2025 年报 {it.get('report_pages')} 页 · 数据来源：巨潮资讯网</div>
 <div class="stats">
   <div class="stat"><b>{len(flags)}</b>条结论</div>
   <div class="stat"><b>{len(groups)}</b>个关注点</div>
   <div class="stat"><b>{len(matches)}</b>条与问询函配对</div>
   <div class="stat"><b>{len(questions)}</b>个真实问询问题</div>
 </div>
 <h2 style="font-size:18px">一、与真实问询函对照</h2>
 <ul>{''.join(qrows) or '<li>该公司未收集到问询问题</li>'}</ul>
 <h2 style="font-size:18px">二、逐条预检结论</h2>
 {''.join(cards)}
 <footer>每条结论均指向年报原文页码；仅陈述原文与数字，不构成投资建议。<br>
 本页由 tools/build_report_html.py 生成，数据可复核。</footer>
</div></body></html>"""
    path = os.path.join(OUT, f"report-{it['name']}.html")
    os.makedirs(OUT, exist_ok=True)
    open(path, "w", encoding="utf-8").write(page)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
