"""严格匹配：每条结论是否正面回答了某个问询问题。

不做逐条 API 调用，而是一家公司一次：把问题列表和结论列表一起给模型，
让它输出配对关系。20 家公司 = 20 次调用。

用法：
    cd 问询函预演
    set DS_KEY=...
    python tools/match_strict.py --source b2
    python tools/match_strict.py --source b1
输出：
    data/match_<source>.json
"""
from __future__ import annotations

import argparse
import json
import os
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = os.environ.get("DS_KEY", "")
API = "https://api.deepseek.com/v1/chat/completions"
MODEL = os.environ.get("DS_MODEL", "deepseek-chat")


def ask(prompt: str) -> dict:
    body = {"model": MODEL, "messages": [{"role": "user", "content": prompt}],
            "temperature": 0, "max_tokens": 2500, "response_format": {"type": "json_object"}}
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
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["b1", "b2", "rules"], required=True)
    ap.add_argument("--dir", default="")
    args = ap.parse_args()
    if not KEY:
        print("缺少 DS_KEY")
        return 1
    qs = json.load(open(os.path.join(ROOT, "data", "questions.json"), encoding="utf-8"))["items"]
    out = []
    for item in qs:
        if args.dir:
            p = os.path.join(ROOT, "data", args.dir, f"{item['code']}.json")
        elif args.source == "rules":
            p = os.path.join(ROOT, "data", "flags", f"{item['code']}.json")
        else:
            d = "llm_b1" if args.source == "b1" else "llm"
            p = os.path.join(ROOT, "data", d, f"{item['code']}.json")
        if not os.path.exists(p) or not item["questions"]:
            continue
        flags = json.load(open(p, encoding="utf-8")).get("flags", [])
        if not flags:
            out.append({"code": item["code"], "name": item["name"], "matches": [], "flags": 0,
                        "questions": len(item["questions"]), "matched_flags": 0, "matched_questions": 0})
            continue
        qtext = "\n".join(f"Q{i+1}. {q[:200]}" for i, q in enumerate(item["questions"]))
        def label(f):
            return (f.get("issue") or f.get("rule") or "")[:120] + "（" + (f.get("topic") or "规则") + "）"
        ftext = "\n".join(f"F{j+1}. {label(f)}" for j, f in enumerate(flags))
        prompt = f"""下面是监管问询的问题和系统的结论。请判断：
1）每条结论是否正面回答了某个问题（不是同一话题，而是回答了那个问题）；
2）哪些问题没有任何结论回答。

问题：
{qtext}

结论：
{ftext}

只输出 JSON：{{"matches":[{{"flag":"F1","question":"Q3"}}],"unmatched_flags":["F2"],"unmatched_questions":["Q1"]}}
"""
        res = ask(prompt)
        matches = res.get("matches", [])
        out.append({"code": item["code"], "name": item["name"], "flags": len(flags),
                    "questions": len(item["questions"]), "matches": matches,
                    "matched_flags": len({m.get("flag") for m in matches if m.get("flag")}),
                    "matched_questions": len({m.get("question") for m in matches if m.get("question")})})
        print(f"   {item['name']:8} 问题 {len(item['questions']):2} 结论 {len(flags):2} "
              f"配对 {len(matches):2}")
        time.sleep(0.4)
    json.dump({"source": args.source, "items": out},
              open(os.path.join(ROOT, "data", f"match_{args.dir or args.source}.json"), "w", encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=1)
    tq = sum(x["questions"] for x in out)
    mq = sum(x["matched_questions"] for x in out)
    tf = sum(x["flags"] for x in out)
    mf = sum(x["matched_flags"] for x in out)
    print(f"\n{args.source}: 问题命中 {mq}/{tq}（{mq/max(tq,1):.0%}），结论被支撑 {mf}/{tf}（{mf/max(tf,1):.0%}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
