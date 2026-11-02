"""监管关注点驱动的检索与判断（进化第一版）。

关注点来自 143 个真实问询问题的归纳，每条带：
- 关键词（检索用）
- 监管通常追问什么（提示词用）

对每家公司、每个关注点检索 6 页，让模型找 1-2 条异常，引用原文。

用法：
    cd 问询函预演
    set DS_KEY=...
    python tools/llm_concerns.py --code 600491
输出：
    data/llm_concerns/<code>.json
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
OUTDIR = os.path.join(ROOT, "data", "llm_concerns")

CONCERNS = {
    "收入确认与毛利率": {
        "kws": ["营业收入", "收入确认", "毛利率", "主营业务"],
        "ask": "收入变动原因、第四季度收入是否异常、毛利率与同业差异、是否存在提前确认",
    },
    "应收账款与坏账": {
        "kws": ["应收账款", "坏账", "账龄", "合同资产", "前五名"],
        "ask": "账龄结构、前五名集中度、单项与组合计提依据、坏账损失同比大增原因",
    },
    "预付款项": {
        "kws": ["预付款项", "预付款", "预付对象"],
        "ask": "预付款大幅增长原因、对象与商业实质、是否流向关联方、长期挂账",
    },
    "其他应收款与资金往来": {
        "kws": ["其他应收款", "往来款", "资金拆借", "其他应付款"],
        "ask": "其他应收款账龄、坏账、往来对象、是否存在关联方占用",
    },
    "存货与跌价": {
        "kws": ["存货", "跌价", "发出商品", "库存商品"],
        "ask": "存货结构、跌价准备计提与转回依据、库龄、发出商品占比",
    },
    "在建工程与转固": {
        "kws": ["在建工程", "转固", "固定资产"],
        "ask": "在建工程进度、是否达到预定可使用状态、长期不转固原因",
    },
    "商誉与减值": {
        "kws": ["商誉", "减值测试", "资产组"],
        "ask": "商誉账面价值、资产组划分、减值测试关键假设与结论",
    },
    "投资性房地产": {
        "kws": ["投资性房地产", "公允价值", "减值"],
        "ask": "投资性房地产计量模式、公允价值变动、未计提减值的合理性",
    },
    "货币资金与有息负债": {
        "kws": ["货币资金", "短期借款", "利息收入", "利息费用", "受限"],
        "ask": "存贷双高、受限资金、利息收入与货币资金是否匹配",
    },
    "关联交易与资金占用": {
        "kws": ["关联交易", "关联方", "非经营性占用", "资金占用"],
        "ask": "关联交易定价公允性、关联方资金占用、代垫代付",
    },
    "应付与往来": {
        "kws": ["应付账款", "其他应付款", "往来款"],
        "ask": "应付款大幅增长原因、账龄、是否存在关联方",
    },
    "诉讼担保与内控": {
        "kws": ["诉讼", "仲裁", "担保", "内部控制", "否定意见"],
        "ask": "重大诉讼、对外担保、内控缺陷及整改",
    },
}


def run_concern(pgs, name: str, conf: dict):
    ctx = L.retrieve(pgs, conf["kws"], k=6, per_page=1500, max_chars=9000)
    if not ctx:
        return []
    prompt = f"""你在做年报预检，关注点：{name}。
监管在这个关注点上通常会追问：{conf['ask']}。
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
        out.append({"topic": name, "issue": (it.get("issue") or "")[:120], "quote": q[:160],
                    "page": n, "confidence": it.get("confidence"), "citation_ok": True})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", default="")
    args = ap.parse_args()
    if not L.KEY:
        print("缺少 DS_KEY")
        return 1
    items = json.load(open(DATA, encoding="utf-8"))["items"]
    targets = [x for x in items if not args.code or x["code"] == args.code]
    os.makedirs(OUTDIR, exist_ok=True)
    for it in targets:
        report = open(os.path.join(ROOT, it["dir"], "report.txt"), encoding="utf-8").read()
        pgs = L.pages(report)
        flags = []
        for name, conf in CONCERNS.items():
            flags += run_concern(pgs, name, conf)
            time.sleep(0.2)
        json.dump({"code": it["code"], "name": it["name"], "flags": flags},
                  open(os.path.join(OUTDIR, f"{it['code']}.json"), "w", encoding="utf-8", newline="\n"),
                  ensure_ascii=False, indent=1)
        print(f"== {it['name']} 结论 {len(flags)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
