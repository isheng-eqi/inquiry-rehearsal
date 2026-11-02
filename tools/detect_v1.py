"""第一版检查器：从年报里抽关键数字，按 4 条规则报异常。

规则（都可解释、可复核）：
  R1 收入下滑但应收账款增速明显高于收入（应收增速 - 收入增速 > 30pp）
  R2 预付款项同比增长超过 100%
  R3 收入同比下滑超过 30% 且归母净利润为负（持续经营压力）
  R4 正文出现"非经营性占用/资金占用"且伴随金额（资金占用迹象）

每条结论带页码与原文片段，输出 JSON。

用法：
    cd 问询函预演
    python tools/detect_v1.py --code 600491
输出：
    data/flags/<code>.json
"""
from __future__ import annotations

import argparse
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "dataset.json")
OUTDIR = os.path.join(ROOT, "data", "flags")


def norm(text: str) -> str:
    # PDF 里数字常被换行拆开："9,118,795,179.2 3" -> "9,118,795,179.23"
    return re.sub(r"(?<=[\d,.])\s+(?=\d)", "", text)


def page_of(text: str, pos: int) -> int:
    m = list(re.finditer(r"=== 第 (\d+) 页 ===", text[:pos]))
    return int(m[-1].group(1)) if m else 0


def num(s: str):
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def extract_main(text: str):
    # PDF 里两列数字常被粘在一起：4,431,303,030.539,118,795,179.23
    m = re.search(r"营业收入\s*(-?[\d,]+\.\d{2})(-?[\d,]+\.\d{2})\s*(-?[\d.]+)", text)
    if not m:
        return None
    return {"rev_now": num(m.group(1)), "rev_prev": num(m.group(2)),
            "rev_yoy": num(m.group(3)), "pos": m.start()}


def extract_bs_item(text: str, item: str):
    # 合并资产负债表里第一次出现：项目 期末 期初
    idx = text.find("合并资产负债表")
    if idx < 0:
        return None
    seg = text[idx:idx + 60000]
    m = re.search(item + r"\s*(-?[\d,]+\.\d{2})(-?[\d,]+\.\d{2})", seg)
    if not m:
        return None
    return {"now": num(m.group(1)), "prev": num(m.group(2)), "pos": idx + m.start()}


def growth(now, prev):
    if now is None or prev in (None, 0):
        return None
    return (now - prev) / abs(prev) * 100


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    args = ap.parse_args()
    items = json.load(open(DATA, encoding="utf-8"))["items"]
    it = next((x for x in items if x["code"] == args.code), None)
    if not it:
        print("no such code")
        return 1
    raw = open(os.path.join(ROOT, it["dir"], "report.txt"), encoding="utf-8").read()
    text = norm(raw)
    flags = []

    main_data = extract_main(text)
    ar = extract_bs_item(text, "应收账款")
    pre = extract_bs_item(text, "预付款项")
    np_ = re.search(r"归属于上市公司股东的净利润\s*\(?([\-\d,\.]+)\)?", text)

    if main_data and ar:
        ar_g = growth(ar["now"], ar["prev"])
        rev_yoy = main_data["rev_yoy"] if main_data["rev_yoy"] is not None else growth(main_data["rev_now"], main_data["rev_prev"])
        if ar_g is not None and rev_yoy is not None and rev_yoy < 0 and ar_g - rev_yoy > 30:
            flags.append({"rule": "R1 收入下滑但应收快增", "page": page_of(text, ar["pos"]),
                          "values": {"应收本期": ar["now"], "应收上期": ar["prev"], "应收增速%": round(ar_g, 1),
                                     "收入同比%": round(rev_yoy, 1)},
                          "quote": text[ar["pos"]:ar["pos"] + 80]})
    if pre:
        g = growth(pre["now"], pre["prev"])
        if g is not None and g > 100:
            flags.append({"rule": "R2 预付款项同比翻倍", "page": page_of(text, pre["pos"]),
                          "values": {"本期": pre["now"], "上期": pre["prev"], "增速%": round(g, 1)},
                          "quote": text[pre["pos"]:pre["pos"] + 80]})
    if main_data and main_data["rev_yoy"] is not None and main_data["rev_yoy"] < -30:
        flags.append({"rule": "R3 收入大幅下滑", "page": page_of(text, main_data["pos"]),
                      "values": {"收入同比%": main_data["rev_yoy"]},
                      "quote": text[main_data["pos"]:main_data["pos"] + 100]})
    # R5 资产构成表：科目 本期 占比 上期 占比 变动%（用未压平的原文，保住换行）
    for m in re.finditer(r"(预付款项|应收账款|存货|在建工程)\s*(-?[\d,]+\.\d{2})\s+([\d.]+)\s+(-?[\d,]+\.\d{2})\s+([\d.]+)\s+(-?[\d.]+)", raw):
        try:
            chg = float(m.group(6))
        except ValueError:
            continue
        if abs(chg) >= 100:
            flags.append({"rule": f"R5 {m.group(1)}变动{chg:.0f}%", "page": page_of(raw, m.start()),
                          "values": {"科目": m.group(1), "本期": m.group(2), "上期": m.group(4), "变动%": chg},
                          "quote": raw[m.start():m.start() + 90]})
    # R2' 正文自述"预付款项同比增长 443.42%"这类大幅变动
    for m in re.finditer(r"(预付款项|应收账款|存货|在建工程)[^。]{0,60}?(?:同比)?(?:增长|增加|上升)[^。]{0,12}?(\d{2,4}\.\d+)%", raw):
        try:
            g = float(m.group(2))
        except ValueError:
            continue
        if g >= 100:
            flags.append({"rule": f"R2' {m.group(1)}同比增{g:.0f}%", "page": page_of(raw, m.start()),
                          "values": {"科目": m.group(1), "同比%": g},
                          "quote": raw[m.start():m.start() + 100]})
    for m in re.finditer(r"(非经营性占用|资金占用)[^。]{0,80}?([\d,]+\.\d{2}\s*万?元)", text):
        flags.append({"rule": "R4 资金占用迹象", "page": page_of(text, m.start()),
                      "values": {"金额原文": m.group(2)}, "quote": text[m.start():m.start() + 100]})
        break

    os.makedirs(OUTDIR, exist_ok=True)
    out = {"code": args.code, "name": it["name"], "flags": flags,
           "main": main_data and {k: v for k, v in main_data.items() if k != "pos"},
           "receivable": ar and {k: v for k, v in ar.items() if k != "pos"},
           "prepay": pre and {k: v for k, v in pre.items() if k != "pos"}}
    json.dump(out, open(os.path.join(OUTDIR, f"{args.code}.json"), "w", encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=1)
    print(f"== {it['name']} ({args.code})")
    for f in flags:
        print(f"   [{f['rule']}] p{f['page']} {f['values']}")
    print(f"   {len(flags)} flags -> data/flags/{args.code}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
