"""用手工校准过的"顶层问题"重新做严格匹配，对比噪音标签下的结果。

用法：
    cd 问询函预演
    set DS_KEY=...
    python tools/match_manual.py
输出：
    data/match_manual.json
"""
from __future__ import annotations

import json
import os
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = os.environ.get("DS_KEY", "")
API = "https://api.deepseek.com/v1/chat/completions"
MODEL = os.environ.get("DS_MODEL", "deepseek-chat")

MANUAL = {
    "600491": [
        "持续经营能力：归母净利润-25.86亿元、连续三年亏损、有息负债100.35亿元且有逾期，说明持续经营是否存在重大不确定性",
        "主营业务与毛利率：营业收入44.31亿元同比-51.40%，土建施工毛利率大额为负，说明原因及与同行业差异",
        "应收账款和合同资产：应收账款52.86亿元、账龄1年以上占71.93%、坏账计提比例16.35%、本期坏账损失3.23亿元同比大增，说明计提是否充分",
        "资金往来：其他应收款24.62亿元、1年以上占73.39%、坏账准备11.28亿元，预付款项账龄1年以上，其他应付款大幅增长，说明是否存在关联方资金占用",
        "其他非流动资产：256.49亿元（PPP项目255.94亿元），一年内到期75.77亿元，说明减值计提是否充分",
    ],
    "600825": [
        "投资性房地产：账面价值5.94亿元、占非流动资产41.19%、未计提减值，近五年累计增长138.55%，说明是否应计提减值",
        "应收账款：余额0.94亿元，前五名占52.02%且全额计提，广告板块0.45亿元账龄2年以上全额计提，说明合理性",
        "其他应收款：余额1.30亿元、坏账准备0.90亿元、计提比例68.97%，前五名0.88亿元，说明形成原因",
        "投资理财：其他权益工具投资2.49亿元同比-16.24%，其他非流动金融资产1.42亿元同比-40.53%，说明公允价值与损失确认",
    ],
    "600363": [
        "预付款项：余额0.73亿元同比+443.42%，前两名对象占57.78%，说明商业实质与资金流向",
        "货币资金与短期负债：货币资金25.60亿元（受限0.75亿元），有息负债20.69亿元同比+49.71%，说明存贷双高的合理性",
        "主营业务与收入：激光系列与LED芯片收入波动大，说明收入确认与可持续性",
        "存货：账面价值5.74亿元同比-13.76%，发出商品2.05亿元同比+14.61%、占35.71%，说明跌价准备是否充分",
        "应付账款与其他应付款：应付账款8.11亿元、其他应付款1.70亿元同比大增（往来款1.30亿元），说明原因",
    ],
}


def ask(prompt: str) -> dict:
    body = {"model": MODEL, "messages": [{"role": "user", "content": prompt}],
            "temperature": 0, "max_tokens": 2000, "response_format": {"type": "json_object"}}
    for _ in range(3):
        try:
            r = requests.post(API, json=body, headers={"Authorization": "Bearer " + KEY}, timeout=150)
            if r.status_code == 200:
                return json.loads(r.json()["choices"][0]["message"]["content"])
        except Exception:  # noqa: BLE001
            pass
        time.sleep(2)
    return {}


def main() -> int:
    import sys
    d = sys.argv[1] if len(sys.argv) > 1 else "llm"
    if not KEY:
        print("缺少 DS_KEY")
        return 1
    out = []
    for code, qs in MANUAL.items():
        p = os.path.join(ROOT, "data", d, f"{code}.json")
        if not os.path.exists(p):
            continue
        flags = json.load(open(p, encoding="utf-8"))["flags"]
        qtext = "\n".join(f"Q{i+1}. {q}" for i, q in enumerate(qs))
        ftext = "\n".join(f"F{j+1}. {f.get('issue','')[:120]}" for j, f in enumerate(flags))
        prompt = f"""下面是监管问询的顶层问题和系统的结论。判断每条结论是否正面回答了某个问题（同一话题不算，要回答该问题）。
问题：
{qtext}
结论：
{ftext}
只输出 JSON：{{"matches":[{{"flag":"F1","question":"Q2"}}],"unmatched_flags":["F3"],"unmatched_questions":["Q1"]}}"""
        res = ask(prompt)
        m = res.get("matches", [])
        matched_q = len({x.get("question") for x in m if x.get("question")})
        matched_f = len({x.get("flag") for x in m if x.get("flag")})
        out.append({"code": code, "questions": len(qs), "flags": len(flags),
                    "matched_questions": matched_q, "matched_flags": matched_f, "matches": m})
        print(f"   {code}: 顶层问题 {len(qs)}，结论 {len(flags)}，配对问题 {matched_q}，配对结论 {matched_f}")
        for x in m:
            print("      ", x)
        time.sleep(0.4)
    json.dump(out, open(os.path.join(ROOT, "data", f"match_manual_{d}.json"), "w", encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=1)
    tq = sum(x["questions"] for x in out)
    mq = sum(x["matched_questions"] for x in out)
    tf = sum(x["flags"] for x in out)
    mf = sum(x["matched_flags"] for x in out)
    print(f"\n手工标签：问题命中 {mq}/{tq}（{mq/max(tq,1):.0%}），结论被支撑 {mf}/{tf}（{mf/max(tf,1):.0%}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
