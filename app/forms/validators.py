import re

from wtforms.validators import ValidationError

_EMAIL = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")


def email_address(form, field):
    value = (field.data or "").strip()
    if len(value) > 160 or not _EMAIL.match(value):
        raise ValidationError("Enter a valid email address.")