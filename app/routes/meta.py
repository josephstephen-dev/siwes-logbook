import json
import hmac
import os

from flask import (Blueprint, Response, current_app, abort, request, render_template,
                   send_from_directory)
from flask_login import current_user, login_required
from sqlalchemy import text

from ..extensions import db
from ..models.user import User
from ..services.invitations import public_url

bp = Blueprint("meta", __name__)


@bp.route("/robots.txt")
def robots():
    body = "\n".join([
        "User-agent: *",
        "Disallow: /student/", "Disallow: /supervisor/", "Disallow: /coordinator/",
        "Disallow: /join/", "Disallow: /files/", "Disallow: /setup", "Disallow: /reset-password/",
        "Allow: /v/check", "Disallow: /v/",
        f"Sitemap: {public_url('meta.sitemap')}", ""])
    return Response(body, mimetype="text/plain")


@bp.route("/sitemap.xml")
def sitemap():
    urls = [public_url("auth.role_chooser"), public_url("verify.check_pdf"), public_url("meta.privacy")]
    xml = ('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
           + "".join(f"<url><loc>{u}</loc></url>" for u in urls) + "</urlset>")
    return Response(xml, mimetype="application/xml")


@bp.route("/healthz")
def healthz():
    try:
        db.session.execute(text("select 1"))
        User.query.filter_by(role="coordinator").first()      # fails if the tables were never created
        return {"status": "ok"}
    except Exception as e:
        db.session.rollback()
        body = {"status": "error"}
        if os.environ.get("SHOW_BOOT_ERRORS") == "1":          # temporary switch, see deployment steps
            body["detail"] = f"{type(e).__name__}: {str(e)[:400]}"
        return body, 503


@bp.route("/privacy")
def privacy():
    return render_template("meta/privacy.html")


@bp.route("/help")
@login_required
def help_page():
    cfg = current_app.config
    coords = []
    if current_user.role != "coordinator":
        coords = User.query.filter_by(role="coordinator", status="active").order_by(User.full_name).all()
    return render_template("meta/help.html", coords=coords, email=cfg["SUPPORT_EMAIL"],
                           phone=cfg["SUPPORT_PHONE"], wa=cfg["SUPPORT_WHATSAPP"].lstrip("+"))


@bp.route("/manifest.webmanifest")
def manifest():
    data = {"name": current_app.config["APP_NAME"], "short_name": "SIWES", "start_url": "/", "scope": "/",
            "display": "standalone", "background_color": "#f6f7f5", "theme_color": "#1b5e44",
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

@bp.route("/internal/cron/nightly")
def cron_nightly():
    secret = current_app.config.get("CRON_SECRET") or ""
    sent = request.headers.get("Authorization", "")
    if not secret or not hmac.compare_digest(sent, f"Bearer {secret}"):
        abort(404)
    from ..models.placement import Placement
    from ..services import audit_chain, detection
    bad = sum(1 for (sid,) in db.session.query(Placement.student_id).all()
              if not audit_chain.run_check(sid).ok)
    cp = audit_chain.make_checkpoint()
    audit_chain.publish(cp)
    return {"problems": bad, "checkpoint": cp.digest, "new_flags": detection.scan(since_days=3)}