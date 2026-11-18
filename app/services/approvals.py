from flask import current_app

from ..extensions import db
from ..models.entry import Entry
from . import weeks, audit_chain
from .canonical import sha256_text
from .entries import RuleError
from .invitations import now, public_url
from .notifications import send_email


def submit_week(student, wk, typed_name, confirmed):
    p = student.placement
    if wk.status in ("submitted", "approved"):
        raise RuleError("This week has already been sent to your supervisor.")
    if not student.industry_supervisor_id:
        raise RuleError("Link your supervisor first (My supervisor), so they can approve this week.")
    working = [r for r in weeks.rows_for(p, wk.week_no, weeks.entries_by_date(student)) if r.works]
    if not working:
        raise RuleError("This week has no working days.")
    missing = [r.label for r in working if not r.entry]
    if missing:
        raise RuleError("Every working day needs an entry first. Missing: " + ", ".join(missing))
    if any(r.entry.status == "returned" for r in working):
        raise RuleError("Correct the returned entries first.")
    if not confirmed:
        raise RuleError("Tick the box confirming this week's entries are your own work.")
    if not (typed_name or "").strip():
        raise RuleError("Type your name to sign.")
    wk.typed_name = typed_name.strip()
    wk.confirmed_at = wk.submitted_at = now()
    wk.status = "submitted"
    audit_chain.append(student.id, "week_submitted", {"week": wk.week_no, "name": wk.typed_name})
    db.session.commit()
    sup = student.industry_supervisor
    if sup and sup.email:
        send_email(sup.email, f"{student.full_name}: Week {wk.week_no} is ready for your approval",
                   f"Hello {sup.full_name.split()[0]},\n\n{student.full_name} has sent Week "
                   f"{wk.week_no} of their SIWES logbook for your approval.\n"
                   f"Sign in and open it here:\n{public_url('supervisor.week_review', week_id=wk.id)}\n")


def _check_owner(sup, wk):
    if wk.student.industry_supervisor_id != sup.id:
        raise RuleError("This isn't one of your students.")


def return_entry(sup, wk, day, comment):
    _check_owner(sup, wk)
    if wk.status not in ("submitted", "returned"):
        raise RuleError("This week isn't waiting for review.")
    p = wk.student.placement
    if weeks.week_no_for(p, day) != wk.week_no:
        raise RuleError("That day isn't in this week.")
    entry = Entry.query.filter_by(student_id=wk.student_id, work_date=day).first()
    if not entry:
        raise RuleError("There is no entry for that day.")
    entry.status, entry.return_comment = "returned", comment.strip()
    wk.status, wk.confirmed_at = "returned", None
    audit_chain.append(wk.student_id, "entry_returned",
                       {"week": wk.week_no, "date": day.isoformat(),
                        "comment_sha": sha256_text(comment.strip()), "by": sup.id})
    db.session.commit()
    student = wk.student
    if student.email:
        send_email(student.email, f"Week {wk.week_no}: your supervisor returned an entry",
                   f"Hello {student.full_name.split()[0]},\n\nYour supervisor asked you to correct "
                   f"the entry for {day.strftime('%A %d %B')}:\n\"{comment.strip()}\"\n\n"
                   f"Open the week here:\n{public_url('student.week_chart', n=wk.week_no)}\n")


def approve_week(sup, wk, comment, signer_name, designation):
    _check_owner(sup, wk)
    if not sup.is_verified:
        raise RuleError("Your coordinator must confirm your identity before you can approve weeks.")
    if wk.status != "submitted":
        raise RuleError("This week isn't waiting for approval.")
    for e in weeks.week_entries(wk.student, wk.student.placement, wk.week_no):
        e.sealed = True
    wk.supervisor_comment = (comment or "").strip()
    wk.approver_id, wk.approver_name = sup.id, signer_name.strip()
    wk.approver_designation = designation.strip()
    wk.approved_at, wk.status = now(), "approved"
    audit_chain.append(wk.student_id, "week_approved",
                       {"week": wk.week_no, "by": sup.id,
                        "comment_sha": sha256_text(wk.supervisor_comment or "")})
    db.session.commit()