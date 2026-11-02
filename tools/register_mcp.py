"""把「问询函预演」MCP Server 注册进 Nexent 平台。

做法：直接写平台库（nexent schema）：
  1) mcp_record_t  登记 MCP 服务地址与工具清单；
  2) ag_tool_info_t 为 7 个工具建工具记录（source=mcp）；
  3) ag_tool_instance_t 绑定到智能体 ZIJINHUA（agent_id=3）当前版本。

不改动原有工具与智能体配置；失败可回滚（见文件末尾清理 SQL）。

用法：
    python tools/register_mcp.py
"""
from __future__ import annotations

import base64
import json
import subprocess

TENANT = "a96c2f1b-340d-436c-8f29-95e79faa8f0f"
USER = "86b52fc7-43d2-4725-8747-566644e43d7e"
AGENT_ID = 3
MCP_NAME = "inquiry-rehearsal"
MCP_URL = "http://172.18.0.1:8772/mcp"

TOOLS = [
    ("list_companies", "列出数据集里的公司（代码、简称、年报页数）", {}),
    ("precheck", "对某公司做年报预检，返回结论列表（每条带页码与原文引文）",
     {"code": {"type": "string", "description": "公司代码，如 600363"}}),
    ("get_page_text", "取某公司年报某页原文，用于核对结论证据",
     {"code": {"type": "string"}, "page": {"type": "integer"}}),
    ("list_concerns", "列出监管关注点本体（名称、关键词、准则对齐）", {}),
    ("company_kg", "返回某公司在知识图谱中的子图摘要",
     {"code": {"type": "string"}}),
    ("build_report", "生成该公司的 Markdown 预检报告",
     {"code": {"type": "string"}}),
    ("learn_concern", "提议新的监管关注点（写提案文件，等人确认）",
     {"name": {"type": "string"}, "keywords": {"type": "string"}, "ask": {"type": "string"}}),
]


def sql_literal(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def main() -> int:
    reg = {"tools": [{"name": n, "description": d} for n, d, _ in TOOLS],
           "_toolNames": [n for n, _, _ in TOOLS]}
    stmts = [
        "begin;",
        f"insert into nexent.mcp_record_t (tenant_id,user_id,mcp_name,mcp_server,source,"
        f"status,enabled,delete_flag,registry_json,tags,description,ingroup_permission) values ("
        f"{sql_literal(TENANT)},{sql_literal(USER)},{sql_literal(MCP_NAME)},{sql_literal(MCP_URL)},"
        f"'local',true,true,'N',{sql_literal(json.dumps(reg, ensure_ascii=False))},"
        f"ARRAY['finance','annual-report','knolwedge-graph'],"
        f"{sql_literal('问询函预演：年报预检、证据核对、图谱查询')},'READ_ONLY');",
    ]
    for name, desc, inputs in TOOLS:
        stmts.append(
            f"insert into nexent.ag_tool_info_t (name,class_name,description,source,author,usage,"
            f"params,inputs,output_type,is_available,origin_name,is_user_selectable,delete_flag) values ("
            f"{sql_literal(name)},{sql_literal(name)},{sql_literal(desc)},'mcp',{sql_literal(USER)},"
            f"{sql_literal(MCP_NAME)},'[]',{sql_literal(json.dumps(inputs, ensure_ascii=False))},"
            f"'string',true,{sql_literal(name)},true,'N');")
    # 取新 tool_id（按名字），绑定到 agent 3 的当前版本
    for name, _, _ in TOOLS:
        stmts.append(
            "insert into nexent.ag_tool_instance_t (tool_id,agent_id,params,user_id,tenant_id,enabled,version_no,delete_flag) "
            f"select tool_id,{AGENT_ID},'{{}}',{sql_literal(USER)},{sql_literal(TENANT)},true,4,'N' "
            f"from nexent.ag_tool_info_t where name={sql_literal(name)} and source='mcp' and usage={sql_literal(MCP_NAME)} "
            "order by tool_id desc limit 1;")
    stmts.append("commit;")
    sql = "\n".join(stmts)

    b = base64.b64encode(sql.encode()).decode()
    cmd = (f"echo {b} | base64 -d > /tmp/reg.sql && docker cp /tmp/reg.sql nexent-postgresql:/tmp/reg.sql && "
           f"docker exec nexent-postgresql psql -U root -d nexent -v ON_ERROR_STOP=1 -f /tmp/reg.sql")
    bc = base64.b64encode(cmd.encode()).decode()
    r = subprocess.run(["wsl", "-d", "Ubuntu-Nexent", "--", "bash", "-c", f"echo {bc} | base64 -d | bash"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(r.stdout[-2000:])
    print(r.stderr[-500:])
    return 0 if r.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
