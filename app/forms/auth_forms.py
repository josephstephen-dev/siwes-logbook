from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField
from wtforms.validators import DataRequired, EqualTo, Length


class _SignInBase(FlaskForm):
    password = PasswordField("Password", validators=[DataRequired(), Length(max=128)])
    remember = BooleanField("Remember me on this device")


class StudentSignInForm(_SignInBase):
    identifier = StringField("Matric number or email", validators=[DataRequired(), Length(max=160)])


class SupervisorSignInForm(_SignInBase):
    identifier = StringField("Email or phone", validators=[DataRequired(), Length(max=160)])


class CoordinatorSignInForm(_SignInBase):
    identifier = StringField("Staff email", validators=[DataRequired(), Length(max=160)])


class ForgotPasswordForm(FlaskForm):
    identifier = StringField("Matric number or email", validators=[DataRequired(), Length(max=160)])

class ResetPasswordForm(FlaskForm):
    password = PasswordField("New password", validators=[DataRequired(), Length(max=128)])
    confirm = PasswordField("Confirm password", validators=[
        DataRequired(), EqualTo("password", message="Passwords don't match.")])