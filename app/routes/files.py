from flask import Blueprint, abort, send_file
from flask_login import current_user, login_required

from ..extensions import db
from ..models.attachment import Attachment
from ..services import uploads

bp = Blueprint("files", __name__)


@bp.route("/sketch/<int:att_id>")
@login_required
def sketch(att_id):
    a = db.session.get(Attachment, att_id)
    if not a:
        abort(404)
    student = a.week.student
    u = current_user
    allowed = (u.role == "coordinator" or u.id == student.id
               or (u.role == "supervisor" and student.industry_supervisor_id == u.id))
    if not allowed:
        abort(404)
    mime = "image/png" if a.stored_name.endswith(".png") else "image/jpeg"
    resp = send_file(uploads.path_for(a.stored_name), mimetype=mime)
    resp.headers["Cache-Control"] = "private, max-age=3600"
    return resp