from functools import wraps
from flask import abort
from flask_login import current_user, login_required


def role_required(role):
    """Signed in AND exactly this role. No switching, ever."""
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role != role:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


HOME_ENDPOINT = {
    "student": "student.home",
    "supervisor": "supervisor.pending_weeks",
    "coordinator": "coordinator.dashboard",
}