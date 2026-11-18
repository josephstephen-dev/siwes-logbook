from ..extensions import db
from .user import utcnow


class WeekRecord(db.Model):
    __tablename__ = "week_records"
    __table_args__ = (db.UniqueConstraint("student_id", "week_no", name="uq_week_student_no"),)

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    week_no = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="open")   # open|submitted|returned|approved
    report = db.Column(db.Text, nullable=False, default="")
    typed_name = db.Column(db.String(120))
    confirmed_at = db.Column(db.DateTime(timezone=True))
    submitted_at = db.Column(db.DateTime(timezone=True))
    supervisor_comment = db.Column(db.Text)
    approved_at = db.Column(db.DateTime(timezone=True))
    approver_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    approver_name = db.Column(db.String(120))
    approver_designation = db.Column(db.String(120))
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    student = db.relationship("User", foreign_keys=[student_id])
    approver = db.relationship("User", foreign_keys=[approver_id])
    attachments = db.relationship("Attachment", backref="week", order_by="Attachment.id",
                                  cascade="all, delete-orphan")