from datetime import datetime

from app.extensions import db


class ExerciseAttempt(db.Model):  # type: ignore[name-defined]
    __tablename__ = "exercise_attempts"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exercise_id = db.Column(
        db.Integer, db.ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    audio_path = db.Column(db.String(255), nullable=False)
    transcription = db.Column(db.Text, nullable=True)

    # Whisper grading metrics
    accuracy_score = db.Column(db.Float, default=0.0)
    fluency_score = db.Column(db.Float, default=0.0)
    completeness_score = db.Column(db.Float, default=0.0)
    overall_score = db.Column(db.Float, default=0.0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return (
            f"<ExerciseAttempt {self.id}: Student {self.student_id} "
            f"Exercise {self.exercise_id} Score {self.overall_score}>"
        )
