from flask import Blueprint

reports_bp = Blueprint("reports", __name__)


@reports_bp.route("/download")
def download() -> str:
    return "Reports Download Stub"
