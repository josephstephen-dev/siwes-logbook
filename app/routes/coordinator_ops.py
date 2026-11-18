from types import SimpleNamespace

from flask import abort, flash, redirect, render_template, request, send_file, url_for, current_app
from flask_login import current_user
from sqlalchemy import or_

from ..extensions import db
from ..models.checkpoint import Checkpoint, IntegrityResult
from ..models.entry import Entry
from ..models.flag import Flag
from ..models.placement import Placement
from ..models.user import User
from ..models.verification import IssuedLogbook
from ..models.week import WeekRecord
from ..services import audit_chain, detection, pdf_report, weeks
from ..services import finalize as finalize_svc
from ..services.invitations import now
from ..services.permissions import role_required
from .coordinator import _person, bp
from datetime import datetime, timedelta, timezone
import json


def _placements():
    return (Placement.query.join(User, Placement.student_id == User.id)
            .order_by(User.full_name).all())


# ---- student detail ----------------------------------------------------

@bp.route("/students/<int:student_id>")
@role_required("coordinator")
def student_detail(student_id):
    st = _person(student_id, "student")
    p = st.placement
    ctx = dict(st=st, p=p, result=IntegrityResult.query.filter_by(student_id=st.id).first(),
               timeline=[], entries=[], flags=[])
    if p:
        by = weeks.entries_by_date(st)
        recs = {w.week_no: w for w in WeekRecord.query.filter_by(student_id=st.id)}
        for n in range(weeks.current_week_no(p), 0, -1):
            working = [r for r in weeks.rows_for(p, n, by) if r.works]
            wk = recs.get(n)
            ctx["timeline"].append(SimpleNamespace(
                n=n, start=weeks.week_start(p, n), end=weeks.week_end(p, n), wk=wk,
                done=sum(1 for r in working if r.entry), total=len(working),
                label=weeks.STATUS_LABEL[wk.status] if wk else "Draft"))
        ctx["entries"] = (Entry.query.filter_by(student_id=st.id)
                          .order_by(Entry.work_date.desc()).limit(30).all())
        ids = [e.id for e in Entry.query.filter_by(student_id=st.id)]
        if ids:
            ctx["flags"] = Flag.query.filter(or_(Flag.entry_a_id.in_(ids), Flag.entry_b_id.in_(ids))).all()
    return render_template("coordinator/student_detail.html", **ctx)


# ---- flags -------------------------------------------------------------

@bp.route("/flags")
@role_required("coordinator")
def flags():
    status = request.args.get("status", "open")
    q = Flag.query
    if status in ("open", "dismissed", "confirmed"):
        q = q.filter_by(status=status)
    counts = {s: Flag.query.filter_by(status=s).count() for s in ("open", "dismissed", "confirmed")}
    return render_template("coordinator/flags.html", rows=q.order_by(Flag.score.desc()).all(),
                           status=status, counts=counts)


@bp.route("/flags/scan", methods=["POST"])
@role_required("coordinator")
def flags_scan():
    n = detection.scan(since_days=30)
    flash(f"Scan finished. {n} new possible similarit{'y' if n == 1 else 'ies'} found.", "success")
    return redirect(url_for("coordinator.flags"))


@bp.route("/flags/<int:flag_id>")
@role_required("coordinator")
def flag_review(flag_id):
    f = db.session.get(Flag, flag_id)
    if not f:
        abort(404)
    return render_template("coordinator/flag_review.html", f=f,
                           a_html=detection.highlight(f.entry_a.body, f.entry_b.body),
                           b_html=detection.highlight(f.entry_b.body, f.entry_a.body))


@bp.route("/flags/<int:flag_id>/decide", methods=["POST"])
@role_required("coordinator")
def flag_decide(flag_id):
    f = db.session.get(Flag, flag_id)
    if not f:
        abort(404)
    if f.status != "open":
        flash("This flag has already been decided.", "error")
        return redirect(url_for("coordinator.flags", status=f.status))
    decision, note = request.form.get("decision"), request.form.get("note", "").strip()
    if decision not in ("dismiss", "confirm") or len(note) < 5:
        flash("Write a short note (at least 5 characters) explaining your decision.", "error")
        return redirect(url_for("coordinator.flag_review", flag_id=f.id))
    f.status = "dismissed" if decision == "dismiss" else "confirmed"
    f.note, f.reviewed_by_id, f.reviewed_at = note[:1000], current_user.id, now()
    db.session.commit()
    flash("Your decision was recorded.", "success")
    return redirect(url_for("coordinator.flags"))


# ---- integrity ---------------------------------------------------------

def _stale(r):
    if not r or not r.checked_at:
        return False
    t = r.checked_at if r.checked_at.tzinfo else r.checked_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - t > timedelta(hours=36)


@bp.route("/integrity")
@role_required("coordinator")
def integrity():
    results = {r.student_id: r for r in IntegrityResult.query}
    cp = Checkpoint.query.order_by(Checkpoint.id.desc()).first()
    heads = json.loads(cp.heads) if cp else {}
    rows = _placements()
    rows.sort(key=lambda p: 0 if (results.get(p.student_id) and not results[p.student_id].ok)
              else 1 if p.student_id not in results else 2)
    counts = SimpleNamespace(
        ok=sum(1 for p in rows if results.get(p.student_id) and results[p.student_id].ok),
        bad=sum(1 for p in rows if results.get(p.student_id) and not results[p.student_id].ok),
        unchecked=sum(1 for p in rows if p.student_id not in results))
    ev = audit_chain.event_counts()
    counts.events = sum(ev.values())
    return render_template("coordinator/integrity.html", rows=rows, results=results, cp=cp,
                           heads=heads, counts=counts, events=ev,
                           stale={p.student_id: _stale(results.get(p.student_id)) for p in rows},
                           cp_problems=audit_chain.audit_checkpoints())


@bp.route("/integrity/check-digest", methods=["POST"])
@role_required("coordinator")
def integrity_check_digest():
    if audit_chain.published_matches(request.form.get("digest", "")):
        flash("That checkpoint matches one held on this server and is unaltered.", "success")
    else:
        flash("No checkpoint on this server matches that value. Compare it with the emailed one.", "error")
    return redirect(url_for("coordinator.integrity"))


@bp.route("/integrity/run", methods=["POST"])
@role_required("coordinator")
def integrity_run_all():
    bad = sum(1 for p in _placements() if not audit_chain.run_check(p.student_id).ok)
    flash("All checks finished. " + ("Everything is verified." if not bad else f"{bad} problem(s) found."),
          "success" if not bad else "error")
    return redirect(url_for("coordinator.integrity"))


@bp.route("/integrity/<int:student_id>/run", methods=["POST"])
@role_required("coordinator")
def integrity_run(student_id):
    _person(student_id, "student")
    audit_chain.run_check(student_id)
    return redirect(request.referrer or url_for("coordinator.integrity"))


# ---- finalize ----------------------------------------------------------

@bp.route("/finalize")
@role_required("coordinator")
def finalize():
    issued = {i.student_id: i for i in IssuedLogbook.query.filter_by(revoked_at=None)}
    return render_template("coordinator/finalize.html", rows=_placements(), issued=issued, sel=None, checks=None)


@bp.route("/finalize/<int:student_id>")
@role_required("coordinator")
def finalize_student(student_id):
    st = _person(student_id, "student")
    if not st.placement:
        abort(404)
    issued = IssuedLogbook.query.filter_by(student_id=st.id, revoked_at=None).first()
    return render_template("coordinator/finalize.html", rows=None, issued=issued, sel=st,
                           checks=finalize_svc.checklist(st))


@bp.route("/finalize/<int:student_id>/generate", methods=["POST"])
@role_required("coordinator")
def finalize_generate(student_id):
    st = _person(student_id, "student")
    if not st.placement or not finalize_svc.checklist(st).ready:
        flash("The checklist must pass before a verified PDF can be issued.", "error")
    else:
        try:
            rec = pdf_report.issue(st, current_user)
            flash(f"Verified PDF issued: {rec.vid}. Any earlier copy for this student no longer verifies.", "success")
        except Exception as exc:
            db.session.rollback()
            current_app.logger.exception("PDF generation failed for student %s", student_id)
            flash(f"The PDF could not be created ({type(exc).__name__}: {exc}). Nothing was issued.", "error")
    return redirect(url_for("coordinator.finalize_student", student_id=student_id))

@bp.route("/issued/<vid>/download")
@role_required("coordinator")
def issued_download(vid):
    rec = IssuedLogbook.query.filter_by(vid=vid).first()
    if not rec:
        abort(404)
    import os
    return send_file(os.path.join(pdf_report.issued_dir(), rec.filename), mimetype="application/pdf",
                     as_attachment=True, download_name=f"{rec.vid}.pdf")