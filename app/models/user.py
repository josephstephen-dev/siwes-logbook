from datetime import datetime, timezone
from flask_login import UserMixin
from ..extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(20), nullable=False, index=True)   # student | supervisor | coordinator
    supervisor_kind = db.Column(db.String(20))                    # industry | school

    full_name = db.Column(db.String(120), nullable=False)
    matric_number = db.Column(db.String(40), unique=True)
    email = db.Column(db.String(160), unique=True)
    phone = db.Column(db.String(30))
    department = db.Column(db.String(120))
    level = db.Column(db.String(10))
    company = db.Column(db.String(160))
    designation = db.Column(db.String(120))

    password_hash = db.Column(db.String(255))
    # active | pending (coordinator waiting for approval) | deactivated
    status = db.Column(db.String(20), nullable=False, default="active")
    last_sign_in_at = db.Column(db.DateTime(timezone=True))
    email_verified_at = db.Column(db.DateTime(timezone=True)) # active | unverified | pending | deactivated
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    # students: who supervises them
    industry_supervisor_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    # supervisors: identity confirmed by phone. coordinators: approved by a colleague.
    verified_at = db.Column(db.DateTime(timezone=True))
    verified_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    industry_supervisor = db.relationship(
        "User", foreign_keys=[industry_supervisor_id], remote_side="User.id",
        backref="supervised_students")
    verified_by = db.relationship(
        "User", foreign_keys=[verified_by_id], remote_side="User.id")

    @property
    def role_label(self):
        return self.role.capitalize()

    @property
    def is_active(self):
        return self.status == "active"

    @property
    def is_verified(self):
        return self.verified_at is not None