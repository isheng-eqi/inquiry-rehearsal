"""打初赛包：文档 + 演示 + 截图 + 代码 + 关键结果（不含原始 PDF）。

用法：
    cd 问询函预演
    python tools/make_package.py
"""
from __future__ import annotations

import datetime as dt
import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUB = os.path.join(ROOT, "submission")
OUTDIR = os.path.dirname(ROOT)

FILES = [
    "00-先读我-评委入口.md",
    "开发设计文档-问询函预演.md",
    "开发设计文档-问询函预演.docx",
    "实验记录.md",
    "Nexent编排说明.md",
]
DIRS = [
    ("videos", (".mp4",)),
    ("screenshots", (".png",)),
]
CODE = [
    "tools/build_dataset.py", "tools/extract_questions.py", "tools/llm_judge.py",
    "tools/llm_concerns.py", "tools/learn_concerns.py", "tools/llm_learned.py",
    "tools/match_strict.py", "tools/match_manual.py", "tools/evaluate_all.py",
    "tools/detect_v1.py", "tools/build_demo.py", "tools/make_package.py",
    "tools/verify_doc.py", "tools/audit_sample.py", "tools/quote_rate.py",
]
DATA = [
    "data/dataset.json", "data/questions.json", "data/concerns_learned.json",
    "data/eval_all.json", "data/eval_llm.json", "data/match_b2.json",
    "data/match_b1.json", "data/match_rules.json", "data/match_llm_learned.json",
    "data/match_llm_learned2.json", "data/audit_20.json", "data/quote_rate.json",
]
RESULT_DIRS = ["data/llm_learned", "data/llm"]


def main() -> int:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M")
    out = os.path.join(OUTDIR, f"ICT-问询函预演-初赛包-{stamp}.zip")
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in FILES:
            p = os.path.join(SUB, f)
            if os.path.exists(p):
                z.write(p, f"提交材料/{f}")
                n += 1
        for d, exts in DIRS:
            base = os.path.join(SUB, d)
            if not os.path.isdir(base):
                continue
            for fn in sorted(os.listdir(base)):
                if fn.endswith(exts):
                    z.write(os.path.join(base, fn), f"提交材料/{d}/{fn}")
                    n += 1
        for f in CODE:
            p = os.path.join(ROOT, f)
            if os.path.exists(p):
                z.write(p, f"代码/{f}")
                n += 1
        for f in DATA:
            p = os.path.join(ROOT, f)
            if os.path.exists(p):
                z.write(p, f"结果/{os.path.basename(f)}")
                n += 1
        for d in RESULT_DIRS:
            base = os.path.join(ROOT, d)
            if not os.path.isdir(base):
                continue
            for fn in sorted(os.listdir(base)):
                if fn.endswith(".json"):
                    z.write(os.path.join(base, fn), f"结果/{d.split('/')[-1]}/{fn}")
                    n += 1
        readme = (
            "ICT 自进化 · 问询函预演 · 初赛提交包\n"
            f"生成时间：{dt.datetime.now().isoformat(timespec='seconds')}\n\n"
            "目录：\n"
            "  提交材料/  入口、设计文档、实验记录、演示视频、证据截图\n"
            "  代码/      tools/*.py（数据下载、检测、评测、演示）\n"
            "  结果/      三基线、留出集严格匹配、逐公司结论\n\n"
            "原始年报/问询函 PDF（89MB）不入包，运行 代码/tools/build_dataset.py 可重新下载。\n"
            "复跑模型相关脚本需要 DS_KEY。\n"
        )
        z.writestr("README-包说明.txt", readme)
        n += 1
    size = os.path.getsize(out) / 1024 / 1024
    print(f"{out}  ({size:.2f} MB, {n} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
