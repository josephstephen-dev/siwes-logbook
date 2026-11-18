from ..extensions import db
from .user import utcnow


class Attachment(db.Model):
    __tablename__ = "attachments"
    id = db.Column(db.Integer, primary_key=True)
    week_id = db.Column(db.Integer, db.ForeignKey("week_records.id"), nullable=False, index=True)
    stored_name = db.Column(db.String(80), nullable=False)
    caption = db.Column(db.String(200), nullable=False, default="")
    size = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)