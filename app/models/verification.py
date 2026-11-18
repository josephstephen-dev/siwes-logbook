from ..extensions import db
from .user import utcnow


class IssuedLogbook(db.Model):
    __tablename__ = "issued_logbooks"
    id = db.Column(db.Integer, primary_key=True)
    vid = db.Column(db.String(24), unique=True, nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    pdf_sha256 = db.Column(db.String(64), nullable=False, index=True)
    filename = db.Column(db.String(80), nullable=False)
    size = db.Column(db.Integer, nullable=False, default=0)
    company = db.Column(db.String(160))
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    initials = db.Column(db.String(8))
    matric_tail = db.Column(db.String(3))
    head_seq = db.Column(db.Integer, nullable=False)
    head_digest = db.Column(db.String(64), nullable=False)
    issued_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    issued_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    revoked_at = db.Column(db.DateTime(timezone=True))
    student = db.relationship("User", foreign_keys=[student_id])