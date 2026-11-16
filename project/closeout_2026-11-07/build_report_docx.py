"""Build the editable course report from the reviewed Markdown manuscript."""
from pathlib import Path
import re
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT

HERE=Path(__file__).resolve().parent
OUT=HERE/'deliverables'
OUT.mkdir(exist_ok=True)
doc=Document()
section=doc.sections[0]
section.page_width=Inches(8.5);section.page_height=Inches(11)
section.top_margin=Inches(.68);section.bottom_margin=Inches(.68)
section.left_margin=Inches(.75);section.right_margin=Inches(.75)
section.footer_distance=Inches(.30)
for name in ('Normal','Title','Subtitle','Heading 1','Heading 2','Heading 3','List Bullet'):
    style=doc.styles[name];style.font.name='Arial';style.font.color.rgb=RGBColor(0,0,0)
    style.font.size=Pt(10.5)
    style.paragraph_format.space_after=Pt(5)
    style.paragraph_format.line_spacing=1.10
    for border in style.element.xpath('./w:pPr/w:pBdr'):
        border.getparent().remove(border)
doc.styles['Title'].font.size=Pt(24);doc.styles['Title'].font.bold=True
doc.styles['Title'].paragraph_format.space_after=Pt(8)
doc.styles['Subtitle'].font.size=Pt(13)
for name,size in [('Heading 1',15),('Heading 2',12),('Heading 3',11)]:
    st=doc.styles[name];st.font.size=Pt(size);st.font.bold=True
    st.paragraph_format.space_before=Pt(13);st.paragraph_format.space_after=Pt(6)
    st.paragraph_format.keep_with_next=True
footer=section.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.RIGHT
run=footer.add_run();run.font.size=Pt(9)
field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');run._r.addnext(field)

def hyperlink(p,label,target):
    if not re.match(r'https?://',target):target=(HERE/target).resolve().as_uri()
    h=OxmlElement('w:hyperlink');h.set(qn('r:id'),p.part.relate_to(target,RT.HYPERLINK,is_external=True))
    r=OxmlElement('w:r');pr=OxmlElement('w:rPr')
    color=OxmlElement('w:color');color.set(qn('w:val'),'244F72');pr.append(color)
    u=OxmlElement('w:u');u.set(qn('w:val'),'single');pr.append(u);r.append(pr)
    t=OxmlElement('w:t');t.text=label;r.append(t);h.append(r);p._p.append(h)

def inline(p,s):
    # Only the Markdown forms present in the reviewed source are interpreted.
    for chunk in re.split(r'(\[[^\]]+\]\([^)]+\)|\*\*[^*]+\*\*|`[^`]+`)',s):
        if not chunk:continue
        m=re.fullmatch(r'\[([^\]]+)\]\(([^)]+)\)',chunk)
        if m:hyperlink(p,m[1],m[2])
        elif chunk.startswith('**'):
            r=p.add_run(chunk[2:-2]);r.bold=True
        elif chunk.startswith('`'):
            r=p.add_run(chunk[1:-1]);r.font.name='DejaVu Sans Mono';r.font.size=Pt(8.5)
        else:p.add_run(chunk)

def table(lines):
    rows=[[x.strip() for x in l.strip().strip('|').split('|')] for l in lines]
    rows=[r for r in rows if not all(re.fullmatch(r':?-+:?',x) for x in r)]
    cols=len(rows[0]);t=doc.add_table(rows=len(rows), cols=cols);t.alignment=WD_TABLE_ALIGNMENT.CENTER
    t.autofit=False
    if cols==5:widths=[2.55,1.18,.68,1.40,.89]
    elif cols==4:widths=[3.10,1.25,1.25,1.10]
    else:widths=[1.55,2.55,2.60]
    assert abs(sum(widths)-6.7)<.01
    for i,w in enumerate(widths):t.columns[i].width=Inches(w)
    for ri,row in enumerate(rows):
        for ci,value in enumerate(row):
            cell=t.cell(ri,ci);cell.width=Inches(widths[ci]);cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            props=cell._tc.get_or_add_tcPr()
            shade=OxmlElement('w:shd');shade.set(qn('w:fill'),'DCE7F0' if ri==0 else ('F6F8FA' if ri%2==0 else 'FFFFFF'));props.append(shade)
            margins=OxmlElement('w:tcMar')
            for side in ('top','left','bottom','right'):
                el=OxmlElement('w:'+side);el.set(qn('w:w'),'90' if side in ('top','bottom') else '100');el.set(qn('w:type'),'dxa');margins.append(el)
            props.append(margins)
            borders=OxmlElement('w:tcBorders')
            for side in ('top','left','bottom','right'):
                b=OxmlElement('w:'+side);b.set(qn('w:val'),'single');b.set(qn('w:sz'),'4');b.set(qn('w:color'),'D9D9D9');borders.append(b)
            props.append(borders)
            p=cell.paragraphs[0];p.paragraph_format.space_after=Pt(0);p.paragraph_format.line_spacing=1.05
            p.paragraph_format.keep_with_next=ri<len(rows)-1
            if ci>0 and cols>=4:p.alignment=WD_ALIGN_PARAGRAPH.CENTER
            inline(p,value)
            for r in p.runs:r.font.size=Pt(9.4);r.bold=ri==0
        trpr=t.rows[ri]._tr.get_or_add_trPr()
        no_split=OxmlElement('w:cantSplit');trpr.append(no_split)
        if ri==0:
            repeat=OxmlElement('w:tblHeader');trpr.append(repeat)
    doc.add_paragraph().paragraph_format.space_after=Pt(1)

lines=(HERE/'FINAL_REPORT.md').read_text().splitlines();i=0
while i<len(lines):
    line=lines[i].strip()
    if not line:i+=1;continue
    if line.startswith('|'):
        ts=[]
        while i<len(lines) and lines[i].strip().startswith('|'):ts.append(lines[i]);i+=1
        table(ts);continue
    if line.startswith('# '):
        inline(doc.add_paragraph(style='Title'),line[2:])
    elif line.startswith('## '):inline(doc.add_paragraph(style='Heading 1'),line[3:])
    elif line.startswith('### '):inline(doc.add_paragraph(style='Heading 2'),line[4:])
    elif line.startswith('- '):inline(doc.add_paragraph(style='List Bullet'),line[2:])
    elif line.startswith('Development Comparisons'):inline(doc.add_paragraph(style='Subtitle'),line)
    else:inline(doc.add_paragraph(),line)
    i+=1
doc.core_properties.title='Trace Grounded Follow Up for Agent Monitoring'
doc.core_properties.subject='Development comparisons and evidence use diagnostics'
doc.core_properties.author='TGF project team'
doc.core_properties.keywords='TGF, authorization, monitoring, controlled diagnostics'
for p in doc.paragraphs:
    for border in p._p.xpath('./w:pPr/w:pBdr'):
        border.getparent().remove(border)
doc.save(OUT/'TGF_Report.docx')
print(OUT/'TGF_Report.docx')
