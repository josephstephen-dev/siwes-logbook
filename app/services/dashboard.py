from collections import Counter, defaultdict
from datetime import datetime, timezone
from types import SimpleNamespace

from ..extensions import db
from ..models.entry import Entry
from ..models.flag import Flag
from ..models.placement import Placement
from ..models.user import User
from ..models.week import WeekRecord
from . import weeks


def ago(d):
    if not d:
        return "No entries"
    n = (weeks.today() - d).days
    return "Today" if n == 0 else "Yesterday" if n == 1 else f"{n} days ago" if n < 14 else d.strftime("%d %b")


def _age_days(dt):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).days


def build(q="", company="", supervisor_id=None, sort="risk", risk="", only_pending=False):
    t = weeks.today()
    ps = (Placement.query.join(User, Placement.student_id == User.id)
          .filter(User.status == "active").all())
    by, late, last = defaultdict(dict), Counter(), {}
    for sid, d, is_late in db.session.query(Entry.student_id, Entry.work_date, Entry.is_late):
        by[sid][d] = 1
        late[sid] += 1 if is_late else 0
        if sid not in last or d > last[sid]:
            last[sid] = d
    open_f, conf_f = Counter(), Counter()
    for f in Flag.query.filter(Flag.status.in_(["open", "confirmed"])):
        target = open_f if f.status == "open" else conf_f
        target[f.entry_a.student_id] += 1
        target[f.entry_b.student_id] += 1
    pending, oldest = Counter(), {}
    for w in WeekRecord.query.filter_by(status="submitted"):
        pending[w.student_id] += 1
        oldest[w.student_id] = max(oldest.get(w.student_id, 0), _age_days(w.submitted_at))

    rows = []
    for p in ps:
        s = p.student
        cons = weeks.consistency(p, by[s.id])
        if t < p.start_date:
            label, rank = "Not started", 0
        elif cons.pct < 60 or conf_f[s.id] or oldest.get(s.id, 0) > 7:
            label, rank = "At risk", 3
        elif cons.pct < 80 or late[s.id] >= 3 or open_f[s.id]:
            label, rank = "Watch", 2
        else:
            label, rank = "On track", 1
        rows.append(SimpleNamespace(
            p=p, s=s, company=p.company_name, pct=cons.pct, last=ago(last.get(s.id)),
            pending=pending[s.id], late=late[s.id], flags=open_f[s.id],
            overdue=oldest.get(s.id, 0) > 7, risk=label, rank=rank, sup=s.industry_supervisor))

    companies = sorted({r.company for r in rows})
    sups = sorted({(r.sup.id, r.sup.full_name) for r in rows if r.sup}, key=lambda x: x[1])
    stats = SimpleNamespace(
        students=len(rows), companies=len(companies),
        pending=sum(r.pending for r in rows), overdue=sum(1 for r in rows if r.overdue),
        flags=Flag.query.filter_by(status="open").count(),
        avg=round(sum(r.pct for r in rows) / len(rows)) if rows else 0)

    if q:
        rows = [r for r in rows if q in r.s.full_name.lower() or q in (r.s.matric_number or "").lower()
                or q in r.company.lower()]
    if company:
        rows = [r for r in rows if r.company == company]
    if supervisor_id:
        rows = [r for r in rows if r.sup and r.sup.id == supervisor_id]
    if risk in ("At risk", "Watch", "On track", "Not started"):
        rows = [r for r in rows if r.risk == risk]
    if only_pending:
        rows = [r for r in rows if r.pending > 0]
    if sort == "consistency":
        rows.sort(key=lambda r: r.pct)
    elif sort == "name":
        rows.sort(key=lambda r: r.s.full_name)
    else:
        rows.sort(key=lambda r: (-r.rank, r.pct))
    return rows, stats, companies, sups