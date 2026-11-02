"""docx 排版后处理：表格行不跨页、表头跨页重复。

用法：
    python tools/fix_docx_layout.py submission/开发设计文档-问询函预演.docx
"""
from __future__ import annotations

import sys

import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


def main(path: str) -> int:
    d = docx.Document(path)
    for table in d.tables:
        for i, row in enumerate(table.rows):
            tr = row._tr
            trPr = tr.get_or_add_trPr()
            cant = OxmlElement("w:cantSplit")
            trPr.append(cant)
            if i == 0:
                hdr = OxmlElement("w:tblHeader")
                trPr.append(hdr)
    d.save(path)
    print(f"layout fixed: {len(d.tables)} tables")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
