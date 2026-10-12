#!/usr/bin/env python3
"""Сборка PDF/PNG из единого Markdown-источника; запуск из любой директории."""
from pathlib import Path
import re, json, hashlib, importlib.metadata
from xml.sax.saxutils import escape
import fitz
from fontTools.ttLib import TTFont as FontFile
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether

ROOT = Path(__file__).resolve().parents[1]
TEXT = (ROOT/'docs/case-study-ru.md').read_text(encoding='utf-8')
OUT = ROOT/'submission'
OUT.mkdir(exist_ok=True)
INK = colors.HexColor('#172B3A')
ACCENT = colors.HexColor('#19656C')
LIGHT = colors.HexColor('#EFF4F5')
MUTED = colors.HexColor('#52616C')
for weight in ('Regular','Bold'):
    fp = ROOT/f'assets/fonts/Inter-{weight}.ttf'
    cmap = FontFile(fp).getBestCmap()
    missing = sorted({c for c in TEXT if not c.isspace() and ord(c) not in cmap})
    if missing: raise ValueError(f'Непокрытые символы {weight}: {missing}')
    pdfmetrics.registerFont(TTFont('Inter'+weight,str(fp)))
pdfmetrics.registerFontFamily('InterRegular', normal='InterRegular',bold='InterBold',italic='InterRegular',boldItalic='InterBold')
styles = {
    'h1': ParagraphStyle('h1',fontName='InterBold',fontSize=20,leading=23,textColor=INK,spaceAfter=5),
    'h2': ParagraphStyle('h2',fontName='InterRegular',fontSize=11,leading=14,textColor=ACCENT,spaceAfter=10),
    'h3': ParagraphStyle('h3',fontName='InterBold',fontSize=10.7,leading=13,textColor=ACCENT,spaceBefore=9,spaceAfter=5,keepWithNext=True),
    'body': ParagraphStyle('body',fontName='InterRegular',fontSize=9.15,leading=12.5,textColor=INK,spaceAfter=6),
    'cell': ParagraphStyle('cell',fontName='InterRegular',fontSize=8.5,leading=11.4,textColor=INK),
    'th': ParagraphStyle('th',fontName='InterBold',fontSize=8.4,leading=11,textColor=INK),
}
def fmt(s):
    return re.sub(r'\*\*(.*?)\*\*',r'<b>\1</b>',escape(s))
def p(s, style='body'): return Paragraph(fmt(s),styles[style])
lines=TEXT.splitlines()
story=[]
i=0
while i<len(lines):
    s=lines[i].strip()
    if not s: i+=1; continue
    if s=='---': story.append(PageBreak()); i+=1; continue
    if s.startswith('|'):
        rows=[]
        while i<len(lines) and lines[i].strip().startswith('|'):
            cells=[v.strip() for v in lines[i].strip().strip('|').split('|')]
            if not all(re.fullmatch(r'[:\- ]+',v) for v in cells): rows.append(cells)
            i+=1
        data=[[p(v,'th' if j==0 else 'cell') for v in row] for j,row in enumerate(rows)]
        width=A4[0]-72
        widths=[width*.25,width*.34,width*.41] if 'Предлагаемое правило' in rows[0] else [width*.23,width*.45,width*.32]
        t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([
            ('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(-1,0),LIGHT),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F7F9FA')]),
            ('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),
            ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),
            ('LINEBELOW',(0,0),(-1,0),.7,ACCENT),
            ('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#DAE2E5')),
        ]))
        story.extend([t,Spacer(1,6)])
        continue
    for prefix,style in [('### ','h3'),('## ','h2'),('# ','h1')]:
        if s.startswith(prefix): story.append(p(s[len(prefix):],style));break
    else: story.append(p(s))
    i+=1

def footer(c,d):
    c.saveState()
    c.setStrokeColor(ACCENT);c.setLineWidth(1);c.line(36,A4[1]-25,A4[0]-36,A4[1]-25)
    c.setFont('InterRegular',7.4);c.setFillColor(MUTED)
    c.drawString(36,23,'PRODUCT MASTERS  /  SINOASIA B&R  /  УЧЕБНЫЙ КЕЙС')
    c.drawRightString(A4[0]-36,23,str(d.page))
    c.restoreState()
pdf=OUT/'RFM_Sinoasia_Case_RU.pdf'
doc=SimpleDocTemplate(str(pdf),pagesize=A4,leftMargin=36,rightMargin=36,topMargin=37,bottomMargin=37,
    title='RFM-анализ клиентской базы Sinoasia B&R',author='',subject='Учебный кейс: повторные продажи и удержание')
doc.build(story,onFirstPage=footer,onLaterPages=footer)
render=fitz.open(pdf)
assert len(render)==2,f'Ожидалось 2 страницы, получено {len(render)}'
plain='\n'.join(page.get_text() for page in render)
norm=lambda s: re.sub(r'\s+','',s)
expected=[]
for line in lines:
    s=line.strip()
    if not s or s=='---': continue
    if s.startswith('|'):
        cells=[v.strip() for v in s.strip('|').split('|')]
        if all(re.fullmatch(r'[:\- ]+',v) for v in cells): continue
        expected.extend(cells)
    else: expected.append(re.sub(r'^#{1,3} ','',s))
missing_text=[s for s in expected if norm(s.replace('**','')) not in norm(plain)]
assert not missing_text, f'Текст не совпадает: {missing_text}'
bounds=[]
for j,page in enumerate(render,1):
    assert abs(page.rect.width-A4[0])<.1 and abs(page.rect.height-A4[1])<.1
    for block in page.get_text('blocks'):
        x0,y0,x1,y1=block[:4]
        if x0<0 or y0<0 or x1>page.rect.width or y1>page.rect.height: bounds.append([j,*block[:4]])
    page.get_pixmap(matrix=fitz.Matrix(2,2),alpha=False).save(OUT/f'RFM_Sinoasia_Page_{j}.png')
assert not bounds,bounds
assert pdf.stat().st_size<25*1024*1024
v={'pages':len(render),'format':'A4','font_cmap':'все символы покрыты Inter Regular/Bold',
   'source_text_match':True,'blocks_outside_page':bounds,'pdf_bytes':pdf.stat().st_size,
   'pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),
   'versions':{k:importlib.metadata.version(k) for k in ['reportlab','PyMuPDF','fonttools']},
   'visual_review':'отдельная ручная проверка PNG необходима'}
(ROOT/'docs/render-validation.json').write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(v,ensure_ascii=False,indent=2))
