from datetime import datetime

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from flask_login import UserMixin

from app.extensions import db

ph = PasswordHasher()


class User(UserMixin, db.Model):  # type: ignore[name-defined]
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(
        db.String(20), nullable=False, default="student"
    )  # student, therapist, supervisor, admin
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)

    def set_password(self, password: str) -> None:
        self.password_hash = ph.hash(password)

    def check_password(self, password: str) -> bool:
        try:
            return ph.verify(self.password_hash, password)
        except VerifyMismatchError:
            return False
        except Exception:
            return False

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role})>"
