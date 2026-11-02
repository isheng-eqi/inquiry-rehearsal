"""从训练集问询问题里归纳监管关注点（不碰测试集）。

输入：训练公司的问询问题（data/questions.json）
输出：data/concerns_learned.json（10 条左右，每条含 name / keywords / ask）

用法：
    cd 问询函预演
    set DS_KEY=...
    python tools/learn_concerns.py
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
TRAIN = ["600825", "600491", "600363", "920932", "600703", "600545", "600818", "600877"]


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", default=",".join(TRAIN))
    ap.add_argument("--out", default="data/concerns_learned.json")
    args = ap.parse_args()
    train = [x.strip() for x in args.train.split(",") if x.strip()]
    qs = {x["code"]: x for x in json.load(open(os.path.join(ROOT, "data", "questions.json"), encoding="utf-8"))["items"]}
    lines = []
    for code in train:
        it = qs.get(code)
        if not it:
            continue
        for q in it["questions"][:8]:
            lines.append(f"- {it['name']}：{q[:220]}")
    text = "\n".join(lines)
    prompt = f"""下面是交易所对 8 家公司年报的问询问题节选。请归纳出 10 个监管关注点，
每个关注点给出：名称（不超过 12 字）、5-8 个用于检索年报的关键词、监管通常追问什么（一句话）。
只输出 JSON：{{"concerns":[{{"name":"...","keywords":["..."],"ask":"..."}}]}}
问题节选：
{text}"""
    body = {"model": MODEL, "messages": [{"role": "user", "content": prompt}],
            "temperature": 0, "max_tokens": 3000, "response_format": {"type": "json_object"}}
    for _ in range(3):
        r = requests.post(API, json=body, headers={"Authorization": "Bearer " + KEY}, timeout=150)
        if r.status_code == 200:
            data = json.loads(r.json()["choices"][0]["message"]["content"])
            break
        time.sleep(3)
    else:
        print("API 失败")
        return 1
    concerns = data.get("concerns", [])
    out = os.path.join(ROOT, args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump({"train": train, "concerns": concerns},
              open(out, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
    print(f"学到 {len(concerns)} 个关注点：")
    for c in concerns:
        print(f"   {c['name']} | 关键词 {c['keywords'][:4]} | {c['ask'][:50]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
