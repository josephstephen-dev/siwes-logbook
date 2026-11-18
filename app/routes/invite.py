from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, session, url_for)
from flask_login import current_user, logout_user
from sqlalchemy import func

from ..extensions import limiter
from ..forms.invite_forms import (ResendForm, StaffSignUpForm, StudentSignUpForm,
                                  SupervisorSignUpForm)
from ..models.user import User
from ..services import invitations as svc
from ..services import staff_code
from ..services.notifications import send_verify_email
from ..services.passwords import password_problems
from ..services.permissions import HOME_ENDPOINT
from ..services.tokens import read_verify_token


bp = Blueprint("invite", __name__)


def _join_limit():
    return current_app.config["JOIN_LIMIT"]


def _staff_limit():
    return current_app.config["STAFF_LIMIT"]


def _gone(link, kind="student"):
    if link is None:
        reason = "invalid"
    else:
        reason = {"Closed": "closed", "Expired": "expired",
                  "Full": "full" if kind == "student" else "used"}.get(link.state, "used")
    return render_template("invite/invalid_link.html", reason=reason), 410


def _already_signed_in():
    return render_template("invite/already_signed_in.html", next_url=request.path,
                           home_url=url_for(HOME_ENDPOINT[current_user.role]))


@bp.route("/switch", methods=["POST"])
def switch_account():
    """Sign out, then continue to the sign-up link that was opened."""
    nxt = request.form.get("next", "")
    logout_user()
    session.clear()
    if nxt.startswith("/join/") and "//" not in nxt and "\\" not in nxt:
        return redirect(nxt)
    return redirect(url_for("auth.role_chooser"))


@bp.route("/student/<token>", methods=["GET", "POST"])
@limiter.limit(_join_limit, methods=["POST"])
def join_student(token):
    link = svc.find_link(token, "student")
    if not link or not link.is_open:
        return _gone(link)
    if current_user.is_authenticated:
        return _already_signed_in()
    form = StudentSignUpForm()
    problems, error = [], None
    if form.validate_on_submit():
        problems = password_problems(form.password.data)
        if not problems:
            error = svc.duplicate_problem(form.matric_number.data, form.email.data, form.phone.data)
        if not problems and not error:
            _, mail_ok = svc.register_student(link, form.data)
            session["verify_email"] = form.email.data.strip().lower()
            session["mail_failed"] = not mail_ok
            return redirect(url_for("invite.complete", role="student"))
    return render_template("invite/student_setup.html", form=form, error=error, problems=problems)


@bp.route("/supervisor/<token>", methods=["GET", "POST"])
@limiter.limit(_join_limit, methods=["POST"])
def join_supervisor(token):
    link = svc.find_link(token, "supervisor")
    if not link or not link.is_open or link.student.industry_supervisor_id:
        return _gone(link, "supervisor")
    student = link.student

    if current_user.is_authenticated:
        if current_user.role != "supervisor":
            return _already_signed_in()
        if request.method == "POST":               # an existing supervisor adds another student
            svc.attach_supervisor(link, current_user)
            flash(f"You are now the supervisor of {student.full_name}.", "success")
            return redirect(url_for("supervisor.pending_weeks"))
        return render_template("invite/supervisor_confirm.html", student=student)

    form = SupervisorSignUpForm()
    problems, error = [], None
    if form.validate_on_submit():
        problems = password_problems(form.password.data)
        if not problems:
            error = svc.duplicate_problem(email=form.email.data, phone=form.phone.data)
        if not problems and not error:
            _, mail_ok = svc.register_supervisor(link, form.data)
            session["verify_email"] = form.email.data.strip().lower()
            session["mail_failed"] = not mail_ok
            return redirect(url_for("invite.complete", role="supervisor"))
    return render_template("invite/supervisor_setup.html", form=form, student=student,
                           token=token, error=error, problems=problems)


@bp.route("/supervisor/<token>/sign-in")
def supervisor_signin(token):
    """A supervisor who already has an account: sign in, then come back to confirm."""
    session["next"] = url_for("invite.join_supervisor", token=token)
    return redirect(url_for("auth.sign_in_supervisor"))


@bp.route("/staff", methods=["GET", "POST"])
@limiter.limit(_staff_limit, methods=["POST"])
def join_staff():
    if current_user.is_authenticated:
        return _already_signed_in()
    enabled = staff_code.code_expiry() is not None
    form = StaffSignUpForm()
    problems, error = [], None
    if enabled and form.validate_on_submit():
        if not staff_code.check_code(form.code.data):
            error = "That staff code isn't valid."
        else:
            problems = password_problems(form.password.data)
            if not problems:
                error = svc.duplicate_problem(email=form.email.data)
            if not problems and not error:
                _, mail_ok = svc.register_staff(form.data)
                session["verify_email"] = form.email.data.strip().lower()
                session["mail_failed"] = not mail_ok
                return redirect(url_for("invite.complete", role="coordinator"))
    return render_template("invite/staff_setup.html", form=form, error=error,
                           problems=problems, enabled=enabled)

@bp.route("/done/<role>")
def complete(role):
    if role not in ("student", "supervisor", "coordinator"):
        return render_template("errors/404.html"), 404
    return render_template("invite/setup_success.html", role=role,
                           email=session.get("verify_email"),
                           mail_failed=session.pop("mail_failed", False))


@bp.route("/verify/<token>")
def verify_email(token):
    user = read_verify_token(token)
    if user is None:
        return render_template("invite/invalid_link.html", reason="verify"), 410
    if user.status == "unverified":
        svc.confirm_email(user)
    return render_template("invite/email_confirmed.html", user=user)


@bp.route("/verify/resend", methods=["GET", "POST"])
@limiter.limit("5 per 15 minutes", methods=["POST"])
def resend_verification():
    form = ResendForm()
    if request.method == "GET" and session.get("verify_email"):
        form.email.data = session["verify_email"]
    sent = False
    if form.validate_on_submit():
        user = User.query.filter(func.lower(User.email) == form.email.data.strip().lower(),
                                 User.status == "unverified").first()
        if user:
            send_verify_email(user)
        sent = True                       # same answer whether or not an account matched
    return render_template("invite/resend.html", form=form, sent=sent)