import io
import os
import re
import tempfile

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
    PageBreak, Table, TableStyle, KeepTogether,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas as rl_canvas


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _parse_cgpa(semester_marks: str):
    if not semester_marks:
        return "N/A"
    for token in re.findall(r"\d+(?:\.\d+)?", semester_marks):
        val = float(token)
        if 0.0 <= val <= 10.0:
            return str(round(val, 2))
    return "N/A"


def _bullet_lines(text: str):
    if not text:
        return []
    return [line.strip() for line in text.splitlines() if line.strip()]


def _safe(val, fallback="—"):
    return str(val).strip() if val else fallback


# ─────────────────────────────────────────────
# Styles
# ─────────────────────────────────────────────

def _make_styles():
    """Return dict of all paragraph styles used across both pages."""
    S = {}

    # ── Page 1 (Resume) styles ──────────────────────
    S["r_name"] = ParagraphStyle(
        "r_name",
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.black,
        spaceAfter=2,
        alignment=TA_LEFT,
    )
    S["r_contact"] = ParagraphStyle(
        "r_contact",
        fontName="Helvetica",
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#444444"),
        spaceAfter=1,
        alignment=TA_LEFT,
    )
    S["r_contact_right"] = ParagraphStyle(
        "r_contact_right",
        fontName="Helvetica",
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#1565C0"),
        spaceAfter=1,
        alignment=TA_RIGHT,
    )
    S["r_section"] = ParagraphStyle(
        "r_section",
        fontName="Helvetica-BoldOblique",
        fontSize=10,
        textColor=colors.HexColor("#444444"),
        leading=14,
    )
    S["r_body"] = ParagraphStyle(
        "r_body",
        fontName="Helvetica",
        fontSize=9.5,
        textColor=colors.black,
        spaceAfter=2,
        leading=13,
    )
    S["r_bold"] = ParagraphStyle(
        "r_bold",
        fontName="Helvetica-Bold",
        fontSize=9.5,
        textColor=colors.black,
        spaceAfter=1,
        leading=13,
    )
    S["r_muted"] = ParagraphStyle(
        "r_muted",
        fontName="Helvetica-Oblique",
        fontSize=9,
        textColor=colors.HexColor("#666666"),
        spaceAfter=2,
        leading=12,
    )

    # ── Page 2 (Portfolio) styles ───────────────────
    S["p_name"] = ParagraphStyle(
        "p_name",
        fontName="Helvetica-Bold",
        fontSize=26,
        leading=32,
        textColor=colors.HexColor("#1A237E"),
        spaceAfter=4,
        alignment=TA_LEFT,
    )
    S["p_subtitle"] = ParagraphStyle(
        "p_subtitle",
        fontName="Helvetica",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#455A64"),
        spaceAfter=2,
        alignment=TA_LEFT,
    )
    S["p_link"] = ParagraphStyle(
        "p_link",
        fontName="Helvetica",
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#1565C0"),
        spaceAfter=2,
        alignment=TA_LEFT,
    )
    S["p_section"] = ParagraphStyle(
        "p_section",
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=18,
        textColor=colors.HexColor("#1A237E"),
        spaceBefore=12,
        spaceAfter=4,
        alignment=TA_LEFT,
    )
    S["p_bullet"] = ParagraphStyle(
        "p_bullet",
        fontName="Helvetica",
        fontSize=10,
        textColor=colors.black,
        spaceAfter=2,
        leftIndent=14,
        leading=13,
    )

    return S


# ─────────────────────────────────────────────
# Section header widget (grey pill)
# ─────────────────────────────────────────────

def _section_header(title: str, style, page_width_pts: float):
    """Return a grey-background Table row acting as a section pill header."""
    cell = Paragraph(title, style)
    tbl = Table([[cell]], colWidths=[page_width_pts - 40 * mm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EEEEEE")),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING",   (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 3),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
    ]))
    return tbl


# ─────────────────────────────────────────────
# Page 1 — Resume
# ─────────────────────────────────────────────

def _build_resume_story(student, S, page_width):
    """Build ReportLab story elements for the resume page."""
    story = []

    # ── Header: Name + contact row ───────────────
    story.append(Paragraph(_safe(student.name, "Student"), S["r_name"]))

    email_val = _safe(getattr(student, "email", None), "")
    phone_val = _safe(getattr(student, "phone", None), "")
    contact_left  = " | ".join(x for x in [email_val, phone_val] if x and x != "—")
    li = getattr(student, "linkedin", "") or ""
    gh = getattr(student, "github", "") or ""

    link_parts = []
    if li:
        link_parts.append(f'<link href="{li}"><u>LinkedIn</u></link>')
    if gh:
        link_parts.append(f'<link href="{gh}"><u>GitHub</u></link>')
    contact_right = " | ".join(link_parts)

    contact_row = Table(
        [[Paragraph(contact_left, S["r_contact"]),
          Paragraph(contact_right, S["r_contact_right"])]],
        colWidths=[(page_width - 40*mm) * 0.55,
                   (page_width - 40*mm) * 0.45],
    )
    contact_row.setStyle(TableStyle([
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING",   (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(contact_row)
    story.append(Spacer(1, 3 * mm))

    # ── EDUCATION ────────────────────────────────
    story.append(_section_header("EDUCATION", S["r_section"], page_width))
    story.append(Spacer(1, 2 * mm))

    branch_val  = _safe(getattr(student, "branch", None))
    year_val    = _safe(getattr(student, "grad_year", None))
    cgpa        = _parse_cgpa(getattr(student, "semester_marks", "") or "")

    edu_header = Table(
        [[Paragraph("<b>GM University</b>", S["r_body"]),
          Paragraph(f"Graduating {year_val}", S["r_muted"])]],
        colWidths=[(page_width - 40*mm) * 0.65,
                   (page_width - 40*mm) * 0.35],
    )
    edu_header.setStyle(TableStyle([
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING",   (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(edu_header)
    story.append(Paragraph(f"• B.E. / B.Tech — {branch_val}", S["r_body"]))
    story.append(Paragraph(f"• CGPA: {cgpa}", S["r_body"]))
    story.append(Spacer(1, 3 * mm))

    # ── PROJECTS ─────────────────────────────────
    story.append(_section_header("PROJECTS", S["r_section"], page_width))
    story.append(Spacer(1, 2 * mm))

    for i, (title_attr, stack_attr, desc_attr) in enumerate([
        ("proj1_title", "proj1_stack", "proj1_desc"),
        ("proj2_title", "proj2_stack", "proj2_desc"),
    ], 1):
        title = _safe(getattr(student, title_attr, None), "")
        stack = _safe(getattr(student, stack_attr, None), "")
        desc  = _safe(getattr(student, desc_attr,  None), "")
        if title and title != "—":
            block = [
                Paragraph(f"<b>{title}</b>", S["r_bold"]),
            ]
            if stack and stack != "—":
                block.append(Paragraph(f"• Tech Stack: {stack}", S["r_body"]))
            for line in _bullet_lines(desc):
                block.append(Paragraph(f"• {line}", S["r_body"]))
            block.append(Spacer(1, 2 * mm))
            story.extend(block)

    story.append(Spacer(1, 1 * mm))

    # ── SKILLS ───────────────────────────────────
    story.append(_section_header("SKILLS", S["r_section"], page_width))
    story.append(Spacer(1, 2 * mm))

    langs  = _safe(getattr(student, "skills_languages", None), "")
    dev    = _safe(getattr(student, "skills_dev", None), "")
    other  = _safe(getattr(student, "skills_other", None), "")

    if langs and langs != "—":
        story.append(Paragraph(f"• <b>Languages:</b> {langs}", S["r_body"]))
    if dev and dev != "—":
        story.append(Paragraph(f"• <b>Web / Dev Tools:</b> {dev}", S["r_body"]))
    for line in _bullet_lines(other):
        story.append(Paragraph(f"• {line}", S["r_body"]))
    story.append(Spacer(1, 3 * mm))

    # ── ACHIEVEMENTS ─────────────────────────────
    story.append(_section_header("ACHIEVEMENTS", S["r_section"], page_width))
    story.append(Spacer(1, 2 * mm))

    for line in _bullet_lines(getattr(student, "achievements", "") or ""):
        story.append(Paragraph(f"• {line}", S["r_body"]))
    story.append(Spacer(1, 3 * mm))

    # ── INTERESTS (2-column table) ────────────────
    story.append(_section_header("INTERESTS", S["r_section"], page_width))
    story.append(Spacer(1, 2 * mm))

    interest_lines = _bullet_lines(getattr(student, "interests", "") or "")
    if interest_lines:
        mid = (len(interest_lines) + 1) // 2
        col_a = interest_lines[:mid]
        col_b = interest_lines[mid:]

        # Pad shorter column
        while len(col_b) < len(col_a):
            col_b.append("")

        col_w = (page_width - 40 * mm) / 2
        rows = []
        for a, b in zip(col_a, col_b):
            rows.append([
                Paragraph(f"• {a}" if a else "", S["r_body"]),
                Paragraph(f"• {b}" if b else "", S["r_body"]),
            ])
        int_tbl = Table(rows, colWidths=[col_w, col_w])
        int_tbl.setStyle(TableStyle([
            ("LEFTPADDING",  (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING",   (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 1),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(int_tbl)

    return story


# ─────────────────────────────────────────────
# Page 2 — Portfolio
# ─────────────────────────────────────────────

def _build_portfolio_story(student, S):
    """Build ReportLab story elements for the portfolio page."""
    story = []
    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph(_safe(student.name, "Unknown Student"), S["p_name"]))

    usn_val    = _safe(student.usn)
    branch_val = _safe(student.branch)
    year_val   = _safe(student.grad_year)
    story.append(Paragraph(
        f"{usn_val}  ·  {branch_val}  ·  Grad Year {year_val}",
        S["p_subtitle"],
    ))
    story.append(Spacer(1, 2 * mm))

    li = getattr(student, "linkedin", "") or ""
    gh = getattr(student, "github", "") or ""
    if li:
        story.append(Paragraph(
            f'LinkedIn: <link href="{li}"><u>{li}</u></link>', S["p_link"]))
    if gh:
        story.append(Paragraph(
            f'GitHub: <link href="{gh}"><u>{gh}</u></link>', S["p_link"]))

    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(
        width="100%", thickness=1.2,
        color=colors.HexColor("#C5CAE9"), spaceAfter=6,
    ))

    sections = [
        ("Semester Marks",  student.semester_marks),
        ("Certifications",  student.certifications),
        ("Achievements",    student.achievements),
    ]
    for heading, content in sections:
        story.append(Paragraph(heading, S["p_section"]))
        lines = _bullet_lines(content)
        if lines:
            for line in lines:
                story.append(Paragraph(f"• {line}", S["p_bullet"]))
        else:
            story.append(Paragraph("• —", S["p_bullet"]))
        story.append(Spacer(1, 2 * mm))

    return story


# ─────────────────────────────────────────────
# Page callbacks
# ─────────────────────────────────────────────

def _make_page1_cb(page_w, page_h):
    def cb(canvas_obj, doc_obj):
        canvas_obj.saveState()
        canvas_obj.setFillColor(colors.white)
        canvas_obj.rect(0, 0, page_w, page_h, fill=1, stroke=0)
        canvas_obj.restoreState()
    return cb


def _make_page2_cb(page_w, page_h):
    accent = colors.HexColor("#3F51B5")
    def cb(canvas_obj, doc_obj):
        canvas_obj.saveState()
        canvas_obj.setFillColor(colors.white)
        canvas_obj.rect(0, 0, page_w, page_h, fill=1, stroke=0)
        canvas_obj.setFillColor(accent)
        canvas_obj.rect(0, page_h - 10, page_w, 10, fill=1, stroke=0)
        canvas_obj.setFont("Helvetica-Oblique", 8)
        canvas_obj.setFillColor(colors.HexColor("#90A4AE"))
        canvas_obj.drawCentredString(
            page_w / 2, 12, "Generated by ProofFolio — GM University")
        canvas_obj.restoreState()
    return cb


def _page_callbacks(page_w, page_h):
    """Return a combined onPage callback that applies the right style per page."""
    p1_cb = _make_page1_cb(page_w, page_h)
    p2_cb = _make_page2_cb(page_w, page_h)

    def on_page(canvas_obj, doc_obj):
        if doc_obj.page == 1:
            p1_cb(canvas_obj, doc_obj)
        else:
            p2_cb(canvas_obj, doc_obj)

    return on_page


# ─────────────────────────────────────────────
# QR Code overlay (applied to page 2 = index 1)
# ─────────────────────────────────────────────

def _apply_qr_overlay(pdf_bytes: bytes, student, page_w, page_h) -> bytes:
    cgpa = _parse_cgpa(getattr(student, "semester_marks", "") or "")
    payload = (
        f"Name: {_safe(student.name)}\n"
        f"USN: {_safe(student.usn)}\n"
        f"Branch: {_safe(student.branch)}\n"
        f"CGPA: {cgpa}"
    )
    print("QR payload:", payload)

    tmp_png = None
    try:
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=8,
            border=3,
        )
        qr.add_data(payload)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        import tempfile
        fd, tmp_png = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        img.convert("RGB").save(tmp_png, format="PNG")

        # Verify
        ir = ImageReader(tmp_png)
        _ = ir.getSize()

        # Build single-page QR overlay
        qr_buf = io.BytesIO()
        c = rl_canvas.Canvas(qr_buf, pagesize=A4)
        qr_x = page_w - 115
        qr_y = page_h - 115
        c.drawImage(tmp_png, qr_x, qr_y, width=85, height=85,
                    preserveAspectRatio=True, mask="auto")
        c.save()
        qr_buf.seek(0)

        main_reader = PdfReader(io.BytesIO(pdf_bytes))
        qr_reader   = PdfReader(qr_buf)

        writer = PdfWriter()
        for i, page in enumerate(main_reader.pages):
            if i == 1:          # page 2 (0-indexed) = portfolio page
                page.merge_page(qr_reader.pages[0])
            writer.add_page(page)

        out = io.BytesIO()
        writer.write(out)
        return out.getvalue()

    finally:
        if tmp_png and os.path.exists(tmp_png):
            os.remove(tmp_png)


# ─────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────

def generate_pdf(student, document_path: str = None) -> bytes:
    """
    Build a 2-page PDF:
      Page 1 — resume layout
      Page 2 — ProofFolio portfolio layout (with QR overlay)
    Optionally appends an uploaded document as additional pages.
    Returns final PDF as bytes.
    """
    page_w, page_h = A4
    S = _make_styles()
    on_page = _page_callbacks(page_w, page_h)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    # Build combined story
    story = []
    story.extend(_build_resume_story(student, S, page_w))
    story.append(PageBreak())
    story.extend(_build_portfolio_story(student, S))

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    two_page_bytes = buf.getvalue()

    # Apply QR overlay to page 2
    merged_bytes = _apply_qr_overlay(two_page_bytes, student, page_w, page_h)

    # ── Append uploaded document pages ───────────────────────────────────
    if document_path and os.path.exists(document_path):
        ext = os.path.splitext(document_path)[1].lower()
        try:
            if ext in (".jpg", ".jpeg", ".png"):
                img_buf = io.BytesIO()
                c2 = rl_canvas.Canvas(img_buf, pagesize=A4)
                c2.setFillColor(colors.white)
                c2.rect(0, 0, page_w, page_h, fill=1, stroke=0)
                c2.setFont("Helvetica-Bold", 11)
                c2.setFillColor(colors.HexColor("#1A237E"))
                c2.drawString(20 * mm, page_h - 18 * mm, "Supporting Document")
                margin = 15 * mm
                c2.drawImage(
                    document_path,
                    margin, 20 * mm,
                    width=page_w - 2 * margin,
                    height=page_h - 35 * mm,
                    preserveAspectRatio=True,
                    anchor="n",
                )
                c2.save()
                img_buf.seek(0)

                base_r  = PdfReader(io.BytesIO(merged_bytes))
                extra_r = PdfReader(img_buf)
                w2 = PdfWriter()
                for p in base_r.pages:  w2.add_page(p)
                for p in extra_r.pages: w2.add_page(p)
                out = io.BytesIO()
                w2.write(out)
                merged_bytes = out.getvalue()

            elif ext == ".pdf":
                base_r  = PdfReader(io.BytesIO(merged_bytes))
                extra_r = PdfReader(document_path)
                w2 = PdfWriter()
                for p in base_r.pages:  w2.add_page(p)
                for p in extra_r.pages: w2.add_page(p)
                out = io.BytesIO()
                w2.write(out)
                merged_bytes = out.getvalue()

        except Exception as e:
            print(f"[ProofFolio] Warning: could not append document: {e}")

    return merged_bytes
