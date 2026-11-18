from ..extensions import db
from .user import utcnow


class Entry(db.Model):
    __tablename__ = "entries"
    __table_args__ = (db.UniqueConstraint("student_id", "work_date", name="uq_entry_student_date"),)

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    work_date = db.Column(db.Date, nullable=False)
    body = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="recorded")   # recorded | returned
    is_late = db.Column(db.Boolean, nullable=False, default=False)
    return_comment = db.Column(db.Text)
    sealed = db.Column(db.Boolean, nullable=False, default=False)
    recorded_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    student = db.relationship("User", foreign_keys=[student_id])
    versions = db.relationship("EntryVersion", backref="entry",
                               order_by="EntryVersion.version_no", cascade="all, delete-orphan")


class EntryVersion(db.Model):
    __tablename__ = "entry_versions"
    id = db.Column(db.Integer, primary_key=True)
    entry_id = db.Column(db.Integer, db.ForeignKey("entries.id"), nullable=False, index=True)
    version_no = db.Column(db.Integer, nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)