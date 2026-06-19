from typing import Any

from flask import Blueprint, flash, redirect, request, url_for
from flask_login import login_required

from app.services.user_service import UserService
from app.utils.decorators import roles_required

admin_bp = Blueprint("admin", __name__)
user_service = UserService()


@admin_bp.route("/verify/<int:user_id>", methods=["POST"])
@login_required
@roles_required("admin")
def verify_user(user_id: int) -> Any:
    """Verifies a user's account."""
    success = user_service.verify_user(user_id)
    if success:
        flash("User verified successfully.", "success")
    else:
        flash("Failed to verify user.", "danger")
    return redirect(url_for("users.dashboard"))


@admin_bp.route("/status/<int:user_id>", methods=["POST"])
@login_required
@roles_required("admin")
def toggle_status(user_id: int) -> Any:
    """Toggles a user's active status."""
    user = user_service.get_user_by_id(user_id)
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("users.dashboard"))

    new_status = not user.is_active
    success = user_service.set_user_status(user_id, new_status)
    if success:
        action = "activated" if new_status else "deactivated"
        flash(f"User has been {action}.", "success")
    else:
        flash("Failed to update user status.", "danger")
    return redirect(url_for("users.dashboard"))


@admin_bp.route("/role/<int:user_id>", methods=["POST"])
@login_required
@roles_required("admin")
def change_role(user_id: int) -> Any:
    """Changes a user's system role."""
    new_role = request.form.get("role")
    if not new_role or new_role not in [
        "student",
        "therapist",
        "supervisor",
        "admin",
    ]:
        flash("Invalid role selected.", "danger")
        return redirect(url_for("users.dashboard"))

    success = user_service.change_user_role(user_id, new_role)
    if success:
        flash(f"User role updated to {new_role}.", "success")
    else:
        flash("Failed to change user role.", "danger")
    return redirect(url_for("users.dashboard"))
