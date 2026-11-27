import os
from flask import Flask, request, session, redirect, url_for
from .config import CONFIGS
from .extensions import db, migrate, login_manager, csrf, limiter
from flask_login import current_user


def create_app(config_name=None):
    # On Vercel (which sets VERCEL=1) always run in production mode unless told otherwise.
    # Dev mode there would turn every error into the blank "This page is unavailable" screen.
    config_name = config_name or os.environ.get("APP_ENV") or ("prod" if os.environ.get("VERCEL") else "dev")
    app = Flask(__name__, instance_path="/tmp/instance" if os.environ.get("VERCEL") else None)
    app.config.from_object(CONFIGS[config_name])
    if config_name == "prod":
        if app.config["MAIL_BACKEND"] != "smtp":
            raise RuntimeError("Set MAIL_BACKEND=smtp (and the MAIL_* settings) in production.")
        # Refuse to start with unsafe settings
        for key in ("SECRET_KEY", "HMAC_KEY"):
            if app.config[key].startswith("dev-only"):
                raise RuntimeError(f"{key} must be set to a long random value in production.")
        if not app.config["SQLALCHEMY_DATABASE_URI"]:
            raise RuntimeError("DATABASE_URL is not set.")
        # Behind Nginx, trust its headers so rate limits see each visitor's real IP
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    from . import models  # noqa: F401
    from .routes import register_blueprints
    register_blueprints(app)

    from .routes.errors import register_error_handlers
    register_error_handlers(app)

    from . import cli
    cli.register(app)

    @login_manager.user_loader
    def load_user(user_id):
        from .models.user import User
        user = db.session.get(User, int(user_id))
        # a deactivated person is signed out on their next request
        return user if user and user.status == "active" else None

    @login_manager.unauthorized_handler
    def unauthorized():
        session["next"] = request.full_path.rstrip("?")
        if request.cookies.get("siwes_seen"):
            return redirect(url_for("auth.session_expired"))
        return redirect(url_for("auth.role_chooser", notice="continue"))

    PRIVATE = ("/student/", "/supervisor/", "/coordinator/", "/files/", "/join/", "/setup",
               "/reset-password/", "/sign-in/", "/forgot-password", "/session-expired",
               "/signed-out", "/help", "/sign-out")

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        resp.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if request.is_secure:
            resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        path = request.path
        if path.startswith(PRIVATE) or (path.startswith("/v/") and path != "/v/check"):
            resp.headers["X-Robots-Tag"] = "noindex, nofollow"     # keep private pages out of search
        if current_user.is_authenticated and not path.startswith("/static/"):
            resp.headers.setdefault("Cache-Control", "no-store")   # Back button shows nothing after sign-out
        return resp

    from .services.weeks import to_lagos
    app.jinja_env.filters["lagos"] = to_lagos
    from . import jobs
    jobs.register(app)

    if config_name == "prod" and app.config["LOG_FILE"]:
        import logging
        from logging.handlers import RotatingFileHandler
        h = RotatingFileHandler(app.config["LOG_FILE"], maxBytes=2_000_000, backupCount=5)
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        app.logger.addHandler(h)
        app.logger.setLevel(logging.INFO)

    from .services import weeks as weeks_svc

    def initials(name):
        return "".join(w[0] for w in (name or "?").split()[:2]).upper()

    def placement_card(user):
        p = getattr(user, "placement", None)
        if not p:
            return None
        return {"company": p.company_name, "week": weeks_svc.current_week_no(p), "total": p.total_weeks}

    app.jinja_env.globals.update(initials=initials, placement_card=placement_card)

    @app.context_processor
    def inject_globals():
        return {"app_name": app.config["APP_NAME"], "institution": app.config["INSTITUTION_NAME"]}

    return app