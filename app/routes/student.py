from datetime import date
from functools import wraps
from types import SimpleNamespace

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..extensions import db
from ..forms.entry_forms import EntryForm, SketchForm
from ..models.attachment import Attachment
from ..models.entry import Entry
from ..models.week import WeekRecord
from ..services import approvals, uploads, weeks
from ..services import invitations as svc
from ..services.entries import MAX_CHARS, MIN_CHARS, RuleError, amend_entry, check_writable, record_entry
from ..services.permissions import role_required

bp = Blueprint("student", __name__)


def placement_required(view):
    @wraps(view)
    def inner(*a, **k):
        if not current_user.placement:
            flash("Your coordinator hasn't set up your placement yet.", "info")
            return redirect(url_for("student.home"))
        return view(*a, **k)
    return inner


def _check_week(p, n):
    if n < 1 or n > weeks.current_week_no(p):
        abort(404)


def _day(day):
    try:
        return date.fromisoformat(day)
    except ValueError:
        abort(404)


def _label(d):
    return weeks.DAYS[min(d.weekday(), 5)]


def _back(p, d):
    n = weeks.week_no_for(p, d)
    return url_for("student.week_chart", n=n) if 1 <= n <= weeks.current_week_no(p) else url_for("student.home")


# ---- home, logbook, details --------------------------------------------

def _week_items(p, limit=None):
    by = weeks.entries_by_date(current_user)
    recs = {w.week_no: w for w in WeekRecord.query.filter_by(student_id=current_user.id)}
    items = []
    for n in range(weeks.current_week_no(p), 0, -1):
        working = [r for r in weeks.rows_for(p, n, by) if r.works]
        wk = recs.get(n)
        items.append(SimpleNamespace(
            n=n, start=weeks.week_start(p, n), end=weeks.week_end(p, n),
            done=sum(1 for r in working if r.entry), total=len(working),
            label=weeks.STATUS_LABEL[wk.status] if wk else "Draft"))
        if limit and len(items) >= limit:
            break
    return items, by, recs


@bp.route("/home")
@role_required("student")
def home():
    p = current_user.placement
    ctx = {"p": p, "today": weeks.today(), "greeting": weeks.greeting()}
    if p:
        recent, by, _ = _week_items(p, limit=3)
        n = weeks.current_week_no(p)
        rows = weeks.rows_for(p, n, by)
        working = [r for r in rows if r.works]
        returned = [SimpleNamespace(e=e, n=weeks.week_no_for(p, e.work_date))
                    for e in Entry.query.filter_by(student_id=current_user.id, status="returned")
                                        .order_by(Entry.work_date)]
        ctx.update(n=n, rows=rows, start=weeks.week_start(p, n), end=weeks.week_end(p, n),
                   cons=weeks.consistency(p, by), not_started=weeks.today() < p.start_date,
                   wk_done=sum(1 for r in working if r.entry), wk_total=len(working),
                   today_row=next((r for r in rows if r.date == weeks.today()), None),
                   recent=recent, returned=returned)
    return render_template("student/home.html", **ctx)


@bp.route("/logbook")
@role_required("student")
@placement_required
def my_logbook():
    p = current_user.placement
    items, by, recs = _week_items(p)
    stats = SimpleNamespace(started=len(items), recorded=len(by),
                            approved=sum(1 for w in recs.values() if w.status == "approved"))
    return render_template("student/my_logbook.html", p=p, items=items, stats=stats)

@bp.route("/details")
@role_required("student")
def logbook_details():
    return render_template("student/logbook_details.html", p=current_user.placement)


# ---- weekly pages --------------------------------------------------------

@bp.route("/week/<int:n>")
@role_required("student")
@placement_required
def week_chart(n):
    p = current_user.placement
    _check_week(p, n)
    wk = weeks.get_week(current_user, n)
    rows = weeks.rows_for(p, n, weeks.entries_by_date(current_user))
    return render_template("student/week_chart.html", wk=wk, rows=rows, n=n,
                           start=weeks.week_start(p, n), end=weeks.week_end(p, n),
                           total=weeks.current_week_no(p), label=weeks.STATUS_LABEL[wk.status])


@bp.route("/week/<int:n>/sketches", methods=["GET", "POST"])
@role_required("student")
@placement_required
def week_sketches(n):
    p = current_user.placement
    _check_week(p, n)
    wk = weeks.get_week(current_user, n)
    locked = wk.status in ("submitted", "approved")
    form = SketchForm(obj=wk)
    if request.method == "GET" and not form.typed_name.data:
        form.typed_name.data = current_user.full_name

    if request.method == "POST":
        if locked:
            flash("This week has been sent to your supervisor and can't be changed.", "error")
            return redirect(url_for("student.week_sketches", n=n))
        if form.validate_on_submit():
            problems = []
            for a in wk.attachments:
                a.caption = (request.form.get(f"caption_{a.id}") or "").strip()[:200]
            for f in request.files.getlist("files"):
                if not f or not f.filename:
                    continue
                if len(wk.attachments) >= 6:
                    problems.append("You can attach up to 6 images per week.")
                    break
                try:
                    name, size = uploads.save_image(f)
                    wk.attachments.append(Attachment(stored_name=name, size=size))
                except ValueError as exc:
                    problems.append(f"{f.filename}: {exc}")
            wk.report = form.report.data or ""
            wk.typed_name = (form.typed_name.data or "").strip() or wk.typed_name
            db.session.commit()
            if request.form.get("action") == "submit":
                try:
                    approvals.submit_week(current_user, wk, form.typed_name.data, form.confirm.data)
                    flash(f"Week {n} was sent to your supervisor.", "success")
                    return redirect(url_for("student.week_chart", n=n))
                except RuleError as exc:
                    flash(str(exc), "error")
            else:
                flash("Saved.", "success")
            for m in problems:
                flash(m, "error")
            return redirect(url_for("student.week_sketches", n=n))
        flash("Please check the form and try again.", "error")

    return render_template("student/sketches_signoff.html", wk=wk, form=form, n=n, locked=locked,
                           end=weeks.week_end(p, n), today=weeks.today(), total=weeks.current_week_no(p))


@bp.route("/sketch/<int:att_id>/delete", methods=["POST"])
@role_required("student")
def sketch_delete(att_id):
    a = db.session.get(Attachment, att_id)
    if not a or a.week.student_id != current_user.id:
        abort(404)
    n = a.week.week_no
    if a.week.status in ("submitted", "approved"):
        flash("This week has been sent to your supervisor and can't be changed.", "error")
    else:
        uploads.remove(a.stored_name)
        db.session.delete(a)
        db.session.commit()
        flash("Image removed.", "success")
    return redirect(url_for("student.week_sketches", n=n))


# ---- daily entries ---------------------------------------------------------

@bp.route("/entry/<day>")
@role_required("student")
@placement_required
def entry_open(day):
    d = _day(day)
    e = Entry.query.filter_by(student_id=current_user.id, work_date=d).first()
    if not e:
        return redirect(url_for("student.entry_write", day=day))
    p = current_user.placement
    n = weeks.week_no_for(p, d)
    wk = weeks.get_week(current_user, n)
    locked = e.sealed or wk.status in ("submitted", "approved")
    return render_template("student/entry_detail.html", e=e, n=n, label=_label(d), locked=locked,
                           draft_keys=f"draft:{current_user.id}:{day} amend:{current_user.id}:{day}")


@bp.route("/entry/<day>/write", methods=["GET", "POST"])
@role_required("student")
@placement_required
def entry_write(day):
    d = _day(day)
    p = current_user.placement
    if Entry.query.filter_by(student_id=current_user.id, work_date=d).first():
        return redirect(url_for("student.entry_open", day=day))
    try:
        check_writable(current_user, d)
    except RuleError as exc:
        flash(str(exc), "error")
        return redirect(_back(p, d))
    form = EntryForm()
    if form.validate_on_submit():
        try:
            _, created = record_entry(current_user, d, form.body.data)
        except RuleError as exc:
            flash(str(exc), "error")
            return redirect(_back(p, d))
        flash("Your entry is recorded." if created else "That entry was already recorded.", "success")
        return redirect(url_for("student.entry_open", day=day))
    return render_template("student/entry_write.html", form=form, d=d, label=_label(d), amend=False,
                           late=d < weeks.today(), n=weeks.week_no_for(p, d),
                           draft_key=f"draft:{current_user.id}:{day}", min_chars=MIN_CHARS, max_chars=MAX_CHARS)


@bp.route("/entry/<day>/amend", methods=["GET", "POST"])
@role_required("student")
@placement_required
def entry_amend(day):
    d = _day(day)
    p = current_user.placement
    e = Entry.query.filter_by(student_id=current_user.id, work_date=d).first()
    if not e:
        abort(404)
    form = EntryForm(obj=e)
    if form.validate_on_submit():
        try:
            amend_entry(e, form.body.data)
            flash("Your amendment was saved. The earlier version is kept in the history.", "success")
            return redirect(url_for("student.entry_open", day=day))
        except RuleError as exc:
            flash(str(exc), "error")
    return render_template("student/entry_write.html", form=form, d=d, label=_label(d), amend=True,
                           late=False, n=weeks.week_no_for(p, d),
                           draft_key=f"amend:{current_user.id}:{day}", min_chars=MIN_CHARS, max_chars=MAX_CHARS)


# ---- supervisor link (unchanged) ----------------------------------------

@bp.route("/supervisor", methods=["GET", "POST"])
@role_required("student")
def supervisor():
    if request.method == "POST":
        if current_user.industry_supervisor_id:
            flash("You already have a supervisor.", "error")
        else:
            svc.create_link("supervisor", current_user,
                            label=f"Supervisor for {current_user.full_name}",
                            days=14, max_uses=1, student=current_user)
            db.session.commit()
        return redirect(url_for("student.supervisor"))

    link = None if current_user.industry_supervisor_id else svc.active_supervisor_link(current_user)
    url = wa = None
    if link:
        url = svc.link_url(link)
        wa = svc.whatsapp_url(
            f"Hello, this is {current_user.full_name} ({current_user.matric_number}). "
            "Please create your supervisor account on the SIWES Logbook so you can review "
            f"and approve my weekly logbook:\n{url}")
    return render_template("student/supervisor.html", link=link, url=url, wa=wa)


@bp.route("/supervisor/cancel", methods=["POST"])
@role_required("student")
def supervisor_cancel():
    link = svc.active_supervisor_link(current_user)
    if link:
        link.closed_at = svc.now()
        db.session.commit()
        flash("That link no longer works.", "success")
    return redirect(url_for("student.supervisor"))