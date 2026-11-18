from types import SimpleNamespace

from ..models.week import WeekRecord
from . import audit_chain, detection, weeks


def checklist(student):
    p = student.placement
    needed = [n for n in range(1, p.total_weeks + 1)
              if any(r.works for r in weeks.rows_for(p, n, {}))]
    recs = {w.week_no: w.status for w in WeekRecord.query.filter_by(student_id=student.id)}
    approved = sum(1 for n in needed if recs.get(n) == "approved")
    flags = detection.open_flags_for(student.id)
    result = audit_chain.run_check(student.id)       # a fresh check, every time
    c = SimpleNamespace(needed=len(needed), approved=approved, weeks_ok=approved == len(needed) and bool(needed),
                        flags=flags, flags_ok=flags == 0, result=result, integrity_ok=result.ok)
    c.ready = c.weeks_ok and c.flags_ok and c.integrity_ok
    return c