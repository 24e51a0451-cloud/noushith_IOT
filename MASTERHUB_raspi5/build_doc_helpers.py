"""
Script to generate the comprehensive 20+ page academic and technical research document
for the MasterHub BCI JioSaavn Remote Companion system.
Outputs a beautifully styled Microsoft Word (.docx) document with embedded high-resolution
UI mockups, architectural charts, sequence workflows, latency waterfalls, and comprehensive tables.
"""

import os
import sys
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

def set_cell_background(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(f'<w:tcMar {nsdecls("w")}>'
                      f'<w:top w:w="{top}" w:type="dxa"/>'
                      f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
                      f'<w:left w:w="{left}" w:type="dxa"/>'
                      f'<w:right w:w="{right}" w:type="dxa"/>'
                      f'</w:tcMar>')
    tcPr.append(tcMar)

def set_cell_border_left(cell, color_hex="1E3A8A", sz="36"):
    tcPr = cell._tc.get_or_add_tcPr()
    borders = parse_xml(f'<w:tcBorders {nsdecls("w")}>'
                        f'<w:left w:val="single" w:sz="{sz}" w:space="0" w:color="{color_hex}"/>'
                        f'<w:top w:val="none"/>'
                        f'<w:right w:val="none"/>'
                        f'<w:bottom w:val="none"/>'
                        f'</w:tcBorders>')
    tcPr.append(borders)

def add_header_footer(doc):
    for s in doc.sections:
        s.top_margin = Inches(1.0)
        s.bottom_margin = Inches(1.0)
        s.left_margin = Inches(1.0)
        s.right_margin = Inches(1.0)
        
        # Header
        hdr = s.header
        hp = hdr.paragraphs[0]
        hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        hrun = hp.add_run("MasterHub IoT & Neural Interface Research | BCI JioSaavn Companion Protocol")
        hrun.font.name = "Calibri"
        hrun.font.size = Pt(8.5)
        hrun.font.color.rgb = RGBColor(120, 144, 156)
        
        # Footer
        ftr = s.footer
        fp = ftr.paragraphs[0]
        fp.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        frun_l = fp.add_run("CONFIDENTIAL & PROPRIETARY — GALATICX ECOSYSTEM\t\t")
        frun_l.font.name = "Calibri"
        frun_l.font.size = Pt(8.5)
        frun_l.font.color.rgb = RGBColor(140, 150, 160)
        
        frun_r = fp.add_run("Technical Specification v1.0.4")
        frun_r.font.name = "Calibri"
        frun_r.font.size = Pt(8.5)
        frun_r.font.color.rgb = RGBColor(140, 150, 160)

def add_callout(doc, title, text, box_type="info"):
    colors = {
        "info": ("EFF6FF", "2563EB", RGBColor(30, 58, 138)),
        "warning": ("FEFCE8", "CA8A04", RGBColor(133, 77, 14)),
        "tip": ("F0FDF4", "16A34A", RGBColor(22, 101, 52)),
        "alert": ("FEF2F2", "DC2626", RGBColor(153, 27, 27))
    }
    bg, border_col, title_col = colors.get(box_type, colors["info"])
    
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    tbl.columns[0].width = Inches(6.5)
    
    cell = tbl.cell(0, 0)
    set_cell_background(cell, bg)
    set_cell_border_left(cell, border_col, sz="36")
    set_cell_margins(cell, top=140, bottom=140, left=200, right=180)
    
    cp = cell.paragraphs[0]
    cp.paragraph_format.space_before = Pt(2)
    cp.paragraph_format.space_after = Pt(4)
    run_t = cp.add_run(f"✦  {title.upper()}\n")
    run_t.font.name = "Arial"
    run_t.font.size = Pt(10)
    run_t.font.bold = True
    run_t.font.color.rgb = title_col
    
    run_b = cp.add_run(text)
    run_b.font.name = "Calibri"
    run_b.font.size = Pt(9.5)
    run_b.font.color.rgb = RGBColor(51, 65, 85)
    
    # spacing after table
    sp = doc.add_paragraph()
    sp.paragraph_format.space_before = Pt(0)
    sp.paragraph_format.space_after = Pt(6)

def add_code_block(doc, code_str, language=""):
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    tbl.columns[0].width = Inches(6.5)
    
    cell = tbl.cell(0, 0)
    set_cell_background(cell, "F8FAFC")
    set_cell_border_left(cell, "64748B", sz="24")
    set_cell_margins(cell, top=100, bottom=100, left=140, right=120)
    
    cp = cell.paragraphs[0]
    cp.paragraph_format.space_before = Pt(0)
    cp.paragraph_format.space_after = Pt(0)
    cp.paragraph_format.line_spacing = 1.05
    
    run = cp.add_run(code_str.strip())
    run.font.name = "Consolas"
    run.font.size = Pt(8.5)
    run.font.color.rgb = RGBColor(15, 23, 42)
    
    sp = doc.add_paragraph()
    sp.paragraph_format.space_before = Pt(0)
    sp.paragraph_format.space_after = Pt(6)

def create_styled_table(doc, col_widths, headers, data):
    tbl = doc.add_table(rows=len(data) + 1, cols=len(headers))
    style_table(tbl, col_widths, headers, data)
    sp = doc.add_paragraph()
    sp.paragraph_format.space_before = Pt(0)
    sp.paragraph_format.space_after = Pt(6)
    return tbl

def style_table(tbl, col_widths, headers, data):
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    
    # Header row
    hdr_row = tbl.rows[0]
    for idx, name in enumerate(headers):
        cell = hdr_row.cells[idx]
        cell.width = Inches(col_widths[idx])
        set_cell_background(cell, "1E3A8A")
        set_cell_margins(cell, top=120, bottom=120, left=140, right=140)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(2)
        run = p.add_run(name)
        run.font.name = "Arial"
        run.font.size = Pt(9.5)
        run.font.bold = True
        run.font.color.rgb = RGBColor(255, 255, 255)
        
    # Data rows
    for r_idx, row_data in enumerate(data):
        row = tbl.rows[r_idx + 1]
        bg_col = "FFFFFF" if r_idx % 2 == 0 else "F8FAFC"
        for c_idx, val in enumerate(row_data):
            cell = row.cells[c_idx]
            cell.width = Inches(col_widths[c_idx])
            set_cell_background(cell, bg_col)
            set_cell_margins(cell, top=100, bottom=100, left=130, right=130)
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.line_spacing = 1.05
            run = p.add_run(str(val))
            run.font.name = "Calibri"
            run.font.size = Pt(9)
            run.font.color.rgb = RGBColor(30, 41, 59)
            if c_idx == 0:
                run.font.bold = True

def add_figure(doc, img_path, caption, width_in=5.5):
    if not os.path.exists(img_path):
        print(f"Warning: image path does not exist: {img_path}")
        return
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run()
    run.add_picture(img_path, width=Inches(width_in))
    
    cp = doc.add_paragraph()
    cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cp.paragraph_format.space_before = Pt(2)
    cp.paragraph_format.space_after = Pt(12)
    crun = cp.add_run(caption)
    crun.font.name = "Calibri"
    crun.font.size = Pt(9)
    crun.font.italic = True
    crun.font.bold = True
    crun.font.color.rgb = RGBColor(71, 85, 105)

print("Helper functions compiled successfully.")
