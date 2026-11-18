import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models.entry import Entry
from ..models.week import WeekRecord

LAGOS = ZoneInfo(os.environ.get("APP_TIMEZONE", "Africa/Lagos"))
DAYS = ["Mon.", "Tue.", "Wed.", "Thur.", "Fri.", "Sat."]
STATUS_LABEL = {"open": "Draft", "submitted": "Submitted",
                "returned": "Returned for correction", "approved": "Approved"}


def today():
    return datetime.now(LAGOS).date()


def to_lagos(dt, fmt="%d %b %Y, %I:%M %p"):
    if not dt:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(LAGOS).strftime(fmt)


def week1_monday(p):
    return p.start_date - timedelta(days=p.start_date.weekday())


def week_start(p, n):
    return week1_monday(p) + timedelta(days=7 * (n - 1))


def week_end(p, n):
    return week_start(p, n) + timedelta(days=5)          # Saturday


def week_no_for(p, d):
    return (d - week1_monday(p)).days // 7 + 1


def current_week_no(p):
    t = today()
    if t < p.start_date:
        return 1
    return max(1, min(week_no_for(p, t), p.total_weeks))


def working_set(p):
    return {int(x) for x in p.working_days.split(",") if x != "" and int(x) < 6}


def entries_by_date(student):
    return {e.work_date: e for e in Entry.query.filter_by(student_id=student.id)}


def week_entries(student, p, n):
    s = week_start(p, n)
    return Entry.query.filter(Entry.student_id == student.id, Entry.work_date >= s,
                              Entry.work_date <= s + timedelta(days=5)).all()


def rows_for(p, n, by_date):
    ws, start, t = working_set(p), week_start(p, n), today()
    rows = []
    for i, label in enumerate(DAYS):
        d = start + timedelta(days=i)
        rows.append(SimpleNamespace(
            label=label, date=d, entry=by_date.get(d), future=d > t,
            works=i in ws and p.start_date <= d <= p.end_date))
    return rows


def consistency(p, by_date):
    ws, t = working_set(p), min(today(), p.end_date)
    due = done = 0
    d = p.start_date
    while d <= t:
        if d.weekday() in ws:
            due += 1
            done += d in by_date
        d += timedelta(days=1)
    return SimpleNamespace(due=due, done=done, pct=round(100 * done / due) if due else 0)


def get_week(student, n):
    wk = WeekRecord.query.filter_by(student_id=student.id, week_no=n).first()
    if wk is None:
        wk = WeekRecord(student_id=student.id, week_no=n, status="open")
        db.session.add(wk)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            wk = WeekRecord.query.filter_by(student_id=student.id, week_no=n).one()
    return wk

def greeting():
    h = datetime.now(LAGOS).hour
    return "Good morning" if h < 12 else "Good afternoon" if h < 17 else "Good evening"