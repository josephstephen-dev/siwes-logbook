from datetime import datetime, timezone
from urllib.parse import urlparse
from flask import (Blueprint, render_template, redirect, url_for, request,
                   session, flash, current_app)
from flask_login import login_user, logout_user, current_user, login_required
from sqlalchemy import func, or_
from ..forms.auth_forms import ResetPasswordForm
from ..services.invitations import normalize_phone
from ..services.notifications import send_reset_email
from ..services.passwords import hash_password, password_problems
from ..services.tokens import read_reset_token
from ..extensions import db, limiter
from ..models.user import User
from ..forms.auth_forms import (StudentSignInForm, SupervisorSignInForm,
                                CoordinatorSignInForm, ForgotPasswordForm)
from ..services.passwords import verify_password
from ..services.permissions import HOME_ENDPOINT

bp = Blueprint("auth", __name__)

FORMS = {
    "student": StudentSignInForm,
    "supervisor": SupervisorSignInForm,
    "coordinator": CoordinatorSignInForm,
}
GENERIC_ERROR = {
    "student": "These details don't match a student account.",
    "supervisor": "These details don't match a supervisor account.",
    "coordinator": "These details don't match a coordinator account.",
}
NOT_ACTIVATED = "Check your invitation link or ask your coordinator."


def find_user(role, ident):
    ident = ident.strip()
    q = User.query.filter_by(role=role)
    if role == "student":
        return q.filter(or_(func.upper(User.matric_number) == ident.upper(),
                            func.lower(User.email) == ident.lower())).first()
    if role == "coordinator":
        return q.filter(func.lower(User.email) == ident.lower()).first()
    phone = normalize_phone(ident) if "@" not in ident else None
    return q.filter(or_(func.lower(User.email) == ident.lower(),
                        User.phone == phone)).first()


def safe_next():
    nxt = session.pop("next", None)
    if nxt and not urlparse(nxt).netloc and nxt.startswith("/"):
        return nxt
    return None


def home_for(user):
    return url_for(HOME_ENDPOINT[user.role])


@bp.route("/")
def role_chooser():
    if current_user.is_authenticated:
        return redirect(home_for(current_user))
    needs_setup = User.query.filter_by(role="coordinator").first() is None
    return render_template("auth/role_chooser.html",
                           notice=request.args.get("notice"), needs_setup=needs_setup)


def _sign_in(role, template):
    if current_user.is_authenticated:
        return redirect(home_for(current_user))

    form = FORMS[role]()
    error, resend = None, False
    if form.validate_on_submit():
        user = find_user(role, form.identifier.data)
        stored = user.password_hash if user else None
        ok = verify_password(stored, form.password.data)

        if ok and user.status == "active":
            login_user(user, remember=form.remember.data)
            session.permanent = True
            user.last_sign_in_at = datetime.now(timezone.utc)
            db.session.commit()
            resp = redirect(safe_next() or home_for(user))
            resp.set_cookie("siwes_seen", "1", max_age=60 * 60 * 24 * 30,
                            httponly=True, samesite="Lax")
            return resp

        if ok and user.status == "unverified":
            error = "Confirm your email first. We sent you a link when you signed up."
            resend = True
        elif ok and user.status == "pending":
            error = "Your account is waiting for approval by another coordinator."
        else:
            # same message for wrong password, unknown account, wrong role
            error = GENERIC_ERROR[role]

    return render_template(template, form=form, error=error, resend=resend,
                           has_next=bool(session.get("next")))


@bp.route("/sign-in/student", methods=["GET", "POST"])
@limiter.limit(lambda: current_app.config["SIGNIN_LIMIT"], methods=["POST"])
def sign_in_student():
    return _sign_in("student", "auth/sign_in_student.html")


@bp.route("/sign-in/supervisor", methods=["GET", "POST"])
@limiter.limit(lambda: current_app.config["SIGNIN_LIMIT"], methods=["POST"])
def sign_in_supervisor():
    return _sign_in("supervisor", "auth/sign_in_supervisor.html")


@bp.route("/sign-in/coordinator", methods=["GET", "POST"])
@limiter.limit(lambda: current_app.config["SIGNIN_LIMIT"], methods=["POST"])
def sign_in_coordinator():
    return _sign_in("coordinator", "auth/sign_in_coordinator.html")


@bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per 15 minutes", methods=["POST"])
def forgot_password():
    form = ForgotPasswordForm()
    sent = False
    if form.validate_on_submit():
        ident = form.identifier.data.strip()
        user = User.query.filter(
            User.status == "active",
            or_(func.upper(User.matric_number) == ident.upper(),
                func.lower(User.email) == ident.lower())).first()
        if user and user.email:
            send_reset_email(user)
        sent = True            # same answer whether or not an account matched
    return render_template("auth/forgot_password.html", form=form, sent=sent)


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
@limiter.limit("10 per 15 minutes", methods=["POST"])
def reset_password(token):
    user = read_reset_token(token)
    if not user:
        return render_template("invite/invalid_link.html", reason="expired"), 410
    form = ResetPasswordForm()
    problems = []
    if form.validate_on_submit():
        problems = password_problems(form.password.data)
        if not problems:
            user.password_hash = hash_password(form.password.data)
            db.session.commit()
            flash("Your password has been changed. Sign in with your new password.", "success")
            return redirect(url_for(f"auth.sign_in_{user.role}"))
    return render_template("auth/reset_password.html", form=form, problems=problems)

@bp.route("/session-expired")
def session_expired():
    return render_template("auth/session_expired.html")


@bp.route("/sign-out", methods=["POST"])
@login_required
def sign_out():
    logout_user()
    session.clear()
    resp = redirect(url_for("auth.signed_out"))
    resp.delete_cookie("siwes_seen")
    return resp


@bp.route("/signed-out")
def signed_out():
    return render_template("auth/signed_out.html")