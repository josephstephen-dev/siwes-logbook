import io

from flask import Blueprint, abort, send_file
from flask_login import current_user, login_required

from ..extensions import db
from ..models.attachment import Attachment
from ..models.stored_file import StoredFile

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
    row = db.session.get(StoredFile, a.stored_name)
    if not allowed or not row:
        abort(404)
    resp = send_file(io.BytesIO(row.data), mimetype=row.mime)
    resp.headers["Cache-Control"] = "private, max-age=3600"
    return resp