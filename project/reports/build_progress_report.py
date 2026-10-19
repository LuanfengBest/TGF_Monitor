"""Render the one-page course report from its editable Markdown source.

Requires reportlab and pypdf. Run from any directory; no model calls.
"""
import hashlib
import json
from pathlib import Path
import re
from xml.sax.saxutils import escape

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(__file__).with_name("progress_report_2026-10-21.md")
PDF = ROOT / "output/pdf/progress_report_2026-10-21.pdf"


def inline(text):
    text = escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    return re.sub(r"\[([^\]]+)\]\((https://[^)]+)\)",
                  r'<link href="\2" color="#153b5b"><u>\1</u></link>', text)


def main():
    raw = SOURCE.read_text(encoding="utf-8")
    assert not any(char in raw for char in "\u2010\u2011\u2012\u2013\u2014")
    PDF.parent.mkdir(parents=True, exist_ok=True)
    text = ParagraphStyle("body", fontName="Times-Roman", fontSize=11, leading=12.6,
                          spaceAfter=6.0, textColor=colors.HexColor("#17212b"), alignment=TA_LEFT)
    title = ParagraphStyle("title", parent=text, fontName="Times-Bold", fontSize=16,
                           leading=18, spaceAfter=6, textColor=colors.HexColor("#153b5b"), alignment=TA_CENTER)
    authors = ParagraphStyle("authors", parent=text, fontSize=10.3, leading=12, spaceAfter=3, alignment=TA_CENTER)
    meta = ParagraphStyle("meta", parent=text, fontName="Helvetica", fontSize=8.2,
                          leading=10, spaceAfter=11, alignment=TA_CENTER, textColor=colors.HexColor("#4c5964"))
    cell = ParagraphStyle("cell", parent=text, fontName="Helvetica", fontSize=9.0, leading=11, spaceAfter=0)
    cell_head = ParagraphStyle("cellhead", parent=cell, fontName="Helvetica-Bold", fontSize=8.6)
    blocks = raw.strip().split("\n\n")
    story = []
    for index, block in enumerate(blocks):
        if block.startswith("# "):
            story.append(Paragraph(inline(block[2:]), title))
        elif index == 1:
            story.append(Paragraph(inline(block), authors))
        elif index == 2:
            story.append(Paragraph(inline(block), meta))
        elif block.startswith("|"):
            rows = [line for line in block.splitlines() if not re.fullmatch(r"[| :\-]+", line)]
            table = Table([[Paragraph(inline(v.strip()), cell_head if i == 0 else cell)
                            for v in line.strip("|").split("|")] for i, line in enumerate(rows)],
                          colWidths=[204, 156, 156], hAlign="LEFT")
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#edf2f6")),
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#8b9aa7")),
                ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.HexColor("#bac4cd")),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]))
            story.extend([table, Spacer(1, 7)])
        else:
            story.append(Paragraph(inline(block), text))
    doc = SimpleDocTemplate(str(PDF), pagesize=letter, rightMargin=42, leftMargin=42,
                            topMargin=34, bottomMargin=34, title="TGF Progress Report - October 21, 2026",
                            author="Pacifica Zhang, Luanfeng Wei, Qier An, Tony Zhu",
                            subject="CPSC 4880/5880; evidence through October 19, 2026")
    doc.build(story)
    reader = PdfReader(PDF)
    if len(reader.pages) != 1:
        raise ValueError(f"Course limit is one page; generated {len(reader.pages)}")
    plain = reader.pages[0].extract_text()
    for required in ["Pacifica Zhang (rz377)", "Luanfeng Wei (lw856)", "Qier An (qa24)", "Tony Zhu (jz965)",
                     "23/24", "20/24", "2/40", "0/40", "1.70", "3,817", "38P/21N/5unknown", "November 30"]:
        assert required in plain, required
    links = [a.get_object().get("/A", {}).get("/URI") for a in reader.pages[0].get("/Annots", [])]
    assert "https://github.com/LuanfengBest/TGF_Monitor" in links
    print(json.dumps({"pages": 1, "source_words_approx": len(raw.split()), "pdf_bytes": PDF.stat().st_size,
                      "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                      "pdf_sha256": hashlib.sha256(PDF.read_bytes()).hexdigest(),
                      "author_and_claim_text_checks": "passed", "repository_link": "verified",
                      "visual_review": "pending"}, indent=2))


if __name__ == "__main__":
    main()
