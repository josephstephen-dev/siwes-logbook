import hashlib
import io
import os
import secrets
from datetime import date
from types import SimpleNamespace
from xml.sax.saxutils import escape as xesc

import qrcode
from flask import current_app
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether, NextPageTemplate,
                                PageBreak, PageTemplate, Paragraph, Spacer, Table)
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.platypus import (BaseDocTemplate, Frame, HRFlowable, Image, KeepTogether,
                                NextPageTemplate, PageBreak, PageTemplate, Paragraph, Spacer, Table)

from ..extensions import db
from ..models.verification import IssuedLogbook
from ..models.week import WeekRecord
from . import audit_chain, uploads, weeks
from .invitations import now, public_url

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def issued_dir():
    path = current_app.config.get("ISSUED_DIR") or os.path.join(current_app.instance_path, "issued")
    os.makedirs(path, exist_ok=True)
    return path


def _fonts():
    """Add static/fonts/DejaVuSans.ttf and DejaVuSans-Bold.ttf to print names with accents (Igbo, Yoruba)."""
    base = os.path.join(current_app.root_path, "static", "fonts")
    reg, bold = os.path.join(base, "DejaVuSans.ttf"), os.path.join(base, "DejaVuSans-Bold.ttf")
    if os.path.exists(reg) and os.path.exists(bold):
        pdfmetrics.registerFont(TTFont("Body", reg))
        pdfmetrics.registerFont(TTFont("Body-Bold", bold))
        registerFontFamily("Body", normal="Body", bold="Body-Bold", italic="Body", boldItalic="Body-Bold")
        return "Body", "Body-Bold"
    return "Helvetica", "Helvetica-Bold"


def make_vid(student):
    parts = [w[0] for w in student.full_name.split()[:2]]
    initials = "".join(parts).upper() or "XX"
    while True:
        vid = f"SW-{date.today().year % 100}-{initials}-" + "".join(secrets.choice(ALPHABET) for _ in range(4))
        if not IssuedLogbook.query.filter_by(vid=vid).first():
            return vid


def _footer(vid, font, numbered):
    def draw(c, doc):
        c.saveState()
        c.setFont(font, 8)
        c.drawString(18 * mm, 10 * mm, f"Verification ID: {vid}")
        if numbered:
            n = str(doc.page - 1)                         # the cover is not numbered
            w = c.stringWidth(n, font, 10) + 12
            x = A4[0] / 2 - w / 2
            c.rect(x, 8 * mm, w, 6.5 * mm)
            c.setFont(font, 10)
            c.drawCentredString(A4[0] / 2, 9.8 * mm, n)
        c.restoreState()
    return draw

def _cover_frame(vid, font):
    def draw(c, doc):
        c.saveState()
        c.setLineWidth(1.6)
        c.rect(6 * mm, 6 * mm, A4[0] - 12 * mm, A4[1] - 12 * mm)
        c.setLineWidth(0.5)
        c.rect(8 * mm, 8 * mm, A4[0] - 16 * mm, A4[1] - 16 * mm)
        c.setFont(font, 8)
        c.drawString(18 * mm, 12 * mm, f"Verification ID: {vid}")
        c.restoreState()
    return draw

def build(student, vid, issued_by=None):
    f, fb = _fonts()
    p, sup = student.placement, student.industry_supervisor
    ss = getSampleStyleSheet()

    def style(name, **kw):
        return ParagraphStyle(name, parent=ss["Normal"], fontName=kw.pop("fontName", f),
                              fontSize=kw.pop("fontSize", 10), leading=kw.pop("leading", 13), **kw)

    body, small = style("body"), style("small", fontSize=8, leading=10)
    bold, center = style("bold", fontName=fb), style("center", fontName=fb, alignment=TA_CENTER)
    right = style("right", alignment=TA_RIGHT)
    title = style("title", fontName=fb, fontSize=14, leading=18, alignment=TA_CENTER)
    note = style("note", fontSize=9, alignment=TA_CENTER)
    big = style("big", fontName=fb, fontSize=20, leading=26, alignment=TA_CENTER)

    def P(text, st=body):
        return Paragraph(xesc(str(text)).replace("\n", "<br/>"), st)

    buf = io.BytesIO()
    doc = BaseDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                          topMargin=16 * mm, bottomMargin=20 * mm,
                          title=f"Industrial Training Logbook {vid}", author="SIWES Logbook")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")
    doc.addPageTemplates([PageTemplate(id="cover", frames=[frame], onPage=_cover_frame(vid, f)),
                          PageTemplate(id="body", frames=[frame], onPage=_footer(vid, f, True))])
    W = doc.width
    box = [("BOX", (0, 0), (-1, -1), 1.2, colors.black), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
    grid = box + [("INNERGRID", (0, 0), (-1, -1), 0.6, colors.black)]

    # ---- cover
    from ..models.entry import Entry
    inst = current_app.config["INSTITUTION_NAME"]
    approved_n = WeekRecord.query.filter_by(student_id=student.id, status="approved").count()
    entries_n = Entry.query.filter_by(student_id=student.id).count()
    green = colors.Color(.09, .31, .23)
    qr = qrcode.make(public_url("verify.result", vid=vid), box_size=8, border=1)
    qb = io.BytesIO()
    qr.save(qb, format="PNG")
    qb.seek(0)

    inst_st = style("inst", fontName=fb, fontSize=15, leading=19, alignment=TA_CENTER)
    scheme = style("scheme", fontSize=9.5, leading=12, alignment=TA_CENTER, textColor=colors.Color(.3, .3, .3))
    head_w = style("headw", fontName=fb, fontSize=8.5, leading=11, textColor=colors.white)
    lab = style("lab", fontName=fb, fontSize=8.5, leading=11, textColor=colors.Color(.33, .33, .3))
    val = style("val", fontSize=10.5, leading=13)

    def block(heading, pairs):
        data = [[Paragraph(xesc(heading).upper(), head_w), ""]]
        data += [[Paragraph(xesc(a), lab), Paragraph(xesc(str(b or "—")), val)] for a, b in pairs]
        return Table(data, colWidths=[W * 0.30, W * 0.70], style=[
            ("SPAN", (0, 0), (1, 0)), ("BACKGROUND", (0, 0), (1, 0), green),
            ("BOX", (0, 0), (-1, -1), 0.8, colors.black),
            ("LINEBELOW", (0, 1), (-1, -2), 0.4, colors.Color(.75, .75, .7)),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE")])

    verify_box = Table(
        [[Image(qb, 34 * mm, 34 * mm),
          [P("VERIFY THIS LOGBOOK", bold), Spacer(1, 2 * mm), P(f"Verification ID: {vid}"), Spacer(1, 1 * mm),
           P("Scan the QR code, or open the verification page and enter the ID. "
             "A printed copy can only be checked against this record.", small)]]],
        colWidths=[40 * mm, W - 40 * mm],
        style=box + [("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)])

    story = [
        P(inst.upper(), inst_st), Spacer(1, 1 * mm),
        P("STUDENT INDUSTRIAL WORK EXPERIENCE SCHEME (SIWES)", scheme), Spacer(1, 7 * mm),
        P("INDUSTRIAL TRAINING LOGBOOK", big), Spacer(1, 2 * mm),
        HRFlowable(width="40%", thickness=2.5, color=green, hAlign="CENTER"), Spacer(1, 5 * mm),
        block("Student", [("Full name", student.full_name), ("Matric number", student.matric_number),
                          ("Department", student.department), ("Level", f"{student.level} Level")]),
        Spacer(1, 4 * mm),
        block("Industrial training placement", [
            ("Company", p.company_name), ("Address", p.company_address),
            ("Training period", f"{p.start_date:%d %B %Y} – {p.end_date:%d %B %Y}"),
            ("Working days", ", ".join(p.day_labels))]),
        Spacer(1, 4 * mm),
        block("Supervision", [("Industry-based supervisor", sup.full_name if sup else None),
                              ("Designation", sup.designation if sup else None),
                              ("School supervisor", p.school_supervisor)]),
        Spacer(1, 4 * mm),
        block("Logbook summary", [("Weeks approved", f"{approved_n} of {p.total_weeks}"),
                                  ("Daily entries recorded", entries_n),
                                  ("Issued on", weeks.to_lagos(now(), "%d %B %Y")),
                                  ("Issued by", issued_by.full_name if issued_by else None)]),
        Spacer(1, 5 * mm), verify_box,
        NextPageTemplate("body"), PageBreak()]

    # ---- weeks
    by_date = weeks.entries_by_date(student)
    recs = {w.week_no: w for w in WeekRecord.query.filter_by(student_id=student.id, status="approved")}
    for n in sorted(recs):
        wk, rows = recs[n], weeks.rows_for(p, n, by_date)
        start, end = weeks.week_start(p, n), weeks.week_end(p, n)
        story.append(Table([[P("WEEKLY PROGRESS CHART", center), P(f"WEEK {n}", center),
                             P(f"WEEK ENDING {end:%d %b %Y}".upper(), center)]],
                           colWidths=[W * 0.5, W * 0.2, W * 0.3], style=grid + [("TOPPADDING", (0, 0), (-1, -1), 10),
                                                                              ("BOTTOMPADDING", (0, 0), (-1, -1), 10)]))
        story += [Spacer(1, 4 * mm), P(f"Date  {start:%d %b %Y}".upper(), right), Spacer(1, 2 * mm)]
        data = [[P("Day", center), P("Description of work done", center)]]
        for r in rows:
            day = Paragraph(f"<b>{r.label}</b><br/><font size=8>{r.date:%d %b}</font>", style("c2", alignment=TA_CENTER))
            if r.entry:
                text = xesc(r.entry.body).replace("\n", "<br/>")
                if r.entry.is_late:
                    text += "<br/><font size=7>Late entry</font>"
                desc = Paragraph(text, body)
            else:
                desc = P("—" if not r.works else "No entry recorded.")
            data.append([day, desc])
        story.append(Table(data, colWidths=[22 * mm, W - 22 * mm], repeatRows=1,
                           style=grid + [("TOPPADDING", (0, 1), (-1, -1), 12), ("BOTTOMPADDING", (0, 1), (-1, -1), 12),
                                         ("BACKGROUND", (0, 0), (-1, 0), colors.Color(.94, .94, .9))]))
        story.append(PageBreak())

        story += [P(f"Date  {end:%d %b %Y}".upper(), right), Spacer(1, 3 * mm),
                  P("FOR SKETCHES, DIAGRAMS AND GRAPHS", title), Spacer(1, 2 * mm),
                  P("(Additional drawing, may be attached where necessary) The student may use the space for additional reports", note),
                  Spacer(1, 4 * mm)]
        for a in wk.attachments:
            path = uploads.path_for(a.stored_name)
            if os.path.exists(path):
                with PILImage.open(path) as im:
                    w, h = im.size
                k = min(W / w, 85 * mm / h)
                story.append(KeepTogether([Image(path, w * k, h * k), P(a.caption or "", small), Spacer(1, 3 * mm)]))
        if wk.report:
            story += [P(wk.report), Spacer(1, 4 * mm)]
        elif not wk.attachments:
            story += [P("No sketches or additional report this week.", small), Spacer(1, 4 * mm)]
        s = student.industry_supervisor
        signed = weeks.to_lagos(wk.confirmed_at, "%d %b %Y") if wk.confirmed_at else "—"
        sign = [
            [P("Student's Signature", bold), P(f"I confirm this week's entries are my own work.\nTyped name: {wk.typed_name}"),
             P(f"Date {signed}")],
            [P("Comments by Industry-Based Supervisor", bold), P(wk.supervisor_comment or ""), ""],
            [P("Name, Signature & Stamp", bold),
             P(f"{wk.approver_name}\n{wk.approver_designation}" + (f", {s.company}" if s else "")),
             P(f"Date {weeks.to_lagos(wk.approved_at, '%d %b %Y')}")],
            [P("Company stamp (if required by the department)", bold), "", ""],
        ]
        story.append(Table(sign, colWidths=[44 * mm, W - 44 * mm - 34 * mm, 34 * mm],
                           rowHeights=[None, 28 * mm, None, 28 * mm],
                           style=grid + [("SPAN", (1, 1), (2, 1)), ("SPAN", (1, 3), (2, 3)),
                                         ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story += [Spacer(1, 2 * mm),
                  P(f"Approved on {weeks.to_lagos(wk.approved_at)} · Identity confirmed by SIWES coordinator on "
                    f"{weeks.to_lagos(s.verified_at, '%d %b %Y') if s and s.verified_at else '—'}", small),
                  PageBreak()]
    if story and isinstance(story[-1], PageBreak):
        story.pop()
    doc.build(story)
    return buf.getvalue()


def issue(student, by):
    """Builds the PDF first, then records the event, stores the file and revokes any earlier copy."""
    vid = make_vid(student)
    pdf = build(student, vid, by)
    ev = audit_chain.append(student.id, "logbook_issued", {"vid": vid})
    name = f"{vid}.pdf"
    with open(os.path.join(issued_dir(), name), "wb") as fh:
        fh.write(pdf)
    for old in IssuedLogbook.query.filter_by(student_id=student.id, revoked_at=None):
        old.revoked_at = now()
    p = student.placement
    digits = "".join(c for c in (student.matric_number or "") if c.isdigit())
    rec = IssuedLogbook(
        vid=vid, student_id=student.id, pdf_sha256=hashlib.sha256(pdf).hexdigest(), filename=name,
        size=len(pdf), company=p.company_name, start_date=p.start_date, end_date=p.end_date,
        initials="".join(w[0] for w in student.full_name.split()[:3]).upper(), matric_tail=digits[-3:],
        head_seq=ev.seq, head_digest=ev.digest, issued_by_id=by.id)
    db.session.add(rec)
    db.session.commit()
    return rec

def _fonts():
    """Uses DejaVu if a valid copy is installed; otherwise the built-in Helvetica."""
    base = os.path.join(current_app.root_path, "static", "fonts")
    reg, bold = os.path.join(base, "DejaVuSans.ttf"), os.path.join(base, "DejaVuSans-Bold.ttf")
    try:
        if os.path.exists(reg) and os.path.exists(bold):
            pdfmetrics.registerFont(TTFont("Body", reg))
            pdfmetrics.registerFont(TTFont("Body-Bold", bold))
            return "Body", "Body-Bold"
    except Exception:
        current_app.logger.warning("DejaVu fonts are not valid; using Helvetica")
    return "Helvetica", "Helvetica-Bold"