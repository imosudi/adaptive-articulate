from flask import Blueprint

analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.route("/dashboard")
def dashboard() -> str:
    return "Analytics Dashboard Stub"
