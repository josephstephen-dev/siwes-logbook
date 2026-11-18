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
        abort(404)                      # already claimed: this page no longer exists
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

@bp.route("/manifest.webmanifest")
def manifest():
    name = current_app.config["APP_NAME"]
    data = {"name": name, "short_name": "SIWES", "start_url": "/", "scope": "/", "display": "standalone",
            "background_color": "#f6f7f5", "theme_color": "#1b5e44",
            "icons": [{"src": "/static/img/icon-192.png", "sizes": "192x192", "type": "image/png"},
                      {"src": "/static/img/icon-512.png", "sizes": "512x512", "type": "image/png"}]}
    return Response(json.dumps(data), mimetype="application/manifest+json")


@bp.route("/sw.js")
def service_worker():
    resp = send_from_directory(current_app.static_folder, "js/sw.js", mimetype="application/javascript")
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@bp.route("/offline")
def offline():
    return render_template("meta/offline.html")