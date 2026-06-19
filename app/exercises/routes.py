from flask import Blueprint

exercises_bp = Blueprint("exercises", __name__)


@exercises_bp.route("/")
def index() -> str:
    return "Exercises Stub"
