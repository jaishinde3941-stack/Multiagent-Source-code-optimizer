"""
evaluation/build_pdf.py — Generate CLI Command Reference PDF

Reads COMMANDS.md and produces a well-formatted PDF using ReportLab.
Usage:
    python evaluation/build_pdf.py
    python evaluation/build_pdf.py --out my_reference.pdf
"""

import argparse
import os
import re
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.flowables import KeepTogether

# ── Colour palette ─────────────────────────────────────────────────────────────
C_DARK    = colors.HexColor("#1a1a2e")   # deep navy — headings
C_ACCENT  = colors.HexColor("#0f3460")   # medium blue — sub-headings
C_CODE_BG = colors.HexColor("#f4f4f8")   # very light grey — code blocks
C_CODE_FG = colors.HexColor("#2d2d2d")   # near-black — code text
C_TABLE_H = colors.HexColor("#0f3460")   # table header bg
C_TABLE_A = colors.HexColor("#eef2ff")   # table alternating row
C_RULE    = colors.HexColor("#4361ee")   # horizontal rule
C_WHITE   = colors.white
C_GREY    = colors.HexColor("#666680")

W, H = A4


def _styles():
    base = getSampleStyleSheet()

    def add(name, **kw):
        base.add(ParagraphStyle(name=name, **kw))

    add("DocTitle",
        fontName="Helvetica-Bold", fontSize=22,
        textColor=C_DARK, spaceAfter=4, alignment=TA_CENTER)

    add("DocSubtitle",
        fontName="Helvetica", fontSize=11,
        textColor=C_GREY, spaceAfter=2, alignment=TA_CENTER)

    add("DocVersion",
        fontName="Helvetica-Oblique", fontSize=9,
        textColor=C_GREY, spaceAfter=16, alignment=TA_CENTER)

    add("H1",
        fontName="Helvetica-Bold", fontSize=14,
        textColor=C_WHITE, spaceAfter=4, spaceBefore=14,
        backColor=C_DARK, borderPad=5,
        leftIndent=0, rightIndent=0)

    add("H2",
        fontName="Helvetica-Bold", fontSize=11,
        textColor=C_ACCENT, spaceAfter=3, spaceBefore=10,
        leftIndent=0)

    add("H3",
        fontName="Helvetica-Bold", fontSize=10,
        textColor=C_DARK, spaceAfter=2, spaceBefore=7,
        leftIndent=0)

    add("Body",
        fontName="Helvetica", fontSize=9,
        textColor=C_DARK, spaceAfter=4,
        leading=13)

    add("MyCode",
        fontName="Courier", fontSize=8,
        textColor=C_CODE_FG, backColor=C_CODE_BG,
        spaceAfter=6, spaceBefore=2,
        leftIndent=8, rightIndent=8,
        borderPad=6, leading=12)

    add("MyBullet",
        fontName="Helvetica", fontSize=9,
        textColor=C_DARK, spaceAfter=2,
        leftIndent=14, bulletIndent=6, leading=12)

    add("MyNote",
        fontName="Helvetica-Oblique", fontSize=8,
        textColor=C_GREY, spaceAfter=4, leftIndent=8)

    add("TableHeader",
        fontName="Helvetica-Bold", fontSize=8,
        textColor=C_WHITE, leading=11)

    add("TableBody",
        fontName="Helvetica", fontSize=8,
        textColor=C_DARK, leading=11)

    return base


def _rule():
    return HRFlowable(
        width="100%", thickness=1.5,
        color=C_RULE, spaceAfter=6, spaceBefore=2,
    )


# ── Column width ratios for proportional table layout ──────────────────────────
# Keys = column count; values = relative widths per column.
_COL_RATIOS = {
    2: [1.0, 2.5],          # Flag | Effect  /  Goal | Command
    3: [1.2, 1.0, 2.0],    # Flag | Short | Effect
    4: [0.9, 2.8, 1.0, 1.5],  # Layer | Method | Confidence | Rollback?
}


def _table_cell(text, is_header, styles):
    """Escape and inline-format a markdown cell string, return a Paragraph."""
    # XML-safe escaping (Paragraph renders &lt; as < and &gt; as >)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # inline code  `...`
    text = re.sub(r"`([^`]+)`", r'<font name="Courier" size="7">\1</font>', text)
    # bold **...**
    text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)
    style = styles["TableHeader"] if is_header else styles["TableBody"]
    return Paragraph(text, style)


def _h1(text, styles):
    clean = re.sub(r"^#+\s*\d+\s*·?\s*", "", text).strip()
    return Paragraph(f"  {clean}", styles["H1"])


def _h2(text, styles):
    clean = re.sub(r"^#+\s*\d+[a-z]?\s*·?\s*", "", text).strip()
    return Paragraph(clean, styles["H2"])


def _h3(text, styles):
    clean = re.sub(r"^#+\s*", "", text).strip()
    return Paragraph(clean, styles["H3"])


def _table(rows, has_header=True, styles=None):
    col_count = max(len(r) for r in rows)
    page_w = W - 4 * cm

    ratios = _COL_RATIOS.get(col_count)
    if ratios and len(ratios) == col_count:
        total = sum(ratios)
        col_widths = [page_w * r / total for r in ratios]
    else:
        col_widths = [page_w / col_count] * col_count

    # Convert plain-string cells to Paragraphs so text wraps and XML entities
    # (e.g. &lt;file&gt;) render as the literal characters < and >.
    if styles is not None:
        para_rows = []
        for ri, row in enumerate(rows):
            is_hdr = (ri == 0 and has_header)
            para_rows.append([_table_cell(str(c), is_hdr, styles) for c in row])
        rows = para_rows

    table = Table(
        rows,
        colWidths=col_widths,
        repeatRows=1 if has_header else 0,
    )

    style = [
        ("BACKGROUND",  (0, 0), (-1, 0),  C_TABLE_H),
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_TABLE_A]),
        ("GRID",        (0, 0), (-1, -1), 0.4, colors.HexColor("#ccccdd")),
        ("TOPPADDING",  (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0),(-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",(0, 0), (-1, -1), 6),
    ]
    table.setStyle(TableStyle(style))
    return table


def _code_block(lines, styles):
    text = "\n".join(lines)
    # Escape XML chars
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = text.replace("\n", "<br/>")
    return Paragraph(text, styles["MyCode"])


def parse_md(md_text, styles):
    """
    Parse COMMANDS.md into a list of ReportLab flowables.
    Handles: # headings, tables, code fences, bullet lists, blockquotes, body text.
    """
    story = []
    lines = md_text.splitlines()
    i = 0
    first_h1_seen = False   # skip document-title H1 (already in cover block)

    while i < len(lines):
        line = lines[i]

        # ── Skip horizontal rules ---
        if re.match(r"^-{3,}$", line.strip()):
            story.append(_rule())
            i += 1
            continue

        # ── H1  (skip the very first one — it duplicates the cover title)
        if line.startswith("# "):
            if not first_h1_seen:
                first_h1_seen = True
                i += 1
                continue
            story.append(Spacer(1, 6))
            story.append(_h1(line, styles))
            i += 1
            continue

        # ── H2
        if line.startswith("## "):
            story.append(_h2(line, styles))
            i += 1
            continue

        # ── H3
        if line.startswith("### "):
            story.append(_h3(line, styles))
            i += 1
            continue

        # ── Code fence
        if line.strip().startswith("```"):
            i += 1
            code_lines = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # closing ```
            if code_lines:
                story.append(_code_block(code_lines, styles))
            continue

        # ── Markdown table
        if line.startswith("|"):
            table_lines = []
            while i < len(lines) and lines[i].startswith("|"):
                table_lines.append(lines[i])
                i += 1
            rows = []
            for tl in table_lines:
                if re.match(r"^\|[-| :]+\|$", tl.strip()):
                    continue  # separator row
                cells = [c.strip() for c in tl.strip().strip("|").split("|")]
                rows.append(cells)
            if rows:
                story.append(Spacer(1, 4))
                # Pass styles so _table() converts cells to Paragraphs
                story.append(_table(rows, styles=styles))
                story.append(Spacer(1, 4))
            continue

        # ── Bullet list
        if re.match(r"^[-*]\s+", line):
            bullets = []
            while i < len(lines) and re.match(r"^[-*]\s+", lines[i]):
                text = re.sub(r"^[-*]\s+", "", lines[i]).strip()
                # bold inline **...**
                text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)
                # inline code `...`
                text = re.sub(r"`([^`]+)`", r'<font name="Courier" size="8">\1</font>', text)
                text = text.replace("&", "&amp;").replace("<b>", "<b>").replace("</b>", "</b>")
                bullets.append(Paragraph(f"• {text}", styles["MyBullet"]))
                i += 1
            story.extend(bullets)
            continue

        # ── Blockquote
        if line.startswith("> "):
            bq_lines = []
            while i < len(lines) and lines[i].startswith("> "):
                bq_lines.append(lines[i][2:].strip())
                i += 1
            text = " ".join(bq_lines)
            text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)
            text = re.sub(r"`([^`]+)`", r'<font name="Courier" size="8">\1</font>', text)
            story.append(Paragraph(f"<i>Note: {text}</i>", styles["MyNote"]))
            continue

        # ── Blank line
        if not line.strip():
            story.append(Spacer(1, 3))
            i += 1
            continue

        # ── Body paragraph
        text = line.strip()
        text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"\*(.*?)\*", r"<i>\1</i>", text)
        text = re.sub(r"`([^`]+)`", r'<font name="Courier" size="8">\1</font>', text)
        text = text.replace("&", "&amp;")
        story.append(Paragraph(text, styles["Body"]))
        i += 1

    return story


def build_pdf(md_path: str, out_path: str):
    with open(md_path, encoding="utf-8") as f:
        md_text = f.read()

    styles = _styles()

    doc = SimpleDocTemplate(
        out_path,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title="CLI Command Reference — AI-Driven Compiler Optimization System",
        author="AI-Driven Compiler Optimization System",
    )

    story = []

    # ── Cover block ────────────────────────────────────────────────────────────
    story.append(Spacer(1, 1.5 * cm))
    story.append(Paragraph(
        "AI-Driven Compiler Optimization System",
        styles["DocTitle"],
    ))
    story.append(Paragraph(
        "CLI Command Reference",
        styles["DocSubtitle"],
    ))
    story.append(Paragraph(
        "Week 8 Edition  ·  Analysis · Optimization · Verification · Security",
        styles["DocVersion"],
    ))
    story.append(_rule())
    story.append(Spacer(1, 0.4 * cm))

    # ── Parse body ─────────────────────────────────────────────────────────────
    story.extend(parse_md(md_text, styles))

    # ── Footer note ────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.6 * cm))
    story.append(_rule())
    story.append(Paragraph(
        "AI-Driven Compiler Optimization System  ·  24CSB0A06  ·  Week 8",
        styles["DocVersion"],
    ))

    # ── Page number callback ───────────────────────────────────────────────────
    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(C_GREY)
        canvas.drawRightString(
            W - 2 * cm,
            1.2 * cm,
            f"Page {doc.page}",
        )
        canvas.drawString(
            2 * cm,
            1.2 * cm,
            "CLI Command Reference — AI-Driven Compiler Optimization System",
        )
        canvas.restoreState()

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"PDF saved to: {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Build CLI Command Reference PDF")
    parser.add_argument(
        "--out",
        default=None,
        help="Output PDF path (default: CLI_Command_Reference.pdf in project root)",
    )
    args = parser.parse_args()

    project_root = os.path.join(os.path.dirname(__file__), "..")
    md_path = os.path.join(project_root, "COMMANDS.md")

    if not os.path.isfile(md_path):
        print(f"ERROR: COMMANDS.md not found at {md_path}")
        sys.exit(1)

    out_path = args.out or os.path.join(project_root, "CLI_Command_Reference.pdf")
    build_pdf(md_path, out_path)


if __name__ == "__main__":
    main()
