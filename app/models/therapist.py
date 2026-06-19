from app.extensions import db


class TherapistProfile(db.Model):  # type: ignore[name-defined]
    __tablename__ = "therapist_profiles"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    supervisor_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    license_note = db.Column(db.Text, nullable=True)

    # Relationships
    user = db.relationship(
        "User",
        foreign_keys=[user_id],
        backref=db.backref("therapist_profile", uselist=False, cascade="all, delete-orphan"),
    )
    supervisor = db.relationship(
        "User",
        foreign_keys=[supervisor_id],
        backref=db.backref("supervised_therapists", lazy="dynamic"),
    )
