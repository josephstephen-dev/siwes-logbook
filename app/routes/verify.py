import hashlib

from flask import Blueprint, current_app, render_template, request

from ..extensions import limiter
from ..models.verification import IssuedLogbook
from ..services import audit_chain

bp = Blueprint("verify", __name__)


def _limit():
    return current_app.config["VERIFY_LIMIT"]


@bp.route("/check", methods=["GET", "POST"])
@limiter.limit(_limit, methods=["POST"])
def check_pdf():
    result = None
    if request.method == "POST":
        f = request.files.get("file")
        if not f or not f.filename:
            result = {"state": "none"}
        else:
            digest = hashlib.sha256(f.read()).hexdigest()
            rec = IssuedLogbook.query.filter_by(pdf_sha256=digest).first()
            if rec and not rec.revoked_at:
                result = {"state": "match", "vid": rec.vid}
            elif rec:
                result = {"state": "replaced", "vid": rec.vid}
            else:
                result = {"state": "nomatch"}
    return render_template("verify/check_pdf.html", result=result)


@bp.route("/<vid>")
@limiter.limit(_limit)
def result(vid):
    rec = IssuedLogbook.query.filter_by(vid=vid.strip().upper()).first()
    valid = False
    if rec and not rec.revoked_at:
        valid, _, _ = audit_chain.verify(rec.student_id, [rec.head_seq, rec.head_digest])
    return render_template("verify/result.html", rec=rec if valid else None, valid=valid)