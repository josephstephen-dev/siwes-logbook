from ..extensions import db
from .user import utcnow


class StoredFile(db.Model):
    """Photos and issued PDFs live in the database so they survive on serverless hosting."""
    __tablename__ = "stored_files"
    name = db.Column(db.String(120), primary_key=True)
    mime = db.Column(db.String(60), nullable=False)
    data = db.Column(db.LargeBinary, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)