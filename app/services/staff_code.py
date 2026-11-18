import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from flask import current_app

from ..extensions import db
from ..models.setting import Setting

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
K_HASH, K_EXPIRES = "staff_code_hash", "staff_code_expires"


def _digest(code):
    key = current_app.config["HMAC_KEY"].encode()
    return hmac.new(key, code.strip().upper().encode(), hashlib.sha256).hexdigest()


def _get(key):
    row = db.session.get(Setting, key)
    return row.value if row else ""


def _put(key, value):
    row = db.session.get(Setting, key)
    if row:
        row.value = value
    else:
        db.session.add(Setting(key=key, value=value))


def new_code(days=7):
    """Makes a fresh code, replacing any older one. Returns it once; it is never stored."""
    code = "-".join("".join(secrets.choice(ALPHABET) for _ in range(4)) for _ in range(3))
    _put(K_HASH, _digest(code))
    _put(K_EXPIRES, (datetime.now(timezone.utc) + timedelta(days=days)).isoformat())
    db.session.commit()
    return code


def revoke_code():
    _put(K_HASH, "")
    db.session.commit()


def code_expiry():
    """When the active code stops working, or None if there isn't one."""
    if not _get(K_HASH):
        return None
    expires = datetime.fromisoformat(_get(K_EXPIRES))
    return expires if expires > datetime.now(timezone.utc) else None


def check_code(code):
    if code_expiry() is None:
        return False
    return hmac.compare_digest(_digest(code), _get(K_HASH))