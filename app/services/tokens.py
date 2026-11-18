import hashlib
import secrets

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


def new_token() -> tuple[str, str]:
    """Returns (token to put in the link, hash to store in the database)."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


# Password-reset links: signed, expire after RESET_TTL_MINUTES, and stop
# working the moment the password changes (so each link is single-use).
def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="password-reset")


def make_reset_token(user) -> str:
    return _serializer().dumps({"uid": user.id, "pw": (user.password_hash or "")[-12:]})


def read_reset_token(token):
    from ..extensions import db
    from ..models.user import User
    try:
        data = _serializer().loads(
            token, max_age=current_app.config["RESET_TTL_MINUTES"] * 60)
    except (BadSignature, SignatureExpired):
        return None
    user = db.session.get(User, data["uid"])
    if not user or user.status != "active":
        return None
    if (user.password_hash or "")[-12:] != data["pw"]:
        return None
    return user

def _verify_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="verify-email")


def make_verify_token(user) -> str:
    return _verify_serializer().dumps({"uid": user.id, "email": user.email})


def read_verify_token(token):
    from ..extensions import db
    from ..models.user import User
    try:
        data = _verify_serializer().loads(
            token, max_age=current_app.config["VERIFY_TTL_HOURS"] * 3600)
    except (BadSignature, SignatureExpired):
        return None
    user = db.session.get(User, data["uid"])
    if not user or user.status == "deactivated":
        return None
    if (user.email or "").lower() != data["email"].lower():
        return None
    return user