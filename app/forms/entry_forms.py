from flask_wtf import FlaskForm
from wtforms import BooleanField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length

from ..services.entries import MAX_CHARS, MIN_CHARS


def _strip(value):
    return (value or "").strip()


class EntryForm(FlaskForm):
    body = TextAreaField("Description of work done", filters=[_strip], validators=[
        DataRequired(message="Write what you did on this day."),
        Length(min=MIN_CHARS, max=MAX_CHARS,
               message=f"Write between {MIN_CHARS} and {MAX_CHARS} characters.")])


class SketchForm(FlaskForm):
    report = TextAreaField("Additional report", filters=[_strip], validators=[Length(max=3000)])
    typed_name = StringField("Typed name", validators=[Length(max=120)])
    confirm = BooleanField("I confirm this week's entries are my own work")