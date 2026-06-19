from flask import Blueprint

recommendations_bp = Blueprint("recommendations", __name__)


@recommendations_bp.route("/next")
def next_exercise() -> str:
    return "Recommendations Next Stub"
