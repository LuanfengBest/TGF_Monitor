"""Render the integrated manuscript; reads saved text only and calls no models."""
from pathlib import Path
import re
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT

HERE = Path(__file__).resolve().parent
OUT = HERE / 'deliverables'
OUT.mkdir(exist_ok=True)
doc = Document()
s = doc.sections[0]
s.page_width = Inches(8.5); s.page_height = Inches(11)
s.top_margin = Inches(.68); s.bottom_margin = Inches(.68)
s.left_margin = Inches(.75); s.right_margin = Inches(.75)
s.footer_distance = Inches(.30)
for name in ('Normal', 'Title', 'Subtitle', 'Heading 1', 'Heading 2', 'List Bullet'):
    st = doc.styles[name]
    st.font.name = 'Arial'; st.font.color.rgb = RGBColor(0, 0, 0)
    st.font.size = Pt(11)
    st.paragraph_format.space_after = Pt(6)
    st.paragraph_format.line_spacing = 1.10
    for border in st.element.xpath('./w:pPr/w:pBdr'):
        border.getparent().remove(border)
doc.styles['Title'].font.size = Pt(24)
doc.styles['Title'].font.bold = True
doc.styles['Subtitle'].font.size = Pt(13)
for name, size in [('Heading 1', 15), ('Heading 2', 12)]:
    st = doc.styles[name]; st.font.size = Pt(size); st.font.bold = True
    st.paragraph_format.space_before = Pt(13)
    st.paragraph_format.space_after = Pt(6)
    st.paragraph_format.keep_with_next = True
footer = s.footer.paragraphs[0]
footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
r = footer.add_run('Authorization auditing | '); r.font.size = Pt(9)
f = OxmlElement('w:fldSimple'); f.set(qn('w:instr'), 'PAGE'); footer._p.append(f)

def inline(p, text):
    for chunk in re.split(r'(\[[^\]]+\]\([^)]+\)|\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)', text):
        if not chunk: continue
        link = re.fullmatch(r'\[([^\]]+)\]\(([^)]+)\)', chunk)
        if link:
            target = link[2].strip('<>')
            if not target.startswith(('http://', 'https://')):
                rel = (HERE / target).resolve().relative_to(HERE.parents[1])
                target = 'https://github.com/LuanfengBest/TGF_Monitor/blob/pacifica/jev-research-update-2026-11-12/' + rel.as_posix()
            h = OxmlElement('w:hyperlink'); h.set(qn('r:id'), p.part.relate_to(target, RT.HYPERLINK, is_external=True))
            run = OxmlElement('w:r'); pr = OxmlElement('w:rPr')
            color = OxmlElement('w:color'); color.set(qn('w:val'), '244F72'); pr.append(color)
            u = OxmlElement('w:u'); u.set(qn('w:val'), 'single'); pr.append(u)
            run.append(pr); t = OxmlElement('w:t'); t.text = link[1]; run.append(t)
            h.append(run); p._p.append(h)
        elif chunk.startswith('**'):
            p.add_run(chunk[2:-2]).bold = True
        elif chunk.startswith('*'):
            p.add_run(chunk[1:-1]).italic = True
        elif chunk.startswith('`'):
            r = p.add_run(chunk[1:-1]); r.font.name = 'DejaVu Sans Mono'; r.font.size = Pt(9)
        else: p.add_run(chunk)

def add_table(lines):
    rows = [[c.strip() for c in x.strip().strip('|').split('|')] for x in lines]
    rows = [r for r in rows if not all(re.fullmatch(r':?-+:?', c) for c in r)]
    n = len(rows[0])
    if n == 2: widths = [1.30, 5.70]
    elif n == 3: widths = [1.48, 2.43, 3.09]
    elif n == 4: widths = [2.05, 1.45, 1.80, 1.70]
    elif n == 5: widths = [2.50, .96, 1.04, 1.04, 1.46]
    elif n == 6 and rows[0][0].startswith('Airline'): widths = [1.70, 1.0, 1.0, 1.0, 1.15, 1.15]
    elif n == 6: widths = [1.60, 1.04, 1.14, 1.07, 1.10, 1.05]
    else: raise ValueError(n)
    assert abs(sum(widths) - 7.0) < .001
    table = doc.add_table(rows=len(rows), cols=n)
    table.autofit = False; table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for ci, width in enumerate(widths): table.columns[ci].width = Inches(width)
    for ri, row in enumerate(rows):
        for ci, value in enumerate(row):
            cell = table.cell(ri, ci); cell.width = Inches(widths[ci])
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            pr = cell._tc.get_or_add_tcPr()
            shade = OxmlElement('w:shd'); shade.set(qn('w:fill'), 'DCE7F0' if ri == 0 else ('F6F8FA' if ri % 2 == 0 else 'FFFFFF')); pr.append(shade)
            mar = OxmlElement('w:tcMar')
            for side in ('top', 'bottom', 'left', 'right'):
                el = OxmlElement('w:' + side); el.set(qn('w:w'), '90' if side in ('top', 'bottom') else '100'); el.set(qn('w:type'), 'dxa'); mar.append(el)
            pr.append(mar)
            borders = OxmlElement('w:tcBorders')
            for side in ('top', 'bottom', 'left', 'right'):
                el = OxmlElement('w:' + side); el.set(qn('w:val'), 'single'); el.set(qn('w:sz'), '4'); el.set(qn('w:color'), 'D9D9D9'); borders.append(el)
            pr.append(borders)
            p = cell.paragraphs[0]; p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.05
            if n >= 4 and ci > 0: p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            inline(p, value)
            for r in p.runs: r.font.size = Pt(9.6); r.bold = ri == 0
        rp = table.rows[ri]._tr.get_or_add_trPr(); rp.append(OxmlElement('w:cantSplit'))
        if ri == 0: rp.append(OxmlElement('w:tblHeader'))
    doc.add_paragraph().paragraph_format.space_after = Pt(1)

lines = (HERE / 'FINAL_REPORT.md').read_text().splitlines()
i = 0
while i < len(lines):
    line = lines[i].strip()
    if not line: i += 1; continue
    if line.startswith('|'):
        block = []
        while i < len(lines) and lines[i].strip().startswith('|'): block.append(lines[i]); i += 1
        add_table(block); continue
    if line.startswith('# '): p = doc.add_paragraph(style='Title'); text = line[2:]
    elif line.startswith('## '): p = doc.add_paragraph(style='Heading 1'); text = line[3:]
    elif line.startswith('### '): p = doc.add_paragraph(style='Heading 2'); text = line[4:]
    elif line.startswith('- '): p = doc.add_paragraph(style='List Bullet'); text = line[2:]
    elif line.startswith('Judge choice and'): p = doc.add_paragraph(style='Subtitle'); text = line
    else: p = doc.add_paragraph(); text = line
    inline(p, text); i += 1
doc.core_properties.title = 'Authorization Auditing with Jev as Final Judge'
doc.core_properties.subject = 'Judge choice, follow-up questions and temporal permission'
doc.core_properties.author = 'TGF project team'
doc.core_properties.keywords = 'authorization, Jev, monitoring, TGF, negative results'
doc.save(OUT / 'Authorization_Auditing_Report.docx')
print(OUT / 'Authorization_Auditing_Report.docx')
