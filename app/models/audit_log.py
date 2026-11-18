from ..extensions import db


class AuditEvent(db.Model):
    __tablename__ = "audit_events"
    __table_args__ = (db.UniqueConstraint("student_id", "seq", name="uq_audit_student_seq"),)

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    seq = db.Column(db.Integer, nullable=False)
    kind = db.Column(db.String(40), nullable=False)
    payload = db.Column(db.Text, nullable=False)       # canonical JSON
    at = db.Column(db.String(32), nullable=False)      # fixed-format UTC text: part of the sealed data
    prev_hash = db.Column(db.String(64), nullable=False)
    digest = db.Column(db.String(64), nullable=False)