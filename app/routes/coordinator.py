from types import SimpleNamespace

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for, Response
from flask_login import current_user
from sqlalchemy import or_

from ..extensions import db
from ..forms.coordinator_forms import LinkForm, PlacementForm
from ..models.join_link import JoinLink
from ..models.placement import Placement
from ..models.user import User
from ..services import invitations as svc, staff_code
from ..services.permissions import role_required
from ..services.tokens import make_reset_token, make_verify_token
from ..services import dashboard as dashboard_svc
import csv
import io

from ..forms.coordinator_forms import PlacementEditForm
from ..models.entry import Entry
from ..models.week import WeekRecord
from ..services import weeks

bp = Blueprint("coordinator", __name__)
PER_PAGE = 25


def _person(user_id, *roles):
    user = db.session.get(User, user_id)
    if not user or user.role not in roles:
        abort(404)
    return user


# ---- dashboard ---------------------------------------------------------

def _dash_args():
    return dict(q=request.args.get("q", "").strip().lower(),
                company=request.args.get("company", ""),
                supervisor_id=request.args.get("supervisor", type=int),
                sort=request.args.get("sort", "risk"),
                risk=request.args.get("risk", ""),
                only_pending=request.args.get("pending") == "1")


@bp.route("/dashboard")
@role_required("coordinator")
def dashboard():
    args = _dash_args()
    rows, stats, companies, sups = dashboard_svc.build(**args)
    per = 25
    page = max(1, request.args.get("page", 1, type=int))
    pages = max(1, -(-len(rows) // per))
    page = min(page, pages)
    p = SimpleNamespace(items=rows[(page - 1) * per: page * per], page=page, pages=pages,
                        total=len(rows), first=(page - 1) * per + 1 if rows else 0,
                        last=min(page * per, len(rows)))
    base = {k: v for k, v in request.args.to_dict().items() if k != "page"}
    sort_urls = {k: url_for("coordinator.dashboard", **{**base, "sort": k})
                 for k in ("risk", "consistency", "name")}
    waiting = SimpleNamespace(
        staff=User.query.filter_by(role="coordinator", status="pending").count(),
        supervisors=User.query.filter(User.role == "supervisor", User.status == "active",
                                      User.verified_at.is_(None)).count(),
        unplaced=User.query.filter(User.role == "student", User.status == "active",
                                   User.id.not_in(db.select(Placement.student_id))).count())
    return render_template("coordinator/dashboard.html", p=p, stats=stats, companies=companies,
                           sups=sups, waiting=waiting, sort_urls=sort_urls,
                           export_url=url_for("coordinator.dashboard_csv", **base),
                           q=args["q"], company=args["company"], sort=args["sort"],
                           risk=args["risk"], only_pending=args["only_pending"],
                           sup=args["supervisor_id"])


def _csv_safe(value):
    """Stops a name like =HYPERLINK(...) from running as a formula when opened in Excel."""
    s = "" if value is None else str(value)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


@bp.route("/dashboard.csv")
@role_required("coordinator")
def dashboard_csv():
    rows, *_ = dashboard_svc.build(**_dash_args())
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Student", "Matric number", "Company", "Industry supervisor", "Consistency %",
                "Last entry", "Pending approvals", "Late entries", "Open flags", "Risk"])
    for r in rows:
        w.writerow([_csv_safe(x) for x in (
            r.s.full_name, r.s.matric_number, r.company, r.sup.full_name if r.sup else "",
            r.pct, r.last, r.pending, r.late, r.flags, r.risk)])
    return Response("\ufeff" + buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=siwes-dashboard-{weeks.today()}.csv"})
# ---- student sign-up link ----------------------------------------------

@bp.route("/student-link", methods=["GET", "POST"])
@role_required("coordinator")
def student_link():
    form = LinkForm()
    if form.validate_on_submit():
        svc.create_link("student", current_user, label=form.label.data.strip(),
                        days=form.days.data, max_uses=form.max_uses.data or None)
        db.session.commit()
        flash("Your sign-up link is ready. Copy it or share it on WhatsApp.", "success")
        return redirect(url_for("coordinator.student_link"))
    rows = []
    for link in JoinLink.query.filter_by(kind="student").order_by(JoinLink.id.desc()).all():
        url = svc.link_url(link)
        rows.append(SimpleNamespace(
            link=link, url=url,
            wa=svc.whatsapp_url("SIWES Logbook: create your student account here "
                                f"(once only, have your matric number ready):\n{url}")))
    return render_template("coordinator/invite_students.html", form=form, rows=rows)


def _student_link(link_id):
    link = db.session.get(JoinLink, link_id)
    if not link or link.kind != "student":
        abort(404)
    return link


@bp.route("/student-link/<int:link_id>/close", methods=["POST"])
@role_required("coordinator")
def link_close(link_id):
    _student_link(link_id).closed_at = svc.now()
    db.session.commit()
    flash("That link is closed. Nobody can sign up with it any more.", "success")
    return redirect(url_for("coordinator.student_link"))


@bp.route("/student-link/<int:link_id>/reopen", methods=["POST"])
@role_required("coordinator")
def link_reopen(link_id):
    svc.reopen(_student_link(link_id))
    db.session.commit()
    flash("That link works again.", "success")
    return redirect(url_for("coordinator.student_link"))


# ---- supervisors -------------------------------------------------------

@bp.route("/supervisors")
@role_required("coordinator")
def supervisors():
    rows = (User.query.filter_by(role="supervisor")
            .order_by(User.verified_at.is_(None).desc(), User.created_at.desc()).all())
    return render_template("coordinator/supervisors.html", rows=rows)


@bp.route("/supervisors/<int:user_id>/confirm", methods=["POST"])
@role_required("coordinator")
def supervisor_confirm(user_id):
    user = _person(user_id, "supervisor")
    user.verified_at = svc.now()
    user.verified_by_id = current_user.id
    db.session.commit()
    flash(f"{user.full_name}'s identity is confirmed.", "success")
    return redirect(url_for("coordinator.supervisors"))


@bp.route("/supervisors/<int:user_id>/remove", methods=["POST"])
@role_required("coordinator")
def supervisor_remove(user_id):
    user = _person(user_id, "supervisor")
    for student in list(user.supervised_students):
        student.industry_supervisor_id = None        # students can invite someone else
    user.status = "deactivated"
    user.verified_at = None
    db.session.commit()
    flash(f"{user.full_name} was removed. Their students can invite another supervisor.", "success")
    return redirect(url_for("coordinator.supervisors"))


# ---- staff (other coordinators) ----------------------------------------

def _staff_page(new_code=None):
    rows = (User.query.filter_by(role="coordinator")
            .order_by((User.status == "pending").desc(), User.full_name).all())
    return render_template("coordinator/staff.html", rows=rows, new_code=new_code,
                           code_until=staff_code.code_expiry(),
                           staff_link=svc.public_url("invite.join_staff"))


@bp.route("/staff")
@role_required("coordinator")
def staff():
    return _staff_page()


@bp.route("/staff/code/new", methods=["POST"])
@role_required("coordinator")
def staff_code_new():
    # Rendered directly (no redirect) so the code never travels through a cookie
    return _staff_page(new_code=staff_code.new_code(days=7))


@bp.route("/staff/code/revoke", methods=["POST"])
@role_required("coordinator")
def staff_code_revoke():
    staff_code.revoke_code()
    flash("The staff code is switched off. Nobody can sign up as a coordinator until you generate a new one.", "success")
    return redirect(url_for("coordinator.staff"))


@bp.route("/staff/<int:user_id>/reset-link", methods=["POST"])
@role_required("coordinator")
def staff_reset_link(user_id):
    user = _person(user_id, "coordinator")
    if user.status != "active" or user.id == current_user.id:
        flash("A reset link can only be made for another active coordinator.", "error")
    else:
        flash(svc.public_url("auth.reset_password", token=make_reset_token(user)), "link")
    return redirect(url_for("coordinator.staff"))


@bp.route("/staff/<int:user_id>/approve", methods=["POST"])
@role_required("coordinator")
def staff_approve(user_id):
    user = _person(user_id, "coordinator")
    if user.status == "pending":
        user.status = "active"
        user.verified_at = svc.now()
        user.verified_by_id = current_user.id
        db.session.commit()
        flash(f"{user.full_name} can now sign in as a coordinator.", "success")
    return redirect(url_for("coordinator.staff"))


@bp.route("/staff/<int:user_id>/deactivate", methods=["POST"])
@role_required("coordinator")
def staff_deactivate(user_id):
    user = _person(user_id, "coordinator")
    if user.id == current_user.id:
        flash("You can't deactivate your own account.", "error")
    else:
        user.status = "deactivated"
        db.session.commit()
        flash(f"{user.full_name} was deactivated.", "success")
    return redirect(url_for("coordinator.staff"))


@bp.route("/staff/<int:user_id>/reactivate", methods=["POST"])
@role_required("coordinator")
def staff_reactivate(user_id):
    user = _person(user_id, "coordinator")
    user.status = "active"
    db.session.commit()
    flash(f"{user.full_name} was reactivated.", "success")
    return redirect(url_for("coordinator.staff"))


# ---- accounts (students and supervisors) --------------------------------

@bp.route("/accounts")
@role_required("coordinator")
def accounts():
    q = request.args.get("q", "").strip()
    role = request.args.get("role", "")
    status = request.args.get("status", "")
    query = User.query.filter(User.role.in_(["student", "supervisor"]))
    if q:
        like = f"%{q}%"
        query = query.filter(or_(User.full_name.ilike(like), User.email.ilike(like),
                                 User.matric_number.ilike(like)))
    if role in ("student", "supervisor"):
        query = query.filter(User.role == role)
    if status in ("active", "deactivated", "unverified"):
        query = query.filter(User.status == status)
    p = query.order_by(User.full_name).paginate(
        page=request.args.get("page", 1, type=int), per_page=PER_PAGE, error_out=False)

    base = User.query.filter(User.role.in_(["student", "supervisor"]))
    counts = SimpleNamespace(
        total=base.count(),
        students=base.filter(User.role == "student").count(),
        supervisors=base.filter(User.role == "supervisor").count(),
        active=base.filter(User.status == "active").count(),
        inactive=base.filter(User.status == "deactivated").count(),
        unconfirmed=base.filter(User.status == "unverified").count(),
        awaiting=base.filter(User.role == "supervisor", User.status == "active",
                             User.verified_at.is_(None)).count())
    return render_template("coordinator/accounts.html", p=p, counts=counts,
                           q=q, role=role, status=status)


def _account(user_id):
    return _person(user_id, "student", "supervisor")


@bp.route("/accounts/<int:user_id>/reset-link", methods=["POST"])
@role_required("coordinator")
def account_reset_link(user_id):
    user = _account(user_id)
    if user.status != "active":
        flash("Reactivate this account first.", "error")
    else:
        flash(svc.public_url("auth.reset_password", token=make_reset_token(user)), "link")
    return redirect(url_for("coordinator.accounts"))


@bp.route("/accounts/<int:user_id>/deactivate", methods=["POST"])
@role_required("coordinator")
def account_deactivate(user_id):
    user = _account(user_id)
    user.status = "deactivated"
    db.session.commit()
    flash(f"{user.full_name} was deactivated and can no longer sign in.", "success")
    return redirect(url_for("coordinator.accounts"))


@bp.route("/accounts/<int:user_id>/verify-link", methods=["POST"])
@role_required("coordinator")
def account_verify_link(user_id):
    user = _person(user_id, "student", "supervisor", "coordinator")
    if user.status != "unverified":
        flash("This account is already confirmed.", "error")
    else:
        flash(svc.public_url("invite.verify_email", token=make_verify_token(user)), "link")
    return redirect(request.referrer or url_for("coordinator.accounts"))


@bp.route("/accounts/<int:user_id>/reactivate", methods=["POST"])
@role_required("coordinator")
def account_reactivate(user_id):
    user = _account(user_id)
    # someone who never confirmed their email goes back to "unconfirmed", not straight to active
    user.status = "active" if (user.last_sign_in_at or user.email_verified_at) else "unverified"
    db.session.commit()
    flash(f"{user.full_name} was reactivated.", "success")
    return redirect(url_for("coordinator.accounts"))


@bp.route("/accounts/<int:user_id>/remove", methods=["POST"])
@role_required("coordinator")
def account_remove(user_id):
    """Unconfirmed accounts, or a student who signed up with someone else's matric number."""
    user = _account(user_id)
    if not (user.status == "unverified" or (user.role == "student" and not user.placement)):
        flash("Only unconfirmed accounts, or students without a placement, can be removed. Deactivate this account instead.", "error")
    else:
        User.query.filter_by(industry_supervisor_id=user.id).update({"industry_supervisor_id": None})
        JoinLink.query.filter(or_(JoinLink.student_id == user.id,
                                  JoinLink.created_by_id == user.id)).delete(synchronize_session=False)
        db.session.delete(user)
        db.session.commit()
        flash("The account was removed.", "success")
    return redirect(url_for("coordinator.accounts"))

# ---- placements --------------------------------------------------------

@bp.route("/placements")
@role_required("coordinator")
def placements():
    rows = (Placement.query.join(User, Placement.student_id == User.id)
            .order_by(User.full_name).all())
    return render_template("coordinator/placements.html", rows=rows)


@bp.route("/placements/new", methods=["GET", "POST"])
@role_required("coordinator")
def placement_new():
    form = PlacementForm()
    students = (User.query.filter(User.role == "student", User.status == "active",
                                  User.id.not_in(db.select(Placement.student_id)))
                .order_by(User.full_name).all())
    form.student.choices = [(s.id, f"{s.full_name} · {s.matric_number}") for s in students]
    if form.validate_on_submit():
        if form.end_date.data <= form.start_date.data:
            flash("The end date must be after the start date.", "error")
        else:
            db.session.add(Placement(
                student_id=form.student.data, company_name=form.company_name.data.strip(),
                company_address=form.company_address.data.strip(),
                start_date=form.start_date.data, end_date=form.end_date.data,
                school_supervisor=form.school_supervisor.data.strip(),
                working_days=",".join(sorted(form.working_days.data))))
            db.session.commit()
            flash("Placement saved.", "success")
            return redirect(url_for("coordinator.placements"))
    return render_template("coordinator/placement_setup.html", form=form, p=None, editing=False,
                           locked_start=False, no_students=not students)

from . import coordinator_ops  # noqa: E402,F401

@bp.route("/placements/<int:pid>/edit", methods=["GET", "POST"])
@role_required("coordinator")
def placement_edit(pid):
    p = db.session.get(Placement, pid)
    if not p:
        abort(404)
    form = PlacementEditForm(obj=p)
    if request.method == "GET":
        form.working_days.data = p.working_days.split(",")
    dates = [e.work_date for e in Entry.query.filter_by(student_id=p.student_id)]
    locked = bool(dates) or WeekRecord.query.filter_by(student_id=p.student_id).first() is not None
    if form.validate_on_submit():
        start, end = form.start_date.data, form.end_date.data
        days = {int(x) for x in form.working_days.data}
        if end <= start:
            flash("The end date must be after the start date.", "error")
        elif locked and start != p.start_date:
            flash("The start date cannot be changed once the student has started their logbook.", "error")
        elif dates and (min(dates) < start or max(dates) > end):
            flash("Some entries fall outside these dates, so the change cannot be applied.", "error")
        elif any(d.weekday() not in days for d in dates):
            flash("A working day that already has an entry cannot be removed.", "error")
        else:
            p.company_name = form.company_name.data.strip()
            p.company_address = form.company_address.data.strip()
            p.school_supervisor = form.school_supervisor.data.strip()
            p.start_date, p.end_date = start, end
            p.working_days = ",".join(sorted(form.working_days.data))
            db.session.commit()
            flash("Placement updated.", "success")
            return redirect(url_for("coordinator.placements"))
    return render_template("coordinator/placement_setup.html", form=form, p=p, editing=True,
                           locked_start=locked, no_students=False)