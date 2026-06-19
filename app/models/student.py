from app.extensions import db


class StudentProfile(db.Model):  # type: ignore[name-defined]
    __tablename__ = "student_profiles"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    date_of_birth_year = db.Column(db.Integer, nullable=True)
    assigned_therapist_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    daily_goal_minutes = db.Column(db.Integer, nullable=False, default=15)

    # Relationships
    user = db.relationship(
        "User",
        foreign_keys=[user_id],
        backref=db.backref("student_profile", uselist=False, cascade="all, delete-orphan"),
    )
    therapist = db.relationship(
        "User", foreign_keys=[assigned_therapist_id], backref=db.backref("students", lazy="dynamic")
    )
