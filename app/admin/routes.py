from flask import Blueprint

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/users")
def manage_users() -> str:
    return "Admin Users Stub"
