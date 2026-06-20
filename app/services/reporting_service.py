import csv
import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models.attempt import ExerciseAttempt
from app.models.recommendation import Recommendation
from app.models.student import StudentProfile
from app.models.user import User


class ReportingService:
    def generate_student_pdf(self, student_id: int) -> bytes:
        """Generates a professional PDF articulation report for a student."""
        student = User.query.get(student_id)
        if not student:
            raise ValueError(f"Student with ID {student_id} not found.")

        profile = StudentProfile.query.filter_by(user_id=student_id).first()
        attempts = (
            ExerciseAttempt.query.filter_by(student_id=student_id)
            .order_by(ExerciseAttempt.created_at.desc())
            .all()
        )
        recommendations = (
            Recommendation.query.filter_by(student_id=student_id, is_completed=False)
            .order_by(Recommendation.created_at.desc())
            .all()
        )

        # Calculate metrics
        total_attempts = len(attempts)
        avg_overall = 0.0
        avg_accuracy = 0.0
        avg_fluency = 0.0
        avg_completeness = 0.0

        if total_attempts > 0:
            avg_overall = sum(a.overall_score for a in attempts) / total_attempts
            avg_accuracy = sum(a.accuracy_score for a in attempts) / total_attempts
            avg_fluency = sum(a.fluency_score for a in attempts) / total_attempts
            avg_completeness = sum(a.completeness_score for a in attempts) / total_attempts

        # Setup PDF document in memory
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=40,
            leftMargin=40,
            topMargin=40,
            bottomMargin=40,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            name="TitleStyle",
            parent=styles["Title"],
            fontSize=22,
            textColor=colors.HexColor("#6366f1"),  # Indico / Primary
            spaceAfter=15,
            alignment=0,  # Left aligned
        )
        subtitle_style = ParagraphStyle(
            name="SubtitleStyle",
            parent=styles["Normal"],
            fontSize=10,
            textColor=colors.HexColor("#64748b"),  # Slate / Muted
            spaceAfter=20,
        )
        h2_style = ParagraphStyle(
            name="H2Style",
            parent=styles["Heading2"],
            fontSize=14,
            textColor=colors.HexColor("#1e293b"),
            spaceBefore=15,
            spaceAfter=10,
        )
        body_style = ParagraphStyle(
            name="BodyStyle",
            parent=styles["BodyText"],
            fontSize=10,
            textColor=colors.HexColor("#334155"),
        )
        body_bold = ParagraphStyle(
            name="BodyBold",
            parent=body_style,
            fontSize=10,
            fontName="Helvetica-Bold",
        )
        table_header_style = ParagraphStyle(
            name="TableHeaderStyle",
            parent=styles["Normal"],
            fontSize=9,
            fontName="Helvetica-Bold",
            textColor=colors.white,
        )
        table_cell_style = ParagraphStyle(
            name="TableCellStyle",
            parent=styles["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#334155"),
        )

        story = []

        # Header Title
        story.append(Paragraph("Speech Articulation Progress Report", title_style))
        gen_time = datetime.now().strftime("%B %d, %Y at %I:%M %p")
        story.append(
            Paragraph(
                f"Generated on {gen_time} | System: AdaptiveArticulate",
                subtitle_style,
            )
        )

        # 1. Student Info Table
        therapist_email = (
            profile.therapist.email if profile and profile.therapist else "Not Assigned"
        )
        goal_mins = profile.daily_goal_minutes if profile else 15

        info_data = [
            [
                Paragraph("Student Email:", body_bold),
                Paragraph(student.email, body_style),
                Paragraph("Assigned Therapist:", body_bold),
                Paragraph(therapist_email, body_style),
            ],
            [
                Paragraph("Daily Goal:", body_bold),
                Paragraph(f"{goal_mins} minutes", body_style),
                Paragraph("Total Practice Attempts:", body_bold),
                Paragraph(str(total_attempts), body_style),
            ],
        ]
        info_table = Table(info_data, colWidths=[100, 160, 120, 150])
        info_table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ]
            )
        )
        story.append(info_table)
        story.append(Spacer(1, 20))

        # 2. Performance Summary metrics
        story.append(Paragraph("Performance Metrics Summary", h2_style))
        summary_data = [
            [
                Paragraph("Average Overall Score", table_header_style),
                Paragraph("Average Accuracy", table_header_style),
                Paragraph("Average Fluency", table_header_style),
                Paragraph("Average Completeness", table_header_style),
            ],
            [
                Paragraph(f"{avg_overall:.1f}%", table_cell_style),
                Paragraph(f"{avg_accuracy:.1f}%", table_cell_style),
                Paragraph(f"{avg_fluency:.1f}%", table_cell_style),
                Paragraph(f"{avg_completeness:.1f}%", table_cell_style),
            ],
        ]
        summary_table = Table(summary_data, colWidths=[132, 132, 132, 132])
        summary_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#6366f1")),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ]
            )
        )
        story.append(summary_table)
        story.append(Spacer(1, 20))

        # 3. Recommendations
        story.append(Paragraph("Active Recommendations", h2_style))
        if recommendations:
            rec_bullets = []
            for r in recommendations[:5]:  # show top 5 active recommendations
                status = "Not Started"
                if r.is_completed:
                    status = "Completed"
                rec_bullets.append(
                    [
                        Paragraph(r.exercise.title, table_cell_style),
                        Paragraph(r.exercise.type.capitalize(), table_cell_style),
                        Paragraph(r.exercise.difficulty.capitalize(), table_cell_style),
                        Paragraph(status, table_cell_style),
                    ]
                )

            rec_table_data = [
                [
                    Paragraph("Recommended Exercise", table_header_style),
                    Paragraph("Type", table_header_style),
                    Paragraph("Difficulty", table_header_style),
                    Paragraph("Status", table_header_style),
                ]
            ] + rec_bullets
            rec_table = Table(rec_table_data, colWidths=[200, 110, 110, 110])
            rec_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#475569")),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ]
                )
            )
            story.append(rec_table)
        else:
            story.append(
                Paragraph(
                    "No pending recommendations. Try complete a few exercises to get next-step suggestions.",
                    body_style,
                )
            )
        story.append(Spacer(1, 20))

        # 4. Attempt History
        story.append(Paragraph("Recent Attempt History", h2_style))
        if attempts:
            hist_rows = []
            for a in attempts[:10]:  # Limit to 10 for neat PDF layout
                date_str = a.created_at.strftime("%b %d, %Y %H:%M")
                hist_rows.append(
                    [
                        Paragraph(date_str, table_cell_style),
                        Paragraph(a.exercise.title, table_cell_style),
                        Paragraph(f"{a.accuracy_score:.0f}%", table_cell_style),
                        Paragraph(f"{a.fluency_score:.0f}%", table_cell_style),
                        Paragraph(f"{a.completeness_score:.0f}%", table_cell_style),
                        Paragraph(f"{a.overall_score:.0f}%", table_cell_style),
                    ]
                )

            hist_table_data = [
                [
                    Paragraph("Date / Time", table_header_style),
                    Paragraph("Exercise Title", table_header_style),
                    Paragraph("Accuracy", table_header_style),
                    Paragraph("Fluency", table_header_style),
                    Paragraph("Completeness", table_header_style),
                    Paragraph("Overall", table_header_style),
                ]
            ] + hist_rows
            hist_table = Table(hist_table_data, colWidths=[110, 172, 62, 62, 62, 62])
            hist_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("ALIGN", (2, 0), (-1, -1), "CENTER"),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ]
                )
            )
            story.append(hist_table)
        else:
            story.append(Paragraph("No practice attempts recorded yet.", body_style))

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes

    def generate_student_csv(self, student_id: int) -> bytes:
        """Generates a CSV file of a student's exercise attempt history."""
        student = User.query.get(student_id)
        if not student:
            raise ValueError(f"Student with ID {student_id} not found.")

        attempts = (
            ExerciseAttempt.query.filter_by(student_id=student_id)
            .order_by(ExerciseAttempt.created_at.desc())
            .all()
        )

        output = io.StringIO()
        writer = csv.writer(output)

        # Write Headers
        writer.writerow(
            [
                "Attempt ID",
                "Student Email",
                "Date",
                "Exercise Title",
                "Exercise Type",
                "Difficulty",
                "Accuracy Score",
                "Fluency Score",
                "Completeness Score",
                "Overall Score",
                "Transcription",
            ]
        )

        # Write Rows
        for a in attempts:
            writer.writerow(
                [
                    a.id,
                    student.email,
                    a.created_at.isoformat(),
                    a.exercise.title,
                    a.exercise.type,
                    a.exercise.difficulty,
                    a.accuracy_score,
                    a.fluency_score,
                    a.completeness_score,
                    a.overall_score,
                    a.transcription or "",
                ]
            )

        csv_content = output.getvalue()
        output.close()
        return csv_content.encode("utf-8")

    def generate_therapist_csv(self, therapist_id: int) -> bytes:
        """Generates a combined CSV file for all students assigned to a therapist."""
        therapist = User.query.get(therapist_id)
        if not therapist:
            raise ValueError(f"Therapist with ID {therapist_id} not found.")

        student_profiles = student_profiles = StudentProfile.query.filter_by(
            assigned_therapist_id=therapist_id
        ).all()
        student_ids = [sp.user_id for sp in student_profiles]

        if not student_ids:
            # Return empty CSV with headers
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(
                [
                    "Attempt ID",
                    "Student Email",
                    "Date",
                    "Exercise Title",
                    "Exercise Type",
                    "Difficulty",
                    "Accuracy Score",
                    "Fluency Score",
                    "Completeness Score",
                    "Overall Score",
                    "Transcription",
                ]
            )
            content = output.getvalue().encode("utf-8")
            output.close()
            return content

        attempts = (
            ExerciseAttempt.query.filter(ExerciseAttempt.student_id.in_(student_ids))
            .order_by(ExerciseAttempt.created_at.desc())
            .all()
        )

        output = io.StringIO()
        writer = csv.writer(output)

        # Write Headers
        writer.writerow(
            [
                "Attempt ID",
                "Student Email",
                "Date",
                "Exercise Title",
                "Exercise Type",
                "Difficulty",
                "Accuracy Score",
                "Fluency Score",
                "Completeness Score",
                "Overall Score",
                "Transcription",
            ]
        )

        for a in attempts:
            writer.writerow(
                [
                    a.id,
                    a.student.email,
                    a.created_at.isoformat(),
                    a.exercise.title,
                    a.exercise.type,
                    a.exercise.difficulty,
                    a.accuracy_score,
                    a.fluency_score,
                    a.completeness_score,
                    a.overall_score,
                    a.transcription or "",
                ]
            )

        csv_content = output.getvalue()
        output.close()
        return csv_content.encode("utf-8")
