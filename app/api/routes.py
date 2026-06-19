from flask import Blueprint

api_bp = Blueprint("api", __name__)


@api_bp.route("/status")
def status() -> dict[str, str]:
    return {"status": "ok"}
