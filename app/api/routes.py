import os
import secrets
from typing import Any

from flask import Blueprint, request
from flask_restx import Api, Resource, abort, fields

from app.extensions import db, limiter
from app.models.attempt import ExerciseAttempt
from app.models.exercise import Exercise
from app.models.recommendation import Recommendation
from app.models.student import StudentProfile
from app.models.user import User
from app.services.assessment_service import AssessmentService
from app.services.audit_service import AuditService
from app.services.exercise_service import ExerciseService
from app.services.recommendation_service import RecommendationService

api_bp = Blueprint("api", __name__)
exercise_service = ExerciseService()
assessment_service = AssessmentService()
rec_service = RecommendationService()

# Authorization Swagger Config
authorizations = {
    "apikey": {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-KEY",
    }
}

api = Api(
    api_bp,
    version="1.0",
    title="AdaptiveArticulate REST API",
    description="REST API endpoints for speech articulation and recommendations, fully secured with Token auth.",
    doc="/docs",
    authorizations=authorizations,
    security="apikey",
)

# Namespaces
ns_auth = api.namespace("auth", description="Authentication operations")
ns_exercises = api.namespace("exercises", description="Exercise management and retrieval")
ns_attempts = api.namespace("attempts", description="Speech attempt logging and assessment")
ns_recommendations = api.namespace(
    "recommendations", description="Student exercise recommendations"
)


def api_login_required(func: Any) -> Any:
    """Decorator to enforce api_token authentication on API endpoints."""

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        token = None
        # 1. Check X-API-KEY header
        if "X-API-KEY" in request.headers:
            token = request.headers["X-API-KEY"]
        # 2. Check Authorization Bearer header
        elif "Authorization" in request.headers:
            auth_header = request.headers["Authorization"]
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

        if not token:
            abort(401, "API token is missing. Provide X-API-KEY or Bearer token.")

        user = User.query.filter_by(api_token=token).first()
        if not user:
            abort(401, "Invalid or expired API token.")

        if not user.is_active:
            abort(403, "User account is inactive.")

        request.api_user = user  # type: ignore[attr-defined]
        return func(*args, **kwargs)

    # Required for RESTX method routing
    wrapper.__doc__ = func.__doc__
    wrapper.__name__ = func.__name__
    return wrapper


# RESTX Models
login_model = api.model(
    "LoginInput",
    {
        "email": fields.String(required=True, description="User email"),
        "password": fields.String(required=True, description="User password"),
    },
)

login_response = api.model(
    "LoginResponse",
    {
        "token": fields.String(description="API Token"),
        "role": fields.String(description="User role"),
        "email": fields.String(description="User email"),
    },
)

exercise_model = api.model(
    "Exercise",
    {
        "id": fields.Integer(readOnly=True, description="Exercise ID"),
        "title": fields.String(required=True, description="Exercise title"),
        "type": fields.String(required=True, description="Exercise type"),
        "difficulty": fields.String(required=True, description="Difficulty level"),
        "prompt_text": fields.String(required=True, description="Prompt text to articulate"),
        "reference_audio_path": fields.String(description="Reference audio file path"),
    },
)

attempt_model = api.model(
    "Attempt",
    {
        "id": fields.Integer(readOnly=True, description="Attempt ID"),
        "student_id": fields.Integer(description="Student ID"),
        "exercise_id": fields.Integer(description="Exercise ID"),
        "transcription": fields.String(description="Speech transcription"),
        "accuracy_score": fields.Float(description="Accuracy score"),
        "fluency_score": fields.Float(description="Fluency score"),
        "completeness_score": fields.Float(description="Completeness score"),
        "overall_score": fields.Float(description="Overall assessment score"),
        "created_at": fields.String(description="Logged timestamp"),
    },
)

recommendation_model = api.model(
    "Recommendation",
    {
        "id": fields.Integer(readOnly=True, description="Recommendation ID"),
        "student_id": fields.Integer(description="Student ID"),
        "exercise_id": fields.Integer(description="Recommended exercise ID"),
        "reason": fields.String(description="Reason for recommendation"),
        "is_completed": fields.Boolean(description="Is recommendation completed"),
    },
)


# --- AUTH ENDPOINTS ---
@ns_auth.route("/login")
class ApiLogin(Resource):
    @ns_auth.expect(login_model, validate=True)
    @ns_auth.response(200, "Success", login_response)
    @ns_auth.response(401, "Invalid credentials")
    @limiter.limit("10 per minute")
    def post(self) -> Any:
        """Authenticate user credentials and retrieve API Token."""
        data = request.json
        if not data:
            abort(400, "Request body is empty")

        user = User.query.filter_by(email=data.get("email")).first()
        if not user or not user.check_password(data.get("password")):
            AuditService.log_audit(f"API login failed for {data.get('email')}")
            abort(401, "Invalid email or password.")

        if not user.is_active:
            abort(403, "Account is deactivated.")

        # Generate API token if not present
        if not user.api_token:
            user.api_token = secrets.token_hex(32)
            db.session.commit()

        AuditService.log_audit(f"API Login successful: {user.email}", user_id=user.id)
        return {"token": user.api_token, "role": user.role, "email": user.email}, 200


# --- EXERCISES ENDPOINTS ---
@ns_exercises.route("")
class ApiExercisesList(Resource):
    @api.doc(security="apikey")
    @api_login_required
    @ns_exercises.marshal_list_with(exercise_model)
    def get(self) -> Any:
        """List all available exercises (filters: category, difficulty)."""
        category = request.args.get("category")
        difficulty = request.args.get("difficulty")

        query = Exercise.query
        if category:
            query = query.filter_by(type=category)
        if difficulty:
            query = query.filter_by(difficulty=difficulty)

        return query.order_by(Exercise.id.desc()).all()

    @api.doc(security="apikey")
    @api_login_required
    @ns_exercises.expect(exercise_model, validate=True)
    @ns_exercises.marshal_with(exercise_model, code=201)
    def post(self) -> Any:
        """Create a new exercise (Therapist/Admin only)."""
        user = request.api_user  # type: ignore[attr-defined]
        if user.role not in ["therapist", "admin"]:
            abort(403, "Therapist or Admin privileges required.")

        data = request.json
        if not data:
            abort(400, "Request body is empty")

        exercise = exercise_service.create_exercise(
            title=data["title"],
            type=data["type"],
            difficulty=data["difficulty"],
            prompt_text=data["prompt_text"],
            reference_audio_path=data.get("reference_audio_path"),
        )
        AuditService.log_audit(
            f"API Exercise Created: {exercise.title} (ID: {exercise.id})",
            user_id=user.id,
        )
        return exercise, 201


@ns_exercises.route("/<int:exercise_id>")
@ns_exercises.param("exercise_id", "The exercise identifier")
class ApiExerciseDetail(Resource):
    @api.doc(security="apikey")
    @api_login_required
    @ns_exercises.marshal_with(exercise_model)
    def get(self, exercise_id: int) -> Any:
        """Retrieve details of a specific exercise."""
        exercise = exercise_service.get_exercise_by_id(exercise_id)
        if not exercise:
            abort(404, "Exercise not found.")
        return exercise

    @api.doc(security="apikey")
    @api_login_required
    @ns_exercises.expect(exercise_model, validate=True)
    @ns_exercises.marshal_with(exercise_model)
    def put(self, exercise_id: int) -> Any:
        """Update an existing exercise (Therapist/Admin only)."""
        user = request.api_user  # type: ignore[attr-defined]
        if user.role not in ["therapist", "admin"]:
            abort(403, "Therapist or Admin privileges required.")

        exercise = exercise_service.get_exercise_by_id(exercise_id)
        if not exercise:
            abort(404, "Exercise not found.")

        data = request.json
        if not data:
            abort(400, "Request body is empty")

        updated = exercise_service.update_exercise(
            exercise_id=exercise_id,
            title=data["title"],
            type=data["type"],
            difficulty=data["difficulty"],
            prompt_text=data["prompt_text"],
            reference_audio_path=data.get("reference_audio_path"),
        )
        AuditService.log_audit(
            f"API Exercise Updated: {exercise.title} (ID: {exercise_id})",
            user_id=user.id,
        )
        return updated

    @api.doc(security="apikey")
    @api_login_required
    def delete(self, exercise_id: int) -> Any:
        """Delete an exercise (Therapist/Admin only)."""
        user = request.api_user  # type: ignore[attr-defined]
        if user.role not in ["therapist", "admin"]:
            abort(403, "Therapist or Admin privileges required.")

        success = exercise_service.delete_exercise(exercise_id)
        if not success:
            abort(404, "Exercise not found or delete failed.")

        AuditService.log_audit(f"API Exercise Deleted (ID: {exercise_id})", user_id=user.id)
        return {"success": True, "message": "Exercise deleted successfully."}, 200


# --- ATTEMPTS ENDPOINTS ---
@ns_attempts.route("")
class ApiAttempts(Resource):
    @api.doc(security="apikey")
    @api_login_required
    @ns_attempts.marshal_list_with(attempt_model)
    def get(self) -> Any:
        """List attempts history for authenticated user (student or caseload)."""
        user = request.api_user  # type: ignore[attr-defined]
        if user.role == "student":
            return ExerciseAttempt.query.filter_by(student_id=user.id).all()
        elif user.role == "therapist":
            students = StudentProfile.query.filter_by(assigned_therapist_id=user.id).all()
            student_ids = [sp.user_id for sp in students]
            if not student_ids:
                return []
            return ExerciseAttempt.query.filter(ExerciseAttempt.student_id.in_(student_ids)).all()
        elif user.role == "admin":
            return ExerciseAttempt.query.all()
        else:
            abort(403, "Role not authorized to view attempts.")

    @api.doc(security="apikey")
    @api_login_required
    @limiter.limit("5 per minute")
    def post(self) -> Any:
        """Submit audio file for speech assessment (Student only)."""
        user = request.api_user  # type: ignore[attr-defined]
        if user.role != "student":
            abort(403, "Only students can submit exercises for assessment.")

        exercise_id_str = request.form.get("exercise_id")
        if not exercise_id_str:
            abort(400, "Missing exercise_id in form parameters.")

        try:
            exercise_id = int(exercise_id_str)
        except ValueError:
            abort(400, "Invalid exercise_id format.")

        exercise = Exercise.query.get(exercise_id)
        if not exercise:
            abort(404, "Exercise not found.")

        if "audio" not in request.files:
            abort(400, "Missing audio file in upload.")

        audio_file = request.files["audio"]
        if audio_file.filename == "":
            abort(400, "Empty audio file name.")

        content_length = request.content_length
        if not content_length:
            audio_file.stream.seek(0, os.SEEK_END)
            content_length = audio_file.stream.tell()
            audio_file.stream.seek(0)

        # Validate audio
        is_valid, err_msg = assessment_service.validate_audio_file(audio_file, content_length)
        if not is_valid:
            abort(400, f"Audio validation failed: {err_msg}")

        # Assess
        try:
            attempt = assessment_service.process_assessment(
                student_id=user.id,
                exercise_id=exercise_id,
                file_storage=audio_file,
            )

            # Update recommendations
            rec_service.mark_recommendation_completed(user.id, exercise_id)
            rec_service.recommend_next(user.id)

            AuditService.log_audit(
                f"API Speech Assessment Logged: {attempt.exercise.title} (ID: {attempt.exercise_id})",
                user_id=user.id,
            )

            return {
                "success": True,
                "attempt_id": attempt.id,
                "transcription": attempt.transcription,
                "accuracy_score": attempt.accuracy_score,
                "fluency_score": attempt.fluency_score,
                "completeness_score": attempt.completeness_score,
                "overall_score": attempt.overall_score,
                "created_at": attempt.created_at.isoformat(),
            }, 201
        except Exception as e:
            abort(500, f"Speech processing engine error: {str(e)}")


# --- RECOMMENDATIONS ENDPOINTS ---
@ns_recommendations.route("")
class ApiRecommendations(Resource):
    @api.doc(security="apikey")
    @api_login_required
    @ns_recommendations.marshal_list_with(recommendation_model)
    def get(self) -> Any:
        """Get pending recommended exercises for the student user."""
        user = request.api_user  # type: ignore[attr-defined]
        if user.role != "student":
            abort(403, "Only students can query practice recommendations.")

        recs = Recommendation.query.filter_by(student_id=user.id, status="pending").all()
        if not recs:
            # Generate one on demand if empty
            rec = rec_service.recommend_next(user.id)
            return [rec] if rec else []
        return recs
