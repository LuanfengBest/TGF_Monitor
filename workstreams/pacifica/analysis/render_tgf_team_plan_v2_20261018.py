"""Render the shareable plan; no research inputs or outputs are modified."""
from pathlib import Path
import re
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs/tgf_experiment_plan_team_v2_2026-10-18.md'
OUTPUT = ROOT / 'output/pdf/TGF_experiment_plan_v2_2026-10-18.pdf'
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
pdfmetrics.registerFont(TTFont('CJK', '/System/Library/Fonts/Supplemental/Arial Unicode.ttf'))
pdfmetrics.registerFontFamily('CJK', normal='CJK', bold='CJK', italic='CJK', boldItalic='CJK')
ink, teal, light, gray = [colors.HexColor(x) for x in ('#182C3C', '#166C76', '#EDF5F5', '#52606A')]
styles = {
    'body': ParagraphStyle('body', fontName='CJK', fontSize=10.1, leading=15.2, textColor=ink, wordWrap='CJK', spaceAfter=6),
    'title': ParagraphStyle('title', fontName='CJK', fontSize=21, leading=30, textColor=ink, wordWrap='CJK', spaceAfter=14),
    'heading': ParagraphStyle('heading', fontName='CJK', fontSize=13.2, leading=21, textColor=teal, wordWrap='CJK', spaceBefore=11, spaceAfter=7, keepWithNext=True),
    'cell': ParagraphStyle('cell', fontName='CJK', fontSize=9, leading=13.5, textColor=ink, wordWrap='CJK', spaceAfter=0),
    'headcell': ParagraphStyle('headcell', fontName='CJK', fontSize=9.1, leading=13.5, textColor=teal, wordWrap='CJK', spaceAfter=0),
    'bullet': ParagraphStyle('bullet', fontName='CJK', fontSize=10.1, leading=15.2, textColor=ink, wordWrap='CJK', leftIndent=9, firstLineIndent=-9, spaceAfter=5),
}

def markup(text):
    text = escape(text)
    text = re.sub(r'\*\*(.*?)\*\*', r'<font color="#166C76">\1</font>', text)
    text = re.sub(r'`([^`]+)`', r'<font color="#345B73">\1</font>', text)
    return text

def p(text, sty='body'):
    return Paragraph(markup(text), styles[sty])

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.saved_pages = []
    def showPage(self):
        self.saved_pages.append(dict(self.__dict__))
        self._startPage()
    def save(self):
        count = len(self.saved_pages)
        for state in self.saved_pages:
            self.__dict__.update(state)
            self.setStrokeColor(colors.HexColor('#D5E1E5'))
            self.line(42, A4[1]-33, A4[0]-42, A4[1]-33)
            self.setFont('CJK', 8)
            self.setFillColor(gray)
            self.drawString(42, A4[1]-24, 'TGF | 组内实验方案 v2 | 2026-10-18')
            self.drawString(42, 23, 'AI审核非人工金标 · 研究计划未执行')
            self.drawRightString(A4[0]-42, 23, f'{self._pageNumber} / {count}')
            super().showPage()
        super().save()

width = A4[0]-84
flow=[]
lines=SOURCE.read_text().splitlines()
i=0
while i<len(lines):
    line=lines[i].strip()
    if not line:
        i+=1; continue
    if line.startswith('|'):
        rows=[]
        while i<len(lines) and lines[i].strip().startswith('|'):
            cells=[v.strip() for v in lines[i].strip().strip('|').split('|')]
            if not all(re.fullmatch(r':?-+:?', c) for c in cells):
                rows.append(cells)
            i+=1
        n=len(rows[0])
        if n==7: proportions=[.095,.12,.075,.075,.13,.18,.325]
        elif n==2: proportions=[.16,.84]
        elif n==3 and rows[0][0]=='环境': proportions=[.10,.27,.63]
        elif n==3: proportions=[.20,.60,.20]
        elif n==4: proportions=[.12,.32,.23,.33]
        else: proportions=[1/n]*n
        table=Table([[p(c,'headcell' if r==0 else 'cell') for c in row] for r,row in enumerate(rows)], colWidths=[width*x for x in proportions], repeatRows=1, hAlign='LEFT')
        table.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),light),('VALIGN',(0,0),(-1,-1),'TOP'),
            ('LINEBELOW',(0,0),(-1,0),.7,teal),('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#D8E2E6')),
            ('LEFTPADDING',(0,0),(-1,-1),5.5),('RIGHTPADDING',(0,0),(-1,-1),5.5),
            ('TOPPADDING',(0,0),(-1,-1),5.5),('BOTTOMPADDING',(0,0),(-1,-1),5.5),
        ]))
        flow += [table,Spacer(1,9)]
        continue
    if line.startswith('# '): flow.append(p(line[2:],'title'))
    elif line.startswith('## '): flow.append(p(line[3:],'heading'))
    elif line.startswith('- '): flow.append(p('• '+line[2:],'bullet'))
    else: flow.append(p(line))
    i+=1

doc=SimpleDocTemplate(str(OUTPUT), pagesize=A4, rightMargin=42,leftMargin=42,topMargin=47,bottomMargin=42, title='TGF 下一步实验计划 v2', author='Codex, prepared at Ruoyang Zhang’s request')
doc.build(flow,canvasmaker=NumberedCanvas)
print(OUTPUT)
