from datetime import datetime, timezone
from ..extensions import db
from .user import utcnow


def _aware(dt):
    """SQLite hands back naive datetimes; treat them as UTC."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class JoinLink(db.Model):
    """kind='student': the coordinator's shared sign-up link (many uses).
       kind='supervisor': a student's single-use link for their supervisor."""
    __tablename__ = "join_links"

    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(20), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    label = db.Column(db.String(120))
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"))   # supervisor links only
    max_uses = db.Column(db.Integer)
    uses = db.Column(db.Integer, nullable=False, default=0)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    closed_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    created_by = db.relationship("User", foreign_keys=[created_by_id])
    student = db.relationship("User", foreign_keys=[student_id])

    @property
    def state(self):
        if self.closed_at:
            return "Closed"
        if _aware(self.expires_at) < datetime.now(timezone.utc):
            return "Expired"
        if self.max_uses is not None and self.uses >= self.max_uses:
            return "Full"
        return "Open"

    @property
    def is_open(self):
        return self.state == "Open"