import os
from typing import Any

from flask import Blueprint, abort, current_app, jsonify, request, send_from_directory
from flask_login import current_user, login_required

from app.extensions import db
from app.models.attempt import ExerciseAttempt
from app.models.student import StudentProfile
from app.models.therapist import TherapistProfile
from app.services.assessment_service import AssessmentService

recordings_bp = Blueprint("recordings", __name__)
assessment_service = AssessmentService()


@recordings_bp.route("/assess/<int:exercise_id>", methods=["POST"])
@login_required
def assess(exercise_id: int) -> Any:
    """AJAX endpoint to assess an audio recording for a given exercise."""
    if "audio" not in request.files:
        return jsonify({"success": False, "error": "No audio file provided"}), 400

    audio_file = request.files["audio"]
    if audio_file.filename == "":
        return jsonify({"success": False, "error": "No selected file"}), 400

    # Get Content-Length from request or compute from stream size
    content_length = request.content_length
    if not content_length:
        audio_file.stream.seek(0, os.SEEK_END)
        content_length = audio_file.stream.tell()
        audio_file.stream.seek(0)  # Reset

    # 1. Validate audio file
    is_valid, err_msg = assessment_service.validate_audio_file(audio_file, content_length)
    if not is_valid:
        return jsonify({"success": False, "error": err_msg}), 400

    try:
        # 2. Process assessment (transcribe, score, save private file)
        attempt = assessment_service.process_assessment(
            student_id=current_user.id,
            exercise_id=exercise_id,
            file_storage=audio_file,
        )

        # 3. Handle recommendation updates asynchronously/proactively
        from app.services.recommendation_service import RecommendationService

        rec_service = RecommendationService()
        rec_service.mark_recommendation_completed(current_user.id, exercise_id)
        rec_service.recommend_next(current_user.id)

        return jsonify(
            {
                "success": True,
                "attempt_id": attempt.id,
                "transcribed_text": attempt.transcription,
                "accuracy_score": attempt.accuracy_score,
                "fluency_score": attempt.fluency_score,
                "completeness_score": attempt.completeness_score,
                "overall_score": attempt.overall_score,
                "created_at": attempt.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

    except Exception as e:
        current_app.logger.error(f"Speech assessment error: {str(e)}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "An error occurred during speech assessment processing.",
                }
            ),
            500,
        )


@recordings_bp.route("/file/<int:attempt_id>")
@login_required
def serve_file(attempt_id: int) -> Any:
    """Securely serve private audio recordings with strict access controls."""
    attempt = db.session.get(ExerciseAttempt, attempt_id)
    if not attempt:
        abort(404)

    # Enforce strict access control
    # 1. Student can only access their own attempts
    if current_user.role == "student":
        if attempt.student_id != current_user.id:
            abort(403)

    # 2. Therapist can only access their assigned student's attempts
    elif current_user.role == "therapist":
        student_profile = StudentProfile.query.filter_by(user_id=attempt.student_id).first()
        if not student_profile or student_profile.assigned_therapist_id != current_user.id:
            abort(403)

    # 3. Supervisor can only access their supervised therapists' student attempts
    elif current_user.role == "supervisor":
        student_profile = StudentProfile.query.filter_by(user_id=attempt.student_id).first()
        if not student_profile:
            abort(403)
        therapist_profile = TherapistProfile.query.filter_by(
            user_id=student_profile.assigned_therapist_id
        ).first()
        if not therapist_profile or therapist_profile.supervisor_id != current_user.id:
            abort(403)

    # 4. Admin has global access

    directory = os.path.join(current_app.root_path, "private_uploads/attempts")
    filename = f"attempt_{attempt.id}.wav"
    return send_from_directory(directory, filename)
