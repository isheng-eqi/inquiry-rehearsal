"""本地编排回放：模型选工具 → MCP 执行 → 模型作答。

明确说明：这不是 Nexent 平台对话，是本地用同一个 MCP 服务跑通的工具调用链路，
用于证明工具协议与判定逻辑可用；平台侧会话建立缺陷见文档附录 B。

用法：
    cd 问询函预演
    set DS_KEY=...
    python tools/agent_replay.py
输出：
    data/agent_replay.json
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

import requests
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = os.environ.get("MCP_URL", "http://127.0.0.1:8772/mcp")
KEY = os.environ.get("DS_KEY", "")
API = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"


def ask(messages, tools):
    body = {"model": MODEL, "messages": messages, "tools": tools, "temperature": 0, "max_tokens": 2000}
    r = requests.post(API, json=body, headers={"Authorization": "Bearer " + KEY}, timeout=180)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]


async def main() -> int:
    if not KEY:
        print("缺少 DS_KEY")
        return 1
    async with streamablehttp_client(URL) as (read, write, _):
        async with ClientSession(read, write) as s:
            await s.initialize()
            listed = await s.list_tools()
            tools = [{"type": "function", "function": {
                "name": t.name, "description": t.description or "",
                "parameters": t.inputSchema or {"type": "object", "properties": {}}}} for t in listed.tools]

            messages = [
                {"role": "system", "content": "你是年报预检助手。需要数据时必须调用工具，不要凭记忆回答；回答里保留页码与原文。"},
                {"role": "user", "content": "查一下 600363 联创光电的年报预检，列出前两条结论并给页码。"},
            ]
            transcript = []
            for _ in range(4):
                msg = ask(messages, tools)
                transcript.append({"role": "assistant", "content": msg.get("content"), "tool_calls": msg.get("tool_calls")})
                messages.append(msg)
                if not msg.get("tool_calls"):
                    break
                for tc in msg["tool_calls"]:
                    fn = tc["function"]["name"]
                    args = json.loads(tc["function"].get("arguments") or "{}")
                    res = await s.call_tool(fn, args)
                    text = "\n".join(c.text for c in res.content)
                    transcript.append({"role": "tool", "name": fn, "args": args, "result": text[:1500]})
                    messages.append({"role": "tool", "tool_call_id": tc["id"], "content": text[:6000]})

            out = {"url": URL, "model": MODEL, "transcript": transcript,
                   "final": next((t["content"] for t in reversed(transcript) if t.get("content")), "")}
            json.dump(out, open(os.path.join(ROOT, "data", "agent_replay.json"), "w", encoding="utf-8", newline="\n"),
                      ensure_ascii=False, indent=1)
            print("工具调用：", [t["name"] for t in transcript if t["role"] == "tool"])
            print("最终回答：", (out["final"] or "")[:400])
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
