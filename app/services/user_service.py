from datetime import datetime
from typing import List, Optional

from app.extensions import db
from app.models.student import StudentProfile
from app.models.therapist import TherapistProfile
from app.models.user import User


class UserService:
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        return db.session.get(User, user_id)

    def get_user_by_email(self, email: str) -> Optional[User]:
        return User.query.filter_by(email=email).first()  # type: ignore[no-any-return]

    def create_user(
        self,
        email: str,
        password: str,
        role: str,
        is_verified: bool = False,
        date_of_birth_year: Optional[int] = None,
        assigned_therapist_id: Optional[int] = None,
        supervisor_id: Optional[int] = None,
        license_note: Optional[str] = None,
    ) -> User:
        user = User(email=email, role=role, is_verified=is_verified)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()  # To populate user.id

        if role == "student":
            student_profile = StudentProfile(
                user_id=user.id,
                date_of_birth_year=date_of_birth_year,
                assigned_therapist_id=assigned_therapist_id,
            )
            db.session.add(student_profile)
        elif role == "therapist":
            therapist_profile = TherapistProfile(
                user_id=user.id, supervisor_id=supervisor_id, license_note=license_note
            )
            db.session.add(therapist_profile)

        db.session.commit()
        return user

    def verify_user(self, user_id: int) -> bool:
        user = self.get_user_by_id(user_id)
        if user:
            user.is_verified = True
            db.session.commit()
            return True
        return False

    def update_last_login(self, user_id: int) -> None:
        user = self.get_user_by_id(user_id)
        if user:
            user.last_login = datetime.utcnow()
            db.session.commit()

    def set_user_status(self, user_id: int, is_active: bool) -> bool:
        user = self.get_user_by_id(user_id)
        if user:
            user.is_active = is_active
            db.session.commit()
            return True
        return False

    def change_user_role(self, user_id: int, new_role: str) -> bool:
        user = self.get_user_by_id(user_id)
        if not user:
            return False

        old_role = user.role
        if old_role == new_role:
            return True

        # Clean up old profile if role changed
        if old_role == "student" and user.student_profile:
            db.session.delete(user.student_profile)
        elif old_role == "therapist" and user.therapist_profile:
            db.session.delete(user.therapist_profile)

        user.role = new_role
        db.session.flush()

        # Create new profile
        if new_role == "student":
            student_profile = StudentProfile(user_id=user.id)
            db.session.add(student_profile)
        elif new_role == "therapist":
            therapist_profile = TherapistProfile(user_id=user.id)
            db.session.add(therapist_profile)

        db.session.commit()
        return True

    def get_all_therapists(self) -> List[User]:
        return User.query.filter_by(role="therapist").all()  # type: ignore[no-any-return]

    def get_all_students(self) -> List[User]:
        return User.query.filter_by(role="student").all()  # type: ignore[no-any-return]

    def get_all_users(self) -> List[User]:
        return User.query.all()  # type: ignore[no-any-return]
