from datetime import date
from types import SimpleNamespace

from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user

from ..extensions import db
from ..forms.approval_forms import ApproveForm, ReturnForm
from ..models.week import WeekRecord
from ..services import approvals, weeks
from ..services.entries import RuleError
from ..services.permissions import role_required

bp = Blueprint("supervisor", __name__)


def _item(wk):
    p = wk.student.placement
    return SimpleNamespace(wk=wk, start=weeks.week_start(p, wk.week_no), end=weeks.week_end(p, wk.week_no))


def _week(week_id):
    wk = db.session.get(WeekRecord, week_id)
    if not wk or wk.status == "open" or wk.student.industry_supervisor_id != current_user.id:
        abort(404)
    return wk


@bp.route("/weeks")
@role_required("supervisor")
def pending_weeks():
    ids = [s.id for s in current_user.supervised_students]
    waiting, recent = [], []
    if ids:
        base = WeekRecord.query.filter(WeekRecord.student_id.in_(ids))
        waiting = [_item(w) for w in base.filter_by(status="submitted").order_by(WeekRecord.submitted_at)]
        recent = [_item(w) for w in base.filter(WeekRecord.status.in_(["approved", "returned"]))
                  .order_by(WeekRecord.id.desc()).limit(10)]
    return render_template("supervisor/pending_weeks.html", waiting=waiting, recent=recent,
                           students=current_user.supervised_students)


def _render_review(wk, form):
    st, p = wk.student, wk.student.placement
    return render_template(
        "supervisor/week_review.html", wk=wk, st=st, form=form,
        rows=weeks.rows_for(p, wk.week_no, weeks.entries_by_date(st)),
        start=weeks.week_start(p, wk.week_no), end=weeks.week_end(p, wk.week_no),
        can_return=wk.status in ("submitted", "returned"), can_approve=wk.status == "submitted")


@bp.route("/weeks/<int:week_id>")
@role_required("supervisor")
def week_review(week_id):
    wk = _week(week_id)
    return _render_review(wk, ApproveForm(signer_name=current_user.full_name,
                                          designation=current_user.designation))


@bp.route("/weeks/<int:week_id>/approve", methods=["POST"])
@role_required("supervisor")
def week_approve(week_id):
    wk = _week(week_id)
    form = ApproveForm()
    if form.validate_on_submit():
        try:
            approvals.approve_week(current_user, wk, form.comment.data,
                                   form.signer_name.data, form.designation.data)
            return redirect(url_for("supervisor.week_done", week_id=wk.id))
        except RuleError as exc:
            flash(str(exc), "error")
    else:
        flash("Tick the confirmation and fill in your name and designation.", "error")
    return _render_review(wk, form)


@bp.route("/weeks/<int:week_id>/return/<day>", methods=["POST"])
@role_required("supervisor")
def entry_return(week_id, day):
    wk = _week(week_id)
    try:
        d = date.fromisoformat(day)
    except ValueError:
        abort(404)
    form = ReturnForm()
    if form.validate_on_submit():
        try:
            approvals.return_entry(current_user, wk, d, form.comment.data)
            flash("The entry was returned to the student with your comment.", "success")
        except RuleError as exc:
            flash(str(exc), "error")
    else:
        flash("Write a short comment (at least 5 characters) explaining what to correct.", "error")
    return redirect(url_for("supervisor.week_review", week_id=wk.id))


@bp.route("/weeks/<int:week_id>/done")
@role_required("supervisor")
def week_done(week_id):
    wk = _week(week_id)
    if wk.status != "approved":
        return redirect(url_for("supervisor.week_review", week_id=wk.id))
    return render_template("supervisor/approval_done.html", wk=wk)