from ..extensions import db
from .user import utcnow


class Setting(db.Model):
    """Small key/value store for things coordinators manage in the app."""
    __tablename__ = "settings"
    key = db.Column(db.String(60), primary_key=True)
    value = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)