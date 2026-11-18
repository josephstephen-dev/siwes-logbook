from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, SelectField, StringField
from wtforms.validators import DataRequired, EqualTo, Length, Regexp
from .validators import email_address

PHONE = Regexp(r"^\+?[0-9 \-]{10,18}$", message="Enter a valid phone number.")
MATRIC = Regexp(r"^[A-Za-z0-9][A-Za-z0-9/\-]{4,29}$", message="Check the matric number format.")
LEVELS = [("", "Select level")] + [(l, f"{l} Level") for l in ("100", "200", "300", "400", "500")]
CONSENT = "My details are used only for managing my SIWES logbook."


class _SignUpBase(FlaskForm):
    password = PasswordField("Password", validators=[DataRequired(), Length(max=128)])
    confirm = PasswordField("Confirm password", validators=[
        DataRequired(), EqualTo("password", message="Passwords don't match.")])


class StudentSignUpForm(_SignUpBase):
    full_name = StringField("Full name", validators=[DataRequired(), Length(max=120)])
    matric_number = StringField("Matric number", validators=[DataRequired(), MATRIC])
    department = StringField("Department", validators=[DataRequired(), Length(max=120)])
    level = SelectField("Level", choices=LEVELS, validators=[DataRequired(message="Select a level.")])
    email = StringField("Email", validators=[DataRequired(), email_address, Length(max=160)])
    phone = StringField("Phone number", validators=[DataRequired(), PHONE])
    consent = BooleanField(CONSENT, validators=[DataRequired(message="Please tick this box to continue.")])


class SupervisorSignUpForm(_SignUpBase):
    full_name = StringField("Full name", validators=[DataRequired(), Length(max=120)])
    company = StringField("Company", validators=[DataRequired(), Length(max=160)])
    designation = StringField("Designation", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), email_address, Length(max=160)])
    phone = StringField("Phone number", validators=[DataRequired(), PHONE])
    consent = BooleanField(CONSENT, validators=[DataRequired(message="Please tick this box to continue.")])


class StaffSignUpForm(_SignUpBase):
    full_name = StringField("Full name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Staff email", validators=[DataRequired(), email_address, Length(max=160)])
    code = StringField("Staff code", validators=[DataRequired(), Length(max=40)])

class FirstRunForm(_SignUpBase):
    full_name = StringField("Full name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Staff email", validators=[DataRequired(), email_address, Length(max=160)])
    token = StringField("Setup key", validators=[DataRequired(), Length(max=200)])

class ResendForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), email_address])