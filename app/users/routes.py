from datetime import date, timedelta
from typing import Any, Dict, List

from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.models.attempt import ExerciseAttempt
from app.models.audit import AuditLog
from app.models.user import User
from app.services.recommendation_service import RecommendationService
from app.services.user_service import UserService

users_bp = Blueprint("users", __name__)
user_service = UserService()
rec_service = RecommendationService()


def calculate_streak(student_id: int) -> int:
    """Calculates student's consecutive active days of exercise attempts."""
    attempts = (
        ExerciseAttempt.query.filter_by(student_id=student_id)
        .order_by(ExerciseAttempt.created_at.desc())
        .all()
    )
    if not attempts:
        return 0

    unique_dates = sorted(list(set(att.created_at.date() for att in attempts)), reverse=True)
    today = date.today()
    yesterday = today - timedelta(days=1)

    if unique_dates[0] not in (today, yesterday):
        return 0

    streak = 1
    current_date = unique_dates[0]
    for d in unique_dates[1:]:
        if d == current_date - timedelta(days=1):
            streak += 1
            current_date = d
        elif d == current_date:
            continue
        else:
            break
    return streak


def _student_dashboard() -> Any:
    """Helper to render the student dashboard view."""
    # Get all attempts
    attempts = (
        ExerciseAttempt.query.filter_by(student_id=current_user.id)
        .order_by(ExerciseAttempt.created_at.desc())
        .all()
    )

    # Get or generate recommendation
    recommendation = rec_service.get_pending_recommendation(current_user.id)
    if not recommendation:
        recommendation = rec_service.recommend_next(current_user.id)

    # Calculate streak
    streak = calculate_streak(current_user.id)

    # Calculate progress today (each attempt = 3 minutes of practice)
    profile = current_user.student_profile
    daily_goal = profile.daily_goal_minutes if profile else 15
    today_attempts = [att for att in attempts if att.created_at.date() == date.today()]
    progress_minutes = len(today_attempts) * 3
    progress_percent = min(100, int((progress_minutes / daily_goal) * 100))

    # Chart Data: average score over the last 7 days
    chart_labels: List[str] = []
    chart_scores: List[float] = []
    for i in range(6, -1, -1):
        d = date.today() - timedelta(days=i)
        chart_labels.append(d.strftime("%b %d"))
        day_attempts = [att for att in attempts if att.created_at.date() == d]
        if day_attempts:
            avg = sum(att.overall_score for att in day_attempts) / len(day_attempts)
            chart_scores.append(round(avg, 1))
        else:
            chart_scores.append(0.0)

    recent_attempts = attempts[:5]

    return render_template(
        "dashboards/student.html",
        recommendation=recommendation,
        streak=streak,
        daily_goal=daily_goal,
        progress_minutes=progress_minutes,
        progress_percent=progress_percent,
        chart_labels=chart_labels,
        chart_scores=chart_scores,
        recent_attempts=recent_attempts,
    )


def _therapist_dashboard() -> Any:
    """Helper to render the therapist dashboard view."""
    # Get therapist's assigned student profiles
    student_profiles = current_user.students.all()
    student_ids = [sp.user_id for sp in student_profiles]

    # Recent attempts from these students
    recent_attempts = (
        ExerciseAttempt.query.filter(ExerciseAttempt.student_id.in_(student_ids))
        .order_by(ExerciseAttempt.created_at.desc())
        .limit(10)
        .all()
        if student_ids
        else []
    )

    # Underperformance Alerts: average of last 3 attempts is < 70%
    alerts: List[Dict[str, Any]] = []
    for sp in student_profiles:
        student_attempts = (
            ExerciseAttempt.query.filter_by(student_id=sp.user_id)
            .order_by(ExerciseAttempt.created_at.desc())
            .limit(3)
            .all()
        )
        if len(student_attempts) >= 2:
            avg_score = sum(att.overall_score for att in student_attempts) / len(student_attempts)
            if avg_score < 70.0:
                alerts.append(
                    {
                        "student": sp.user,
                        "avg_score": round(avg_score, 1),
                        "last_attempt_date": student_attempts[0].created_at,
                    }
                )

    return render_template(
        "dashboards/therapist.html",
        students=student_profiles,
        recent_attempts=recent_attempts,
        alerts=alerts,
    )


def _supervisor_dashboard() -> Any:
    """Helper to render the supervisor dashboard view."""
    # Get supervised therapists
    therapist_profiles = current_user.supervised_therapists.all()
    therapists_data: List[Dict[str, Any]] = []

    for tp in therapist_profiles:
        t_user = tp.user
        t_students = t_user.students.all()
        t_student_ids = [sp.user_id for sp in t_students]

        # Aggregated metrics for this therapist's caseload
        total_attempts = 0
        avg_score = 0.0

        if t_student_ids:
            attempts_query = ExerciseAttempt.query.filter(
                ExerciseAttempt.student_id.in_(t_student_ids)
            ).all()
            total_attempts = len(attempts_query)
            if total_attempts > 0:
                avg_score = round(
                    sum(att.overall_score for att in attempts_query) / total_attempts,
                    1,
                )

        therapists_data.append(
            {
                "user": t_user,
                "student_count": len(t_students),
                "total_attempts": total_attempts,
                "avg_score": avg_score,
            }
        )

    return render_template("dashboards/supervisor.html", therapists=therapists_data)


def _admin_dashboard() -> Any:
    """Helper to render the admin dashboard view."""
    # Fetch all users
    all_users = User.query.order_by(User.created_at.desc()).all()
    # Fetch audit logs
    audit_logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(50).all()

    return render_template("dashboards/admin.html", users=all_users, audit_logs=audit_logs)


@users_bp.route("/dashboard")
@login_required
def dashboard_gate() -> Any:
    # If not verified, force redirect to unverified page
    if not current_user.is_verified:
        return redirect(url_for("auth.unverified"))

    # Render dashboard based on user's role
    role = current_user.role

    if role == "student":
        return _student_dashboard()
    elif role == "therapist":
        return _therapist_dashboard()
    elif role == "supervisor":
        return _supervisor_dashboard()
    elif role == "admin":
        return _admin_dashboard()

    return "Unknown Role Dashboard"
