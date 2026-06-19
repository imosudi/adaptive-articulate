from datetime import datetime

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    EmailField,
    IntegerField,
    PasswordField,
    SelectField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import Email, EqualTo, InputRequired, Length, Optional, ValidationError

from app.models.user import User


class LoginForm(FlaskForm):
    email = EmailField("Email Address", validators=[InputRequired(), Email()])
    password = PasswordField("Password", validators=[InputRequired()])
    remember_me = BooleanField("Remember Me")
    submit = SubmitField("Sign In")


class RegisterForm(FlaskForm):
    email = EmailField("Email Address", validators=[InputRequired(), Email()])
    password = PasswordField(
        "Password",
        validators=[
            InputRequired(),
            Length(min=8, message="Password must be at least 8 characters long."),
        ],
    )
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[InputRequired(), EqualTo("password", message="Passwords must match.")],
    )
    role = SelectField(
        "Register As",
        choices=[("student", "Student / Learner"), ("therapist", "Speech-Language Therapist")],
        validators=[InputRequired()],
    )

    # Student specific fields
    date_of_birth_year = IntegerField(
        "Year of Birth (Optional)",
        validators=[Optional()],
    )

    # Therapist specific fields
    supervisor_email = EmailField(
        "Supervisor Email (Optional)",
        validators=[Optional(), Email()],
    )
    license_note = TextAreaField(
        "Professional License Note / Credentials",
        validators=[Optional(), Length(max=500)],
    )

    submit = SubmitField("Create Account")

    def validate_email(self, email: EmailField) -> None:
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError("Email is already registered. Please sign in.")

    def validate_date_of_birth_year(self, field: IntegerField) -> None:
        if field.data:
            current_year = datetime.utcnow().year
            if field.data < 1900 or field.data > current_year:
                raise ValidationError(
                    f"Please enter a valid birth year between 1900 and {current_year}."
                )


class ResetPasswordRequestForm(FlaskForm):
    email = EmailField("Email Address", validators=[InputRequired(), Email()])
    submit = SubmitField("Request Password Reset")


class ResetPasswordForm(FlaskForm):
    password = PasswordField(
        "New Password",
        validators=[
            InputRequired(),
            Length(min=8, message="Password must be at least 8 characters long."),
        ],
    )
    confirm_password = PasswordField(
        "Confirm New Password",
        validators=[InputRequired(), EqualTo("password", message="Passwords must match.")],
    )
    submit = SubmitField("Update Password")
