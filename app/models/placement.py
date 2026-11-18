from datetime import timedelta
from ..extensions import db
from .user import utcnow

DAY_LABELS = ["Mon", "Tue", "Wed", "Thur", "Fri", "Sat", "Sun"]


class Placement(db.Model):
    __tablename__ = "placements"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    company_name = db.Column(db.String(160), nullable=False)
    company_address = db.Column(db.String(255))
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    working_days = db.Column(db.String(20), nullable=False, default="0,1,2,3,4,5")
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    student = db.relationship("User", foreign_keys=[student_id],
                              backref=db.backref("placement", uselist=False))

    school_supervisor = db.Column(db.String(120))

    @property
    def industry_supervisor(self):
        return self.student.industry_supervisor

    @property
    def day_labels(self):
        return [DAY_LABELS[int(d)] for d in self.working_days.split(",") if d != ""]

    @property
    def total_weeks(self):
        monday = self.start_date - timedelta(days=self.start_date.weekday())
        return (self.end_date - monday).days // 7 + 1