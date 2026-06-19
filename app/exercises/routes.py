from typing import Any

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import login_required

from app.exercises.forms import ExerciseForm
from app.services.exercise_service import ExerciseService
from app.utils.decorators import roles_required

exercises_bp = Blueprint("exercises", __name__)
exercise_service = ExerciseService()


@exercises_bp.route("/")
@login_required
def index() -> Any:
    exercises = exercise_service.get_all_exercises()
    return render_template("exercises/list.html", exercises=exercises)


@exercises_bp.route("/create", methods=["GET", "POST"])
@login_required
@roles_required("therapist", "admin")
def create() -> Any:
    form = ExerciseForm()
    if form.validate_on_submit():
        exercise_service.create_exercise(
            title=form.title.data,
            type=form.type.data,
            difficulty=form.difficulty.data,
            prompt_text=form.prompt_text.data,
            reference_audio_path=form.reference_audio_path.data or None,
        )
        flash("Exercise created successfully!", "success")
        return redirect(url_for("exercises.index"))

    return render_template("exercises/create.html", form=form)


@exercises_bp.route("/edit/<int:exercise_id>", methods=["GET", "POST"])
@login_required
@roles_required("therapist", "admin")
def edit(exercise_id: int) -> Any:
    exercise = exercise_service.get_exercise_by_id(exercise_id)
    if not exercise:
        flash("Exercise not found.", "danger")
        return redirect(url_for("exercises.index"))

    form = ExerciseForm(obj=exercise)
    if form.validate_on_submit():
        exercise_service.update_exercise(
            exercise_id=exercise_id,
            title=form.title.data,
            type=form.type.data,
            difficulty=form.difficulty.data,
            prompt_text=form.prompt_text.data,
            reference_audio_path=form.reference_audio_path.data or None,
        )
        flash("Exercise updated successfully!", "success")
        return redirect(url_for("exercises.index"))

    return render_template("exercises/edit.html", form=form, exercise=exercise)


@exercises_bp.route("/delete/<int:exercise_id>", methods=["POST"])
@login_required
@roles_required("therapist", "admin")
def delete(exercise_id: int) -> Any:
    success = exercise_service.delete_exercise(exercise_id)
    if success:
        flash("Exercise deleted successfully.", "success")
    else:
        flash("Failed to delete exercise.", "danger")
    return redirect(url_for("exercises.index"))


@exercises_bp.route("/practice/<int:exercise_id>")
@login_required
def practice(exercise_id: int) -> Any:
    exercise = exercise_service.get_exercise_by_id(exercise_id)
    if not exercise:
        flash("Exercise not found.", "danger")
        return redirect(url_for("exercises.index"))
    return render_template("exercises/practice.html", exercise=exercise)
