from typing import Any

from flask import Blueprint, Response, abort, render_template, request
from flask_login import current_user, login_required

from app.models.student import StudentProfile
from app.models.therapist import TherapistProfile
from app.models.user import User
from app.services.audit_service import AuditService
from app.services.reporting_service import ReportingService

reports_bp = Blueprint("reports", __name__)
reporting_service = ReportingService()


def has_report_access(student_id: int) -> bool:
    """Helper to check if current user has access to a student's report."""
    if current_user.role == "admin":
        return True

    if current_user.role == "student":
        return current_user.id == student_id

    if current_user.role == "therapist":
        student_profile = StudentProfile.query.filter_by(user_id=student_id).first()
        return (
            student_profile is not None and student_profile.assigned_therapist_id == current_user.id
        )

    if current_user.role == "supervisor":
        student_profile = StudentProfile.query.filter_by(user_id=student_id).first()
        if not student_profile:
            return False
        therapist_profile = TherapistProfile.query.filter_by(
            user_id=student_profile.assigned_therapist_id
        ).first()
        return therapist_profile is not None and therapist_profile.supervisor_id == current_user.id

    return False


@reports_bp.route("/")
@login_required
def index() -> Any:
    """Reports Hub landing page."""
    # Pass caseload data / lists depending on the role
    if current_user.role == "student":
        return render_template("reports/index.html")

    elif current_user.role == "therapist":
        students = current_user.students.all()
        return render_template("reports/index.html", students=students)

    elif current_user.role == "supervisor":
        therapists = current_user.supervised_therapists.all()
        return render_template("reports/index.html", therapists=therapists)

    elif current_user.role == "admin":
        students = StudentProfile.query.all()
        return render_template("reports/index.html", students=students)

    return abort(403)


@reports_bp.route("/download")
@login_required
def download() -> Any:
    """Download PDF or CSV reports for students or caseloads."""
    fmt = request.args.get("format", "pdf").lower()
    student_id_str = request.args.get("student_id")
    is_caseload = request.args.get("caseload", "false").lower() == "true"

    # 1. Handle Caseload CSV Export
    if is_caseload:
        if current_user.role not in ["therapist", "supervisor", "admin"]:
            abort(403)

        if current_user.role == "therapist":
            csv_data = reporting_service.generate_therapist_csv(current_user.id)
            AuditService.log_audit("Caseload CSV Exported", user_id=current_user.id)
            return Response(
                csv_data,
                mimetype="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=caseload_report_{current_user.id}.csv"
                },
            )
        elif current_user.role == "admin":
            # For admin, let them export caseload for a specific therapist if provided, otherwise all
            therapist_id_str = request.args.get("therapist_id")
            therapist_id = int(therapist_id_str) if therapist_id_str else current_user.id
            csv_data = reporting_service.generate_therapist_csv(therapist_id)
            AuditService.log_audit(
                f"Admin Caseload CSV Exported for Therapist {therapist_id}",
                user_id=current_user.id,
            )
            return Response(
                csv_data,
                mimetype="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=caseload_report_{therapist_id}.csv"
                },
            )
        else:
            # Supervisor / other roles can be handled similarly
            abort(403)

    # 2. Handle Individual Student Reports
    student_id = current_user.id
    if student_id_str:
        try:
            student_id = int(student_id_str)
        except ValueError:
            abort(400)

    # Access control
    if not has_report_access(student_id):
        abort(403)

    student = User.query.get(student_id)
    if not student:
        abort(404)

    if fmt == "pdf":
        pdf_data = reporting_service.generate_student_pdf(student_id)
        AuditService.log_audit(
            f"Student PDF Report Downloaded: {student.email}",
            user_id=current_user.id,
        )
        return Response(
            pdf_data,
            mimetype="application/pdf",
            headers={"Content-Disposition": f"inline; filename=report_{student_id}.pdf"},
        )
    elif fmt == "csv":
        csv_data = reporting_service.generate_student_csv(student_id)
        AuditService.log_audit(
            f"Student CSV Report Exported: {student.email}",
            user_id=current_user.id,
        )
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename=report_{student_id}.csv"},
        )

    return abort(400)
