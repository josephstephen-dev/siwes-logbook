import hmac

from flask import Blueprint, abort, current_app, flash, redirect, render_template, url_for

from ..extensions import limiter
from ..forms.invite_forms import FirstRunForm
from ..models.user import User
from ..services import invitations as svc
from ..services.passwords import password_problems

bp = Blueprint("setup", __name__)


def _limit():
    return current_app.config["STAFF_LIMIT"]


@bp.route("/setup", methods=["GET", "POST"])
@limiter.limit(_limit, methods=["POST"])
def first_run():
    if User.query.filter_by(role="coordinator").first():
        abort(404)
    expected = (current_app.config.get("SETUP_TOKEN") or "").strip()
    form = FirstRunForm()
    problems, error = [], None
    if expected and form.validate_on_submit():
        if not hmac.compare_digest(form.token.data.strip().encode(), expected.encode()):
            error = "That setup key isn't valid."
        else:
            problems = password_problems(form.password.data)
            if not problems:
                error = svc.duplicate_problem(email=form.email.data)
            if not problems and not error:
                svc.register_first_coordinator(form.data)
                flash("Your site is ready. Sign in as coordinator.", "success")
                return redirect(url_for("auth.sign_in_coordinator"))
    return render_template("setup/first_run.html", form=form, error=error,
                           problems=problems, enabled=bool(expected))