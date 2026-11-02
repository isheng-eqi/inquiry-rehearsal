"""画一张知识图谱模式图（类与关系），用于文档第 3 章。

用法：
    cd 问询函预演
    python tools/draw_kg.py
输出：
    submission/screenshots/kg-schema.png
"""
from __future__ import annotations

import math
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "submission", "screenshots", "kg-schema.png")
FONT = r"C:\Windows\Fonts\msyh.ttc"
FONT_B = r"C:\Windows\Fonts\msyhbd.ttc"

W, H = 1500, 800
BG = (255, 255, 255)
INK = (28, 38, 58)
MUTED = (110, 125, 150)
BOX = (240, 246, 255)
EDGE = (90, 120, 190)
LINE = (120, 145, 190)

boxes = {
    "Company": (70, 330, 230, 430, "公司"),
    "Report": (330, 330, 470, 430, "年报"),
    "Flag": (570, 330, 710, 430, "结论"),
    "Evidence": (810, 330, 1080, 430, "证据（页码+原文）"),
    "Concern": (570, 110, 710, 210, "关注点"),
    "Standard": (850, 110, 1330, 210, "会计准则 / 监管指引"),
    "Question": (110, 580, 300, 680, "问询问题"),
}


def main() -> int:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(FONT, 26)
    fb = ImageFont.truetype(FONT_B, 30)
    fs = ImageFont.truetype(FONT, 22)

    d.text((90, 36), "知识图谱模式：类与关系", font=fb, fill=INK)
    d.text((90, 80), "节点 539（公司 20 / 年报 20 / 结论 171 / 证据 171 / 问题 143 / 关注点 14）   边 819",
           font=fs, fill=MUTED)

    for name, (x1, y1, x2, y2, label) in boxes.items():
        d.rounded_rectangle([x1, y1, x2, y2], radius=14, fill=BOX, outline=EDGE, width=2)
        lf = fs if len(label) > 8 else f
        tw = d.textlength(label, font=lf)
        d.text((x1 + (x2 - x1 - tw) / 2, y1 + (y2 - y1 - 34) / 2), label, font=lf, fill=INK)

    def arrow(p1, p2, label, offset=(0, -30)):
        d.line([p1, p2], fill=LINE, width=3)
        ang = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
        for s in (0.5, -0.5):
            d.line([p2, (p2[0] - 14 * math.cos(ang + s), p2[1] - 14 * math.sin(ang + s))], fill=LINE, width=3)
        tw = d.textlength(label, font=fs)
        mx = (p1[0] + p2[0]) / 2 - tw / 2 + offset[0]
        my = (p1[1] + p2[1]) / 2 + offset[1]
        d.rectangle([mx - 4, my - 2, mx + tw + 4, my + 30], fill=BG)
        d.text((mx, my), label, font=fs, fill=MUTED)

    arrow((230, 380), (330, 380), "发布")
    arrow((470, 380), (570, 380), "包含")
    arrow((710, 380), (810, 380), "依据")
    arrow((640, 330), (640, 210), "属于")
    arrow((710, 160), (850, 160), "对齐")
    arrow((150, 430), (150, 580), "被问询")

    d.text((560, 560), "说明：问询问题 —属于→ 关注点，为版面清晰未画线", font=fs, fill=MUTED)
    d.text((560, 600), "数据来源：20 家公司年报与问询函，全部公开披露", font=fs, fill=MUTED)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT)
    print(OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
