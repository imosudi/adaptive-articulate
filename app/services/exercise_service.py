from typing import Any, List, Optional

from app.extensions import db
from app.models.exercise import Exercise


class ExerciseService:
    def get_exercise_by_id(self, exercise_id: int) -> Optional[Exercise]:
        return db.session.get(Exercise, exercise_id)

    def get_all_exercises(self) -> List[Exercise]:
        return Exercise.query.order_by(Exercise.created_at.desc()).all()  # type: ignore[no-any-return]

    def get_exercises_by_type(self, exercise_type: str) -> List[Exercise]:
        return Exercise.query.filter_by(type=exercise_type).all()  # type: ignore[no-any-return]

    def create_exercise(
        self,
        title: str,
        type: str,
        difficulty: str,
        prompt_text: str,
        reference_audio_path: Optional[str] = None,
    ) -> Exercise:
        exercise = Exercise(
            title=title,
            type=type,
            difficulty=difficulty,
            prompt_text=prompt_text,
            reference_audio_path=reference_audio_path,
        )
        db.session.add(exercise)
        db.session.commit()
        return exercise

    def update_exercise(self, exercise_id: int, **kwargs: Any) -> Optional[Exercise]:
        exercise = self.get_exercise_by_id(exercise_id)
        if not exercise:
            return None

        for key, value in kwargs.items():
            if hasattr(exercise, key):
                setattr(exercise, key, value)

        db.session.commit()
        return exercise

    def delete_exercise(self, exercise_id: int) -> bool:
        exercise = self.get_exercise_by_id(exercise_id)
        if not exercise:
            return False

        db.session.delete(exercise)
        db.session.commit()
        return True
