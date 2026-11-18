from ..extensions import db
from .user import utcnow


class Checkpoint(db.Model):
    __tablename__ = "checkpoints"
    id = db.Column(db.Integer, primary_key=True)
    stamp = db.Column(db.String(32), nullable=False)
    digest = db.Column(db.String(64), nullable=False, index=True)
    heads = db.Column(db.Text, nullable=False)          # {student_id: [seq, digest]}
    published = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)


class IntegrityResult(db.Model):
    __tablename__ = "integrity_results"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    ok = db.Column(db.Boolean, nullable=False, default=True)
    problem_seq = db.Column(db.Integer)
    message = db.Column(db.String(200))
    checked_at = db.Column(db.DateTime(timezone=True))
    student = db.relationship("User", foreign_keys=[student_id])