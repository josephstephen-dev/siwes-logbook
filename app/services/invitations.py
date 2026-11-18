import re
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from flask import current_app, url_for
from sqlalchemy import func, or_

from ..extensions import db
from ..models.join_link import JoinLink
from ..models.user import User
from .notifications import send_verify_email
from .passwords import hash_password

LEVELS = ["100", "200", "300", "400", "500"]


def now():
    return datetime.now(timezone.utc)

def normalize_phone(raw):
    digits = re.sub(r"[^\d+]", "", raw or "")
    cc = current_app.config.get("DEFAULT_COUNTRY_CODE", "234")
    if digits.startswith("+"):
        return digits
    if digits.startswith("00"):
        return "+" + digits[2:]
    if digits.startswith(cc) and len(digits) > 10:
        return "+" + digits
    if digits.startswith("0"):
        return "+" + cc + digits[1:]
    return digits


def normalize_level(raw):
    m = re.match(r"\s*(\d{3})", raw or "")
    return m.group(1) if m and m.group(1) in LEVELS else None


# ---- links -------------------------------------------------------------

def public_url(endpoint, **values):
    """Full link. PUBLIC_BASE_URL makes links work from other devices."""
    base = (current_app.config.get("PUBLIC_BASE_URL") or "").rstrip("/")
    if base:
        return base + url_for(endpoint, **values)
    return url_for(endpoint, _external=True, **values)


def whatsapp_url(text):
    return "https://wa.me/?text=" + quote(text)


def create_link(kind, by, label, days, max_uses=None, student=None):
    if kind == "supervisor":          # one live link per student
        for old in JoinLink.query.filter_by(kind="supervisor", student_id=student.id, closed_at=None):
            old.closed_at = now()
    link = JoinLink(kind=kind, token=secrets.token_urlsafe(24), label=label,
                    created_by_id=by.id, student_id=student.id if student else None,
                    max_uses=max_uses, expires_at=now() + timedelta(days=days))
    db.session.add(link)
    return link


def link_url(link):
    endpoint = "invite.join_student" if link.kind == "student" else "invite.join_supervisor"
    return public_url(endpoint, token=link.token)


def find_link(token, kind):
    return JoinLink.query.filter_by(token=token, kind=kind).first()


def active_supervisor_link(student):
    for link in (JoinLink.query.filter_by(kind="supervisor", student_id=student.id)
                 .order_by(JoinLink.id.desc())):
        if link.is_open:
            return link
    return None


def reopen(link):
    link.closed_at = None
    if link.state == "Expired":
        link.expires_at = now() + timedelta(days=7)


# ---- sign-ups ----------------------------------------------------------

def duplicate_problem(matric=None, email=None, phone=None):
    """Only confirmed accounts block a sign-up; unconfirmed ones get replaced."""
    live = User.status != "unverified"
    if matric and User.query.filter(live, func.upper(User.matric_number) == matric.strip().upper()).first():
        return "This matric number already has an account. If it isn't yours, tell your coordinator."
    if email and User.query.filter(live, func.lower(User.email) == email.strip().lower()).first():
        return "This email is already used by another account."
    if phone and User.query.filter(live, User.phone == normalize_phone(phone)).first():
        return "This phone number is already used by another account."
    return None


def _drop_unverified(matric=None, email=None, phone=None):
    conds = []
    if matric:
        conds.append(func.upper(User.matric_number) == matric.strip().upper())
    if email:
        conds.append(func.lower(User.email) == email.strip().lower())
    if phone:
        conds.append(User.phone == normalize_phone(phone))
    if not conds:
        return
    for old in User.query.filter(User.status == "unverified", or_(*conds)).all():
        User.query.filter_by(industry_supervisor_id=old.id).update({"industry_supervisor_id": None})
        db.session.delete(old)
    db.session.flush()


def confirm_email(user):
    user.email_verified_at = now()
    user.status = "pending" if user.role == "coordinator" else "active"
    db.session.commit()


def register_student(link, d):
    _drop_unverified(d["matric_number"], d["email"], d["phone"])
    user = User(role="student", status="unverified", full_name=d["full_name"].strip(),
                matric_number=d["matric_number"].strip().upper(),
                email=d["email"].strip().lower(), phone=normalize_phone(d["phone"]),
                department=d["department"].strip().title(), level=normalize_level(d["level"]),
                password_hash=hash_password(d["password"]))
    db.session.add(user)
    link.uses += 1
    db.session.commit()
    return user, send_verify_email(user)


def attach_supervisor(link, supervisor):
    link.student.industry_supervisor_id = supervisor.id
    link.uses += 1
    db.session.commit()


def register_supervisor(link, d):
    _drop_unverified(email=d["email"], phone=d["phone"])
    user = User(role="supervisor", supervisor_kind="industry", status="unverified",
                full_name=d["full_name"].strip(), email=d["email"].strip().lower(),
                phone=normalize_phone(d["phone"]), company=d["company"].strip(),
                designation=d["designation"].strip(),
                password_hash=hash_password(d["password"]))
    db.session.add(user)
    db.session.flush()
    attach_supervisor(link, user)
    return user, send_verify_email(user)


def register_staff(d):
    _drop_unverified(email=d["email"])
    user = User(role="coordinator", status="unverified", full_name=d["full_name"].strip(),
                email=d["email"].strip().lower(), password_hash=hash_password(d["password"]))
    db.session.add(user)
    db.session.commit()
    return user, send_verify_email(user)


def register_first_coordinator(d):
    user = User(role="coordinator", status="active", full_name=d["full_name"].strip(),
                email=d["email"].strip().lower(), password_hash=hash_password(d["password"]),
                verified_at=now())
    db.session.add(user)
    db.session.commit()
    return user