import re
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError

_ph = PasswordHasher()
_DUMMY = _ph.hash("not-a-real-password")


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(stored_hash: str | None, password: str) -> bool:
    """Always does one hash check so unknown accounts take the same time."""
    try:
        return _ph.verify(stored_hash or _DUMMY, password) and stored_hash is not None
    except (VerifyMismatchError, InvalidHashError):
        return False


def password_problems(password: str) -> list[str]:
    """Rules list shown on the account-setup screen."""
    problems = []
    if len(password) < 10:
        problems.append("At least 10 characters")
    if not re.search(r"[A-Za-z]", password):
        problems.append("At least one letter")
    if not re.search(r"\d", password):
        problems.append("At least one number")
    return problems