"""问询函预演 MCP Server：把检测结果、证据、图谱暴露成工具。

工具（7 个）：
  list_companies()                  列出 20 家公司
  precheck(code)                    该公司的预检结论（问题 + 页码 + 原文）
  get_page_text(code, page)         取年报某页原文（证据核对）
  list_concerns()                   监管关注点本体（含准则对齐）
  company_kg(code)                  该公司的图谱子图摘要
  build_report(code)                生成 Markdown 预检报告
  learn_concern(name, keywords, ask) 提议新关注点（写提案文件，等人确认）

运行：
    .venv-nexent311\Scripts\python.exe mcp_server.py
"""
from __future__ import annotations

import json
import os
import re

from fastmcp import FastMCP

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
mcp = FastMCP(name="inquiry-rehearsal",
              instructions="问询函预演：输入公司代码，返回年报预检结论（带页码与原文）；只基于年报原文，不编造。")


def _load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


def _companies():
    return {x["code"]: x for x in _load("dataset.json")["items"]}


@mcp.tool
def list_companies() -> str:
    """列出数据集里的公司（代码、简称、年报页数）。"""
    items = _load("dataset.json")["items"]
    return "\n".join(f"{x['code']} {x['name']} {x.get('report_pages')}页" for x in items)


@mcp.tool
def precheck(code: str) -> str:
    """对某公司做年报预检，返回结论列表（每条带页码与原文引文）。"""
    p = os.path.join(DATA, "llm", f"{code}.json")
    if not os.path.exists(p):
        return f"没有 {code} 的预检结果"
    d = json.load(open(p, encoding="utf-8"))
    if not d["flags"]:
        return f"{d['name']}：预检未发现问题"
    lines = [f"{d['name']}：{len(d['flags'])} 条"]
    for i, f in enumerate(d["flags"], 1):
        lines.append(f"{i}. [{f.get('topic')}] {f.get('issue')}（第 {f.get('page')} 页）")
        lines.append(f"   原文：{(f.get('quote') or '')[:80]}")
    return "\n".join(lines)


@mcp.tool
def get_page_text(code: str, page: int) -> str:
    """取某公司年报第 page 页的原文（用于核对结论的证据）。"""
    items = _companies()
    it = items.get(code)
    if not it:
        return f"没有 {code}"
    text = open(os.path.join(ROOT, it["dir"], "report.txt"), encoding="utf-8").read()
    parts = re.split(r"=== 第 (\d+) 页 ===", text)
    for i in range(1, len(parts), 2):
        if int(parts[i]) == page:
            return re.sub(r"\s+", " ", parts[i + 1])[:1200]
    return f"{code} 没有第 {page} 页"


@mcp.tool
def list_concerns() -> str:
    """列出监管关注点本体（名称、检索关键词、准则对齐）。"""
    kg = _load("kg.json")
    rows = [n for n in kg["nodes"] if n["type"] == "Concern"]
    return "\n".join(f"{n['label']}｜{n['props'].get('standard')}｜{','.join(n['props'].get('keywords', [])[:4])}"
                     for n in rows)


@mcp.tool
def company_kg(code: str) -> str:
    """返回某公司在知识图谱中的子图摘要（年报、结论数、涉及关注点）。"""
    kg = _load("kg.json")
    flags = [n for n in kg["nodes"] if n["type"] == "Flag" and n["id"].startswith(f"flag:{code}:")]
    concerns = set()
    for e in kg["edges"]:
        if e["source"].startswith(f"flag:{code}:") and e["relation"] == "属于":
            concerns.add(e["target"].split(":", 1)[1])
    name = next((n["label"] for n in kg["nodes"] if n["id"] == f"company:{code}"), code)
    return f"{name}：结论 {len(flags)} 条，涉及关注点：{'、'.join(sorted(concerns)) or '无'}"


@mcp.tool
def build_report(code: str) -> str:
    """生成该公司的 Markdown 预检报告（结论 + 页码 + 原文，末尾附免责声明）。"""
    p = os.path.join(DATA, "llm", f"{code}.json")
    if not os.path.exists(p):
        return f"没有 {code} 的预检结果"
    d = json.load(open(p, encoding="utf-8"))
    lines = [f"# {d['name']}（{code}）年报预检", ""]
    for f in d["flags"]:
        lines.append(f"- **[{f.get('topic')}]** {f.get('issue')}（第 {f.get('page')} 页）")
        lines.append(f"  > {(f.get('quote') or '')[:100]}")
    lines += ["", "仅基于年报原文与公开数字，不构成投资建议。"]
    return "\n".join(lines)


@mcp.tool
def learn_concern(name: str, keywords: str, ask: str) -> str:
    """提议一个新的监管关注点（写提案文件，等人确认后才入库）。"""
    path = os.path.join(DATA, "concern_proposals.json")
    items = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else []
    items.append({"name": name, "keywords": [k.strip() for k in keywords.split(",") if k.strip()],
                  "ask": ask, "status": "pending"})
    json.dump(items, open(path, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
    return f"已记录提案：{name}（待人工确认，当前共 {len(items)} 条）"


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8772, show_banner=False)
