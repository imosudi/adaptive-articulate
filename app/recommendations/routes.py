from typing import Any

from flask import Blueprint, flash, redirect, url_for
from flask_login import current_user, login_required

from app.services.recommendation_service import RecommendationService
from app.utils.decorators import roles_required

recommendations_bp = Blueprint("recommendations", __name__)
rec_service = RecommendationService()


@recommendations_bp.route("/next")
@login_required
@roles_required("student")
def next_exercise() -> Any:
    """Fetch the next recommended exercise and redirect the student to it."""
    recommendation = rec_service.recommend_next(current_user.id)
    if recommendation:
        return redirect(url_for("exercises.practice", exercise_id=recommendation.exercise_id))

    flash("No recommended exercises available at the moment.", "info")
    return redirect(url_for("users.dashboard"))
