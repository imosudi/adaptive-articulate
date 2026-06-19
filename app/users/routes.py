from typing import Any

from flask import Blueprint, redirect, url_for
from flask_login import current_user, login_required

users_bp = Blueprint("users", __name__)


@users_bp.route("/dashboard")
@login_required
def dashboard_gate() -> Any:
    # If not verified, force redirect to unverified
    if not current_user.is_verified:
        return redirect(url_for("auth.unverified"))

    # Otherwise, redirect to the analytics dashboard which acts as the role-specific landing page
    return redirect(url_for("analytics.dashboard"))
