from ..extensions import db
from .user import utcnow


class Flag(db.Model):
    __tablename__ = "flags"
    __table_args__ = (db.UniqueConstraint("entry_a_id", "entry_b_id", name="uq_flag_pair"),)

    id = db.Column(db.Integer, primary_key=True)
    entry_a_id = db.Column(db.Integer, db.ForeignKey("entries.id"), nullable=False)
    entry_b_id = db.Column(db.Integer, db.ForeignKey("entries.id"), nullable=False)
    score = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="open")   # open | dismissed | confirmed
    note = db.Column(db.Text)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    reviewed_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    entry_a = db.relationship("Entry", foreign_keys=[entry_a_id])
    entry_b = db.relationship("Entry", foreign_keys=[entry_b_id])
    reviewer = db.relationship("User", foreign_keys=[reviewed_by_id])