from flask import Blueprint

recordings_bp = Blueprint("recordings", __name__)


@recordings_bp.route("/upload")
def upload() -> str:
    return "Recordings Upload Stub"
