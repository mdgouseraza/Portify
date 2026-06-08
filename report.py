import io
import json
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
    PageBreak, Table, TableStyle, KeepTogether, Flowable, Image as RLImage,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas as rl_canvas


# ─────────────────────────────────────────────
# GMU Brand Colors
# ─────────────────────────────────────────────
GMU_MAROON = colors.HexColor("#6B0000")
GMU_GOLD   = colors.HexColor("#C9973A")


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


def _get_projects(student) -> dict:
    """Return project dict, preferring projects_json then falling back to legacy columns."""
    raw = getattr(student, "projects_json", None)
    if raw:
        try:
            data = json.loads(raw)
            if data:
                return data
        except Exception:
            pass

    # Legacy fallback
    legacy = {}
    for i, (t_attr, s_attr, d_attr) in enumerate([
        ("proj1_title", "proj1_stack", "proj1_desc"),
        ("proj2_title", "proj2_stack", "proj2_desc"),
    ], start=1):
        title = _safe(getattr(student, t_attr, None), "")
        if title and title != "—":
            legacy[str(i)] = {
                "title": title,
                "stack": _safe(getattr(student, s_attr, None), ""),
                "desc":  _safe(getattr(student, d_attr, None), ""),
            }
    return legacy


# ─────────────────────────────────────────────
# Styles
# ─────────────────────────────────────────────

def _make_styles():
    S = {}

    # ── Page 1 (Resume) ──────────────────────
    S["r_name"] = ParagraphStyle(
        "r_name",
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#000000"),
        spaceAfter=3,
        alignment=TA_CENTER,
    )
    S["r_contact"] = ParagraphStyle(
        "r_contact",
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#444444"),
        spaceAfter=6,
        alignment=TA_CENTER,
    )
    S["r_section"] = ParagraphStyle(
        "r_section",
        fontName="Helvetica-Bold",
        fontSize=10.5,
        textColor=GMU_MAROON,
        leading=13,
        spaceBefore=6,
        spaceAfter=1,
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
    S["r_italic"] = ParagraphStyle(
        "r_italic",
        fontName="Helvetica-Oblique",
        fontSize=9,
        textColor=colors.HexColor("#555555"),
        spaceAfter=2,
        leading=12,
    )
    S["r_bullet"] = ParagraphStyle(
        "r_bullet",
        fontName="Helvetica",
        fontSize=9.5,
        textColor=colors.black,
        spaceAfter=2,
        leading=13,
        leftIndent=12,
    )

    # ── Page 2 (Portfolio) ───────────────────
    S["p_name"] = ParagraphStyle(
        "p_name",
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=30,
        textColor=GMU_MAROON,
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
        textColor=GMU_MAROON,
        spaceAfter=2,
        alignment=TA_LEFT,
    )
    S["p_section"] = ParagraphStyle(
        "p_section",
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=GMU_MAROON,
        spaceBefore=10,
        spaceAfter=3,
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
# Section header: maroon bold text + maroon line
# ─────────────────────────────────────────────

def _section_header(title, style):
    return [
        Paragraph(title, style),
        HRFlowable(
            width="100%",
            thickness=0.8,
            color=GMU_MAROON,
            spaceBefore=1,
            spaceAfter=4,
            hAlign="LEFT",
        ),
    ]


# ─────────────────────────────────────────────
# Page 1 — Resume
# ─────────────────────────────────────────────

def _build_resume_story(student, S, page_width, profile_pic_path=None):
    story = []
    content_width = page_width - 2 * 20 * mm  # ~481 pts with 20mm margins
    PHOTO_SIZE = 60  # pts

    # ── HEADER: Name + optional profile photo ──
    name_str  = _safe(student.name, "Student").upper()
    name_para = Paragraph(name_str, S["r_name"])

    if profile_pic_path and os.path.exists(profile_pic_path):
        try:
            photo    = RLImage(profile_pic_path, width=PHOTO_SIZE, height=PHOTO_SIZE)
            side_w   = PHOTO_SIZE + 4
            name_w   = content_width - side_w
            header_tbl = Table(
                [[name_para, photo]],
                colWidths=[name_w, side_w],
            )
            header_tbl.setStyle(TableStyle([
                ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN",         (0, 0), (0,  0),  "CENTER"),
                ("ALIGN",         (1, 0), (1,  0),  "RIGHT"),
                ("TOPPADDING",    (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("LEFTPADDING",   (0, 0), (-1, -1), 0),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ]))
            story.append(header_tbl)
        except Exception as e:
            print(f"[ProofFolio] Warning: profile pic error: {e}")
            story.append(name_para)
    else:
        story.append(name_para)

    # ── CONTACT ROW ──────────────────────────
    email_val = _safe(getattr(student, "email", None), "")
    phone_val = _safe(getattr(student, "phone", None), "")
    li = getattr(student, "linkedin", "") or ""
    gh = getattr(student, "github",   "") or ""

    contact_parts = []
    if email_val and email_val != "—":
        contact_parts.append(email_val)
    if phone_val and phone_val != "—":
        contact_parts.append(phone_val)
    if li:
        contact_parts.append(f'<link href="{li}"><font color="#6B0000">LinkedIn</font></link>')
    if gh:
        contact_parts.append(f'<link href="{gh}"><font color="#6B0000">GitHub</font></link>')
    contact_parts.append("GM University, Davangere")

    story.append(Paragraph(" | ".join(contact_parts), S["r_contact"]))
    story.append(HRFlowable(
        width="100%", thickness=0.5,
        color=colors.HexColor("#CCCCCC"),
        spaceAfter=4,
    ))

    # ── PROFESSIONAL SUMMARY ─────────────────
    summary_text = getattr(student, "interests", "") or ""
    if summary_text:
        story.extend(_section_header("PROFESSIONAL SUMMARY", S["r_section"]))
        story.append(Paragraph(summary_text, S["r_body"]))
        story.append(Spacer(1, 2 * mm))

    # ── SKILLS ───────────────────────────────
    langs = _safe(getattr(student, "skills_languages", None), "")
    dev   = _safe(getattr(student, "skills_dev",       None), "")
    other = _safe(getattr(student, "skills_other",     None), "")

    has_skills = any(x and x != "—" for x in [langs, dev, other])
    if has_skills:
        story.extend(_section_header("SKILLS", S["r_section"]))
        if langs and langs != "—":
            story.append(Paragraph(f"<b>Languages:</b> {langs}", S["r_body"]))
        if dev and dev != "—":
            story.append(Paragraph(f"<b>Frameworks &amp; Tools:</b> {dev}", S["r_body"]))
        if other and other != "—":
            story.append(Paragraph(f"<b>Other Skills:</b> {other}", S["r_body"]))
        story.append(Spacer(1, 2 * mm))

    # ── EDUCATION ────────────────────────────
    story.extend(_section_header("EDUCATION", S["r_section"]))
    branch_val = _safe(getattr(student, "branch",    None))
    year_val   = _safe(getattr(student, "grad_year", None))
    cgpa       = _parse_cgpa(getattr(student, "semester_marks", "") or "")

    story.append(Paragraph("<b>GM University</b> | Davangere, Karnataka, India", S["r_bold"]))
    degree_line = f"B.Tech in {branch_val}"
    if year_val and year_val != "—":
        degree_line += f" | Graduating {year_val}"
    if cgpa != "N/A":
        degree_line += f" | CGPA: {cgpa}"
    else:
        degree_line += " | Currently Pursuing"
    story.append(Paragraph(degree_line, S["r_body"]))
    story.append(Spacer(1, 2 * mm))

    # ── PROJECTS ─────────────────────────────
    projects = _get_projects(student)
    if projects:
        story.extend(_section_header("PROJECTS", S["r_section"]))
        for key in sorted(projects.keys(), key=lambda x: int(x)):
            proj  = projects[key]
            title = proj.get("title", "")
            stack = proj.get("stack", "")
            desc  = proj.get("desc",  "")
            if title:
                header_txt = f"<b>{title}</b>"
                if stack:
                    header_txt += f" | {stack}"
                story.append(Paragraph(header_txt, S["r_bold"]))
                for line in _bullet_lines(desc):
                    story.append(Paragraph(f"• {line}", S["r_bullet"]))
                story.append(Spacer(1, 2 * mm))

    # ── ACHIEVEMENTS & CERTIFICATIONS ─────────
    cert_lines = _bullet_lines(getattr(student, "certifications", "") or "")
    ach_lines  = _bullet_lines(getattr(student, "achievements",   "") or "")
    all_items  = cert_lines + ach_lines
    if all_items:
        story.extend(_section_header("ACHIEVEMENTS & CERTIFICATIONS", S["r_section"]))
        for line in all_items:
            story.append(Paragraph(f"• {line}", S["r_bullet"]))

    return story


# ─────────────────────────────────────────────
# Page 2 — Portfolio
# ─────────────────────────────────────────────

def _build_portfolio_story(student, S, profile_pic_path=None):
    story = []
    story.append(Spacer(1, 5 * mm))

    # Name + optional profile photo side by side
    name_para = Paragraph(_safe(student.name, "Unknown Student"), S["p_name"])

    if profile_pic_path and os.path.exists(profile_pic_path):
        try:
            PHOTO_SIZE = 70
            photo = RLImage(profile_pic_path, width=PHOTO_SIZE, height=PHOTO_SIZE)
            tbl = Table(
                [[name_para, photo]],
                colWidths=[None, PHOTO_SIZE + 4],
            )
            tbl.setStyle(TableStyle([
                ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING",    (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("LEFTPADDING",   (0, 0), (-1, -1), 0),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ]))
            story.append(tbl)
        except Exception:
            story.append(name_para)
    else:
        story.append(name_para)

    usn_val    = _safe(student.usn)
    branch_val = _safe(student.branch)
    year_val   = _safe(student.grad_year)
    story.append(Paragraph(
        f"{usn_val}  ·  {branch_val}  ·  Grad Year {year_val}",
        S["p_subtitle"],
    ))
    story.append(Spacer(1, 2 * mm))

    li = getattr(student, "linkedin", "") or ""
    gh = getattr(student, "github",   "") or ""
    if li:
        story.append(Paragraph(
            f'LinkedIn: <link href="{li}"><u>{li}</u></link>', S["p_link"]))
    if gh:
        story.append(Paragraph(
            f'GitHub: <link href="{gh}"><u>{gh}</u></link>', S["p_link"]))

    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(
        width="100%", thickness=1.2,
        color=GMU_GOLD, spaceAfter=6,
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

    # Projects summary on portfolio page
    projects = _get_projects(student)
    if projects:
        story.append(Paragraph("Projects", S["p_section"]))
        for key in sorted(projects.keys(), key=lambda x: int(x)):
            proj  = projects[key]
            title = proj.get("title", "")
            stack = proj.get("stack", "")
            if title:
                line = f"• <b>{title}</b>"
                if stack:
                    line += f" — {stack}"
                story.append(Paragraph(line, S["p_bullet"]))
        story.append(Spacer(1, 2 * mm))

    return story


# ─────────────────────────────────────────────
# Page callbacks — GMU branding
# ─────────────────────────────────────────────

def _make_page1_cb(page_w, page_h):
    def cb(canvas_obj, doc_obj):
        canvas_obj.saveState()
        canvas_obj.setFillColor(colors.white)
        canvas_obj.rect(0, 0, page_w, page_h, fill=1, stroke=0)
        # Thin gold top bar
        canvas_obj.setFillColor(GMU_GOLD)
        canvas_obj.rect(0, page_h - 5, page_w, 5, fill=1, stroke=0)
        canvas_obj.restoreState()
    return cb


def _make_page2_cb(page_w, page_h):
    def cb(canvas_obj, doc_obj):
        canvas_obj.saveState()
        canvas_obj.setFillColor(colors.white)
        canvas_obj.rect(0, 0, page_w, page_h, fill=1, stroke=0)
        # Maroon top bar
        canvas_obj.setFillColor(GMU_MAROON)
        canvas_obj.rect(0, page_h - 10, page_w, 10, fill=1, stroke=0)
        # Gold bottom footer bar
        canvas_obj.setFillColor(GMU_GOLD)
        canvas_obj.rect(0, 0, page_w, 18, fill=1, stroke=0)
        canvas_obj.setFont("Helvetica-Bold", 7.5)
        canvas_obj.setFillColor(colors.HexColor("#1A0000"))
        canvas_obj.drawCentredString(
            page_w / 2, 6, "Generated by ProofFolio — GM University, Davangere · Innovating Minds")
        canvas_obj.restoreState()
    return cb


def _page_callbacks(page_w, page_h):
    p1_cb = _make_page1_cb(page_w, page_h)
    p2_cb = _make_page2_cb(page_w, page_h)

    def on_page(canvas_obj, doc_obj):
        if doc_obj.page == 1:
            p1_cb(canvas_obj, doc_obj)
        else:
            p2_cb(canvas_obj, doc_obj)

    return on_page


# ─────────────────────────────────────────────
# QR Code overlay on page 2
# ─────────────────────────────────────────────

def _apply_qr_overlay(pdf_bytes: bytes, student, page_w, page_h) -> bytes:
    cgpa = _parse_cgpa(getattr(student, "semester_marks", "") or "")
    payload = (
        f"Name: {_safe(student.name)}\n"
        f"USN: {_safe(student.usn)}\n"
        f"Branch: {_safe(student.branch)}\n"
        f"CGPA: {cgpa}\n"
        f"GM University, Davangere"
    )

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

        fd, tmp_png = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        img.convert("RGB").save(tmp_png, format="PNG")

        ir = ImageReader(tmp_png)
        _ = ir.getSize()

        qr_buf = io.BytesIO()
        c = rl_canvas.Canvas(qr_buf, pagesize=A4)
        qr_x = page_w - 115
        qr_y = 30
        c.drawImage(tmp_png, qr_x, qr_y, width=85, height=85,
                    preserveAspectRatio=True, mask="auto")
        c.save()
        qr_buf.seek(0)

        main_reader = PdfReader(io.BytesIO(pdf_bytes))
        qr_reader   = PdfReader(qr_buf)

        writer = PdfWriter()
        for i, page in enumerate(main_reader.pages):
            if i == 1:
                page.merge_page(qr_reader.pages[0])
            writer.add_page(page)

        out = io.BytesIO()
        writer.write(out)
        return out.getvalue()

    finally:
        if tmp_png and os.path.exists(tmp_png):
            os.remove(tmp_png)


# ─────────────────────────────────────────────
# Append a single document page to pdf bytes
# ─────────────────────────────────────────────

def _append_document(merged_bytes: bytes, doc_path: str, page_w: float, page_h: float, label: str = "Supporting Document") -> bytes:
    """Append a single image or PDF file as an extra page."""
    ext = os.path.splitext(doc_path)[1].lower()
    try:
        if ext in (".jpg", ".jpeg", ".png"):
            img_buf = io.BytesIO()
            c2 = rl_canvas.Canvas(img_buf, pagesize=A4)
            c2.setFillColor(colors.white)
            c2.rect(0, 0, page_w, page_h, fill=1, stroke=0)
            # GMU gold top bar
            c2.setFillColor(GMU_GOLD)
            c2.rect(0, page_h - 6, page_w, 6, fill=1, stroke=0)
            c2.setFont("Helvetica-Bold", 11)
            c2.setFillColor(GMU_MAROON)
            c2.drawString(20 * mm, page_h - 18 * mm, label)
            margin = 15 * mm
            c2.drawImage(
                doc_path,
                margin, 20 * mm,
                width=page_w - 2 * margin,
                height=page_h - 35 * mm,
                preserveAspectRatio=True,
                anchor="n",
            )
            # Footer
            c2.setFillColor(GMU_GOLD)
            c2.rect(0, 0, page_w, 18, fill=1, stroke=0)
            c2.setFont("Helvetica-Bold", 7.5)
            c2.setFillColor(colors.HexColor("#1A0000"))
            c2.drawCentredString(page_w / 2, 6, "GM University, Davangere · ProofFolio")
            c2.save()
            img_buf.seek(0)

            base_r  = PdfReader(io.BytesIO(merged_bytes))
            extra_r = PdfReader(img_buf)
            w2 = PdfWriter()
            for p in base_r.pages:  w2.add_page(p)
            for p in extra_r.pages: w2.add_page(p)
            out = io.BytesIO()
            w2.write(out)
            return out.getvalue()

        elif ext == ".pdf":
            base_r  = PdfReader(io.BytesIO(merged_bytes))
            extra_r = PdfReader(doc_path)
            w2 = PdfWriter()
            for p in base_r.pages:  w2.add_page(p)
            for p in extra_r.pages: w2.add_page(p)
            out = io.BytesIO()
            w2.write(out)
            return out.getvalue()

    except Exception as e:
        print(f"[ProofFolio] Warning: could not append {doc_path}: {e}")

    return merged_bytes


# ─────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────

def generate_pdf(student, cert_paths: list = None, profile_pic_path: str = None) -> bytes:
    page_w, page_h = A4
    S       = _make_styles()
    on_page = _page_callbacks(page_w, page_h)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )

    story = []
    story.extend(_build_resume_story(student, S, page_w, profile_pic_path=profile_pic_path))
    story.append(PageBreak())
    story.extend(_build_portfolio_story(student, S, profile_pic_path=profile_pic_path))

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    two_page_bytes = buf.getvalue()

    merged_bytes = _apply_qr_overlay(two_page_bytes, student, page_w, page_h)

    # ── Append all uploaded certificate / proof documents ─────────────────
    if cert_paths:
        for idx, doc_path in enumerate(cert_paths, start=1):
            if doc_path and os.path.exists(doc_path):
                merged_bytes = _append_document(
                    merged_bytes,
                    doc_path,
                    page_w,
                    page_h,
                    label=f"Certificate / Proof of Work — Document {idx}",
                )

    return merged_bytes
