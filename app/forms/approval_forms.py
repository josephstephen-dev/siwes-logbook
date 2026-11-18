from flask_wtf import FlaskForm
from wtforms import BooleanField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length


class ApproveForm(FlaskForm):
    comment = TextAreaField("Comments by Industry-Based Supervisor", validators=[Length(max=1000)])
    signer_name = StringField("Name", validators=[DataRequired(), Length(max=120)])
    designation = StringField("Designation", validators=[DataRequired(), Length(max=120)])
    confirm = BooleanField("I confirm that I reviewed this week's work", validators=[DataRequired()])


class ReturnForm(FlaskForm):
    comment = TextAreaField("Comment", validators=[DataRequired(), Length(min=5, max=500)])