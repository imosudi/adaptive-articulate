from datetime import datetime

from app.extensions import db


class Exercise(db.Model):  # type: ignore[name-defined]
    __tablename__ = "exercises"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    type = db.Column(
        db.String(50), nullable=False, index=True
    )  # sound, word, phrase, sentence, reading
    difficulty = db.Column(db.String(20), nullable=False)  # easy, medium, hard
    prompt_text = db.Column(db.Text, nullable=False)
    reference_audio_path = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    attempts = db.relationship("ExerciseAttempt", backref="exercise", cascade="all, delete-orphan")
    recommendations = db.relationship(
        "Recommendation", backref="exercise", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Exercise {self.id}: {self.title} ({self.difficulty})>"
