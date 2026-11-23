import json
import os
from datetime import datetime, timezone

from flask import current_app

from ..extensions import db
from ..models.audit_log import AuditEvent
from ..models.checkpoint import Checkpoint, IntegrityResult
from ..models.entry import Entry
from ..models.user import User
from ..models.week import WeekRecord
from .canonical import GENESIS, canonical, seal, sha256_text


def _stamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def head(student_id):
    return (AuditEvent.query.filter_by(student_id=student_id)
            .order_by(AuditEvent.seq.desc()).first())


def append(student_id, kind, payload):
    """Adds one event inside the caller's transaction; the caller commits."""
    # On PostgreSQL this serialises writers for the same student so sequence numbers never clash.
    db.session.query(User).filter(User.id == student_id).with_for_update().first()
    last = head(student_id)
    seq = last.seq + 1 if last else 1
    prev = last.digest if last else GENESIS
    body, at = canonical(payload), _stamp()
    ev = AuditEvent(student_id=student_id, seq=seq, kind=kind, payload=body, at=at,
                    prev_hash=prev, digest=seal(prev, student_id, seq, kind, at, body))
    db.session.add(ev)
    db.session.flush()
    return ev


def verify(student_id, expected_head=None):
    """Returns (ok, problem_event_number, plain message)."""
    events = AuditEvent.query.filter_by(student_id=student_id).order_by(AuditEvent.seq).all()
    prev, expect = GENESIS, 1
    latest, approved = {}, set()
    for ev in events:
        if ev.seq != expect:
            return False, expect, "A record is missing or out of order."
        if ev.prev_hash != prev or ev.digest != seal(prev, student_id, ev.seq, ev.kind, ev.at, ev.payload):
            return False, ev.seq, "A record was changed."
        data = json.loads(ev.payload)
        if ev.kind in ("entry_recorded", "entry_amended"):
            latest[data["date"]] = (data["sha"], ev.seq)
        elif ev.kind == "week_approved":
            approved.add(data["week"])
        prev, expect = ev.digest, ev.seq + 1

    if expected_head:                       # a published checkpoint, or the head at issue time
        seq, digest = expected_head
        if seq >= expect:
            return False, expect, "Records were removed after the last checkpoint."
        if events[seq - 1].digest != digest:
            return False, seq, "A record differs from the published checkpoint."

    seen = set()
    for e in Entry.query.filter_by(student_id=student_id):
        key = e.work_date.isoformat()
        seen.add(key)
        if key not in latest:
            return False, expect, "An entry has no record."
        sha, seq = latest[key]
        if sha256_text(e.body) != sha:
            return False, seq, "An entry differs from its recorded version."
    for key, (_, seq) in latest.items():
        if key not in seen:
            return False, seq, "An entry was removed."
    in_db = {w.week_no for w in WeekRecord.query.filter_by(student_id=student_id, status="approved")}
    if in_db != approved:
        return False, expect, "A week's approval does not match its record."
    return True, None, "Integrity verified"


def run_check(student_id):
    cp = Checkpoint.query.order_by(Checkpoint.id.desc()).first()
    heads = json.loads(cp.heads) if cp else {}
    ok, seq, msg = verify(student_id, heads.get(str(student_id)))
    row = IntegrityResult.query.filter_by(student_id=student_id).first()
    if row is None:
        row = IntegrityResult(student_id=student_id)
        db.session.add(row)
    row.ok, row.problem_seq, row.message = ok, seq, msg
    row.checked_at = datetime.now(timezone.utc)
    db.session.commit()
    return row


def make_checkpoint():
    heads = {}
    for (sid,) in db.session.query(AuditEvent.student_id).distinct().all():
        h = head(sid)
        heads[str(sid)] = [h.seq, h.digest]
    stamp = _stamp()
    cp = Checkpoint(stamp=stamp, heads=canonical(heads),
                    digest=sha256_text(canonical([stamp, heads])))
    db.session.add(cp)
    db.session.commit()
    return cp


def publish(cp):
    """Copies the checkpoint outside the database: a log file and an email to every coordinator."""
    from .notifications import send_email
    try:
        path = os.path.join(current_app.instance_path, "checkpoints.log")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a") as f:
            f.write(f"{cp.stamp} {cp.digest}\n")
    except OSError:
        current_app.logger.info("No writable log file here; the checkpoint is published by email only.")
    for c in User.query.filter_by(role="coordinator", status="active"):
        send_email(c.email, f"SIWES daily checkpoint {cp.stamp[:10]}",
                   "This is the daily record checkpoint. Keep this email: it lets issued "
                   f"records be checked later.\n\nCheckpoint: {cp.digest}\nTime: {cp.stamp}\n")
    cp.published = True
    db.session.commit()


def published_matches(digest):
    cp = Checkpoint.query.filter_by(digest=digest.strip()).first()
    return bool(cp) and cp.digest == sha256_text(canonical([cp.stamp, json.loads(cp.heads)]))

def audit_checkpoints():
    """Checks stored checkpoints against their own fingerprint, the external log file, and each other."""
    problems, seen = [], {}
    path = os.path.join(current_app.instance_path, "checkpoints.log")
    have_log = os.path.exists(path)
    logged = set()
    if have_log:
        with open(path) as fh:
            logged = {p[1] for p in (line.split() for line in fh) if len(p) == 2}
    for cp in Checkpoint.query.order_by(Checkpoint.id):
        heads = json.loads(cp.heads)
        day = cp.stamp[:10]
        if cp.digest != sha256_text(canonical([cp.stamp, heads])):
            problems.append(f"The checkpoint of {day} was altered.")
            continue
        if cp.published and cp.digest not in logged:
            problems.append(f"The checkpoint of {day} is missing from the external log file.")
        for sid, (seq, _) in heads.items():
            if sid in seen and seq < seen[sid]:
                problems.append(f"Records were removed between checkpoints (student {sid}, {day}).")
            seen[sid] = seq
    return problems


def event_counts():
    from sqlalchemy import func
    return dict(db.session.query(AuditEvent.student_id, func.count(AuditEvent.id))
                .group_by(AuditEvent.student_id).all())