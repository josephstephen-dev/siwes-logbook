from flask_wtf import FlaskForm
from wtforms import DateField, IntegerField, SelectField, SelectMultipleField, StringField
from wtforms.validators import DataRequired, Length, NumberRange, Optional
from wtforms.widgets import CheckboxInput, ListWidget

from ..models.placement import DAY_LABELS


class LinkForm(FlaskForm):
    label = StringField("Name for this link", default="SIWES sign-up",
                        validators=[DataRequired(), Length(max=120)])
    days = SelectField("Valid for", coerce=int, default=30,
                       choices=[(7, "7 days"), (14, "14 days"), (30, "30 days"), (60, "60 days")])
    max_uses = IntegerField("Maximum sign-ups", validators=[Optional(), NumberRange(min=1, max=2000)])


class PlacementForm(FlaskForm):
    student = SelectField("Student", coerce=int, choices=[])
    company_name = StringField("Company", validators=[DataRequired(), Length(max=160)])
    company_address = StringField("Company address", validators=[Length(max=255)])
    start_date = DateField("Start date", validators=[DataRequired()])
    end_date = DateField("End date", validators=[DataRequired()])
    working_days = SelectMultipleField(
        "Working days", choices=[(str(i), d) for i, d in enumerate(DAY_LABELS)],
        default=["0", "1", "2", "3", "4", "5"],
        widget=ListWidget(prefix_label=False), option_widget=CheckboxInput(),
        validators=[DataRequired(message="Choose at least one working day.")])
    school_supervisor = StringField("School supervisor", validators=[Length(max=120)])

class PlacementEditForm(PlacementForm):
    student = None          # the student can't be changed on an existing placement