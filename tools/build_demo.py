"""生成「问询函预演」60 秒演示：真实年报页 → 真实问询函页 → 数字卡。

素材：data/raw/600363_联创光电/report.pdf（第 25 页）、reply.pdf（第 1 页）。
输出：submission/videos/00-问询函预演-60秒.mp4

用法：
    cd 问询函预演
    python tools/build_demo.py
"""
from __future__ import annotations

import os
import shutil
import subprocess

import fitz
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw", "600363_联创光电")
WORK = os.path.join(ROOT, "submission", "videos", "_build")
OUT = os.path.join(ROOT, "submission", "videos", "00-问询函预演-60秒.mp4")
FF = r"C:\ictwork\ffmpeg\bin\ffmpeg.exe"
FONT = r"C:\Windows\Fonts\msyh.ttc"
W, H = 1920, 1080


def run(args, cwd=None):
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=cwd)
    if p.returncode != 0:
        print(p.stderr[-800:])
        raise SystemExit(1)


def page_image(pdf: str, page_no: int, out: str, caption: str, keyword: str = ""):
    doc = fitz.open(pdf)
    page = doc[page_no - 1]
    clip = None
    if keyword:
        hits = page.search_for(keyword)
        if hits:
            r = hits[0]
            clip = fitz.Rect(40, max(0, r.y0 - 300), page.rect.width - 40,
                             min(page.rect.height, r.y1 + 180))
    pix = page.get_pixmap(matrix=fitz.Matrix(2.6, 2.6), clip=clip)
    pix.save(out)
    img = Image.open(out).convert("RGB")
    # 缩放到画布内
    scale = min((W - 120) / img.width, (H - 240) / img.height)
    img = img.resize((int(img.width * scale), int(img.height * scale)))
    canvas = Image.new("RGB", (W, H), (11, 18, 32))
    canvas.paste(img, ((W - img.width) // 2, 40))
    d = ImageDraw.Draw(canvas)
    f = ImageFont.truetype(FONT, 34)
    tw = d.textlength(caption, font=f)
    d.rectangle([0, H - 150, W, H], fill=(11, 18, 32))
    d.text(((W - tw) / 2, H - 120), caption, font=f, fill=(235, 240, 250))
    canvas.save(out)
    return out


def card(path: str, title: str, sub: str, big: bool = False):
    im = Image.new("RGB", (W, H), (11, 18, 32))
    d = ImageDraw.Draw(im)
    f1 = ImageFont.truetype(FONT, 82 if big else 62)
    f2 = ImageFont.truetype(FONT, 40 if big else 34)
    w1 = d.textlength(title, font=f1)
    d.text(((W - w1) / 2, 400 if big else 420), title, font=f1, fill=(255, 255, 255))
    w2 = d.textlength(sub, font=f2)
    d.text(((W - w2) / 2, 540 if big else 530), sub, font=f2, fill=(150, 195, 255))
    im.save(path)


def main() -> int:
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    shutil.copyfile(FONT, os.path.join(WORK, "font.ttc"))
    segs = []

    def seg(img, secs, name):
        p = os.path.join(WORK, f"{name}.mp4")
        run([FF, "-y", "-loglevel", "error", "-loop", "1", "-i", img, "-t", str(secs),
             "-r", "25", "-c:v", "libx264", "-pix_fmt", "yuv420p", p])
        segs.append(p)

    card(os.path.join(WORK, "s0.png"), "问询函预演", "监管问之前，先问自己", True)
    seg(os.path.join(WORK, "s0.png"), 3, "seg0")

    page_image(os.path.join(RAW, "report.pdf"), 25, os.path.join(WORK, "s1.png"),
               "年报第 25 页：预付款项 0.73 亿元，同比 +443.42%", keyword="443.42")
    seg(os.path.join(WORK, "s1.png"), 12, "seg1")

    card(os.path.join(WORK, "s2.png"), "系统结论", "预付款项异常；第一大预付对象占 57.78%，审计保留意见涉及该款项")
    seg(os.path.join(WORK, "s2.png"), 7, "seg2")

    page_image(os.path.join(RAW, "reply.pdf"), 1, os.path.join(WORK, "s3.png"),
               "问询函第一条：同样的数字，同样的对象", keyword="443.42")
    seg(os.path.join(WORK, "s3.png"), 12, "seg3")

    card(os.path.join(WORK, "s3b.png"), "72 个问题里，答上 29 个", "40% 不是终点：还有 43 个问题没答上")
    seg(os.path.join(WORK, "s3b.png"), 6, "seg3b")

    card(os.path.join(WORK, "s4.png"), "20 家公司 · 两个基线", "裸模型 5% · RAG 22%")
    seg(os.path.join(WORK, "s4.png"), 8, "seg4")

    card(os.path.join(WORK, "s5.png"), "留出集 31% → 40%", "关注点只从 8 家学到，10 家没见过的公司上验证")
    seg(os.path.join(WORK, "s5.png"), 7, "seg5")

    card(os.path.join(WORK, "s6.png"), "问询函预演", "每条结论都指向年报原文页码", True)
    seg(os.path.join(WORK, "s6.png"), 4, "seg6")

    with open(os.path.join(WORK, "list.txt"), "w", encoding="utf-8") as f:
        for s in segs:
            f.write("file '%s'\n" % os.path.basename(s))
    run([FF, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "list.txt",
         "-c", "copy", os.path.basename(OUT)], cwd=WORK)
    shutil.move(os.path.join(WORK, os.path.basename(OUT)), OUT)
    print("[demo]", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
