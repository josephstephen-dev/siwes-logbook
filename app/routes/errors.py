from flask import render_template, request
from flask_login import current_user


def register_error_handlers(app):
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(429)
    def too_many(e):
        endpoint = request.endpoint or ""
        if endpoint.startswith("auth.sign_in_"):
            from .auth import FORMS
            role = endpoint.rsplit("_", 1)[1]
            return render_template(
                f"auth/sign_in_{role}.html", form=FORMS[role](),
                error="Too many attempts. Wait 5 minutes and try again.",
                has_next=False), 429
        return render_template("errors/429.html"), 429

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500