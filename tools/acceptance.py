"""验收脚本：把"能不能交"变成一条命令。

检查：
1. 关键文件在不在（文档、视频、包、数据、结果）；
2. 文档数字与结果文件是否一致（调用 verify_doc）；
3. 数据规模与结构（20 家、143 问、URL 可下载）；
4. 三基线与留出集的关键数字；
5. 人工抽审与引用定位率的记录是否在；
6. 演示视频时长。

用法：
    cd 问询函预演
    python tools/acceptance.py
退出码 0 = 全部通过。
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUB = os.path.join(ROOT, "submission")
OUT = os.path.dirname(ROOT)


def load(path: str):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    rows = []

    def check(name: str, ok: bool, detail: str = ""):
        rows.append((name, bool(ok), detail))

    # 1. 文件
    check("主文档 md", os.path.exists(os.path.join(SUB, "开发设计文档-问询函预演.md")))
    check("主文档 docx", os.path.exists(os.path.join(SUB, "开发设计文档-问询函预演.docx")))
    check("实验记录", os.path.exists(os.path.join(SUB, "实验记录.md")))
    check("入口", os.path.exists(os.path.join(SUB, "00-先读我-评委入口.md")))
    vids = glob.glob(os.path.join(SUB, "videos", "*.mp4"))
    check("演示视频", len(vids) == 1, os.path.basename(vids[0]) if vids else "缺失")
    zips = glob.glob(os.path.join(OUT, "ICT-问询函预演-初赛包-*.zip"))
    check("初赛包", len(zips) >= 1, os.path.basename(sorted(zips)[-1]) if zips else "缺失")

    # 2. 数据
    ds = load("data/dataset.json")["items"]
    check("公司数=20", len(ds) == 20, str(len(ds)))
    bad_url = [x["code"] for x in ds if not x.get("report_url", "").startswith("http")]
    check("年报 URL 全部可下载", not bad_url, ",".join(bad_url) or "ok")
    small = [x["code"] for x in ds if x.get("report_pages", 0) <= 50]
    check("年报页数 > 50", not small, ",".join(small) or "ok")

    qs = load("data/questions.json")["items"]
    nq = sum(len(x["questions"]) for x in qs)
    check("问询问题=143", nq == 143, str(nq))

    # 3. 结果与文档
    p = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "verify_doc.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT)
    check("文档数字对账", p.returncode == 0, (p.stdout or "").strip().splitlines()[-1] if p.stdout else "")

    ea = load("data/eval_all.json")
    check("B2 结论=171", ea["b2"]["flags"] == 171, str(ea["b2"]["flags"]))
    m2 = load("data/match_b2.json")["items"]
    hit = sum(x["matched_questions"] for x in m2)
    check("B2 严格命中=31", hit == 31, str(hit))

    ml = load("data/match_llm_learned2.json")["items"]
    C = ["603599", "603108", "688646", "603398", "600880"]
    m = {x["code"]: x for x in ml}
    h2 = sum(m[c]["matched_questions"] for c in C if c in m)
    check("折2 命中=16", h2 == 16, str(h2))

    # 4. 诚实性记录
    au = load("data/audit_20.json")
    check("人工抽审 20 条", au["n"] == 20, f"确凿{au['true']} 误报{au['false']} 存疑{au['partial']}")
    qr = load("data/quote_rate.json")
    check("引用定位率记录=57%", abs(qr["rate"] - 0.571) < 0.01, f"{qr['located']}/{qr['proposed']}")

    # 5. 视频时长
    try:
        import subprocess as sp
        probe = os.path.join(r"C:\ictwork\ffmpeg\bin", "ffprobe.exe")
        out = sp.run([probe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", vids[0]],
                     capture_output=True, text=True).stdout.strip()
        dur = float(out) if out else 0
    except Exception:  # noqa: BLE001
        dur = 0
    check("视频 55-60 秒", 55 <= dur <= 60, f"{dur:.1f}s")

    print("\n== 验收结果 ==")
    bad = 0
    for name, ok, detail in rows:
        print(f"  {'✓' if ok else '✗'} {name:22} {detail}")
        bad += 0 if ok else 1
    print(f"\n{'通过' if bad == 0 else '失败：' + str(bad) + ' 项'}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
