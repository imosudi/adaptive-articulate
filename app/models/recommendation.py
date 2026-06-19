from datetime import datetime

from app.extensions import db


class Recommendation(db.Model):  # type: ignore[name-defined]
    __tablename__ = "recommendations"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exercise_id = db.Column(
        db.Integer, db.ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False
    )
    assigned_by_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status = db.Column(db.String(20), default="pending")  # pending, completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return (
            f"<Recommendation {self.id}: Student {self.student_id} "
            f"Exercise {self.exercise_id} ({self.status})>"
        )
