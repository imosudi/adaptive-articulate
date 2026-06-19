from typing import Any

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.auth.forms import LoginForm, RegisterForm, ResetPasswordForm, ResetPasswordRequestForm
from app.extensions import db
from app.models.user import User
from app.services.user_service import UserService
from app.utils.tokens import generate_token, verify_token

auth_bp = Blueprint("auth", __name__)
user_service = UserService()


@auth_bp.route("/register", methods=["GET", "POST"])
def register() -> Any:
    if current_user.is_authenticated:
        return redirect(url_for("users.dashboard_gate"))

    form = RegisterForm()
    if form.validate_on_submit():
        supervisor_id = None
        if form.role.data == "therapist" and form.supervisor_email.data:
            supervisor = User.query.filter_by(email=form.supervisor_email.data).first()
            if supervisor and supervisor.role in [
                "supervisor",
                "admin",
                "therapist",
            ]:
                supervisor_id = supervisor.id
            else:
                flash(
                    "Supervisor email not found or user is not a supervisor.",
                    "danger",
                )
                return render_template("auth/register.html", form=form)

        user = user_service.create_user(
            email=form.email.data,
            password=form.password.data,
            role=form.role.data,
            is_verified=False,
            date_of_birth_year=form.date_of_birth_year.data,
            assigned_therapist_id=None,
            supervisor_id=supervisor_id,
            license_note=form.license_note.data,
        )

        token = generate_token(user.email, salt="email-verification")
        verify_url = url_for("auth.verify_email", token=token, _external=True)

        # Flash verification url in dev mode
        flash(
            "Registration successful! Please check your email to verify your account. "
            f"Dev verification link: {verify_url}",
            "success",
        )
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login() -> Any:
    if current_user.is_authenticated:
        return redirect(url_for("users.dashboard_gate"))

    form = LoginForm()
    if form.validate_on_submit():
        user = user_service.get_user_by_email(form.email.data)
        if user and user.check_password(form.password.data):
            if not user.is_active:
                flash(
                    "Your account has been deactivated. Please contact support.",
                    "danger",
                )
                return render_template("auth/login.html", form=form)

            login_user(user, remember=form.remember_me.data)
            user_service.update_last_login(user.id)

            if not user.is_verified:
                flash("Please verify your email to unlock all features.", "warning")
                return redirect(url_for("auth.unverified"))

            next_page = request.args.get("next")
            return redirect(next_page or url_for("users.dashboard_gate"))

        flash("Invalid email or password.", "danger")

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout() -> Any:
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/verify/<token>")
def verify_email(token: str) -> Any:
    email = verify_token(token, salt="email-verification", max_age=86400)
    if not email:
        flash("The verification link is invalid or has expired.", "danger")
        return redirect(url_for("auth.login"))

    user = user_service.get_user_by_email(email)
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("auth.login"))

    if user.is_verified:
        flash("Email already verified.", "info")
    else:
        user_service.verify_user(user.id)
        flash("Your email has been verified! You can now log in.", "success")

    return redirect(url_for("auth.login"))


@auth_bp.route("/unverified")
@login_required
def unverified() -> Any:
    if current_user.is_verified:
        return redirect(url_for("users.dashboard_gate"))
    return render_template("auth/unverified.html")


@auth_bp.route("/resend-verification")
@login_required
def resend_verification() -> Any:
    if current_user.is_verified:
        return redirect(url_for("users.dashboard_gate"))

    token = generate_token(current_user.email, salt="email-verification")
    verify_url = url_for("auth.verify_email", token=token, _external=True)

    flash(
        f"A new verification link has been generated. Dev link: {verify_url}",
        "success",
    )
    return redirect(url_for("auth.unverified"))


@auth_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password_request() -> Any:
    if current_user.is_authenticated:
        return redirect(url_for("users.dashboard_gate"))

    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = user_service.get_user_by_email(form.email.data)
        if user:
            token = generate_token(user.email, salt="password-reset")
            reset_url = url_for("auth.reset_password", token=token, _external=True)
            flash(
                f"Password reset link generated. Dev link: {reset_url}",
                "success",
            )
        else:
            # Prevent user enumeration by flashing the same message
            flash(
                "If that email address exists, a password reset link has been generated.",
                "info",
            )
        return redirect(url_for("auth.login"))

    return render_template("auth/reset-password-request.html", form=form)


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token: str) -> Any:
    if current_user.is_authenticated:
        return redirect(url_for("users.dashboard_gate"))

    email = verify_token(token, salt="password-reset", max_age=3600)
    if not email:
        flash("The password reset link is invalid or has expired.", "danger")
        return redirect(url_for("auth.reset_password_request"))

    user = user_service.get_user_by_email(email)
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("auth.reset_password_request"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash("Your password has been reset! Please sign in with your new password.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset-password.html", form=form)
