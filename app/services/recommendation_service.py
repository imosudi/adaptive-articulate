from typing import List, Optional, Tuple

from app.extensions import db
from app.models.attempt import ExerciseAttempt
from app.models.exercise import Exercise
from app.models.recommendation import Recommendation


class RecommendationService:
    DIFFICULTIES = ["easy", "medium", "hard"]
    TYPES = ["sound", "word", "phrase", "sentence", "reading"]

    def get_pending_recommendation(self, student_id: int) -> Optional[Recommendation]:
        """Returns the current pending recommendation for a student if it exists."""
        rec = Recommendation.query.filter_by(student_id=student_id, status="pending").first()
        return rec  # type: ignore[no-any-return]

    def get_recommendation_history(self, student_id: int) -> List[Recommendation]:
        """Returns all recommendations for a student."""
        recs = (
            Recommendation.query.filter_by(student_id=student_id)
            .order_by(Recommendation.created_at.desc())
            .all()
        )
        return recs  # type: ignore[no-any-return]

    def _calculate_target(self, attempts: List[ExerciseAttempt]) -> Tuple[str, str]:
        """Calculates the target exercise type and difficulty based on attempts."""
        if not attempts:
            return "sound", "easy"

        last_attempt = attempts[0]
        last_exercise = last_attempt.exercise
        current_type = last_exercise.type
        current_diff = last_exercise.difficulty

        # Get the last 3 attempts of the current category type
        type_attempts = [att for att in attempts if att.exercise.type == current_type][:3]

        avg_score = sum(att.overall_score for att in type_attempts) / len(type_attempts)

        # Adaptive difficulty logic
        if avg_score < 70.0:
            target_type = current_type
            target_diff = "medium" if current_diff == "hard" else "easy"
        elif 70.0 <= avg_score <= 85.0:
            target_type = current_type
            target_diff = current_diff
        else:  # avg_score > 85.0
            if current_diff == "easy":
                target_type = current_type
                target_diff = "medium"
            elif current_diff == "medium":
                target_type = current_type
                target_diff = "hard"
            else:  # current_diff == "hard"
                # Move to the next category
                try:
                    idx = self.TYPES.index(current_type)
                    if idx < len(self.TYPES) - 1:
                        target_type = self.TYPES[idx + 1]
                        target_diff = "easy"
                    else:
                        target_type = current_type
                        target_diff = "hard"
                except ValueError:
                    target_type = "sound"
                    target_diff = "easy"

        return target_type, target_diff

    def _select_exercise(
        self,
        student_id: int,
        target_type: str,
        target_diff: str,
        attempts: List[ExerciseAttempt],
    ) -> Optional[Exercise]:
        """Finds a candidate exercise based on targets and student history."""
        # 1. Fetch exercises matching target_type and target_diff
        candidates: List[Exercise] = Exercise.query.filter_by(
            type=target_type, difficulty=target_diff
        ).all()

        # Exclude currently recommended exercises
        recommended_ids = {
            r.exercise_id for r in Recommendation.query.filter_by(student_id=student_id).all()
        }

        # Exclude exercises the student already succeeded at (score >= 85.0)
        passed_exercise_ids = {
            att.exercise_id for att in attempts if att.overall_score and att.overall_score >= 85.0
        }

        # Filter candidates of target difficulty & type that are not passed and not recommended
        active_candidates = [
            c for c in candidates if c.id not in passed_exercise_ids and c.id not in recommended_ids
        ]

        # Prioritize exercises that have NOT been attempted at all
        attempted_ids = {att.exercise_id for att in attempts}
        unattempted_candidates = [c for c in active_candidates if c.id not in attempted_ids]

        if unattempted_candidates:
            return unattempted_candidates[0]
        if active_candidates:
            return active_candidates[0]

        # Fallback 1: Try any exercise in the target category (any difficulty)
        # that has not been completed or recommended
        all_type_exercises: List[Exercise] = Exercise.query.filter_by(type=target_type).all()
        fallback_candidates = [
            ex
            for ex in all_type_exercises
            if ex.id not in passed_exercise_ids and ex.id not in recommended_ids
        ]
        fallback_unattempted = [ex for ex in fallback_candidates if ex.id not in attempted_ids]
        if fallback_unattempted:
            return fallback_unattempted[0]
        if fallback_candidates:
            return fallback_candidates[0]

        # Fallback 2: Try any exercise in the system not completed/recommended
        all_exercises: List[Exercise] = Exercise.query.all()
        general_fallbacks = [
            ex
            for ex in all_exercises
            if ex.id not in passed_exercise_ids and ex.id not in recommended_ids
        ]
        general_unattempted = [ex for ex in general_fallbacks if ex.id not in attempted_ids]
        if general_unattempted:
            return general_unattempted[0]
        if general_fallbacks:
            return general_fallbacks[0]

        # Fallback 3: Recommend any exercise in the system
        ex = Exercise.query.first()
        return ex  # type: ignore[no-any-return]

    def recommend_next(self, student_id: int) -> Optional[Recommendation]:
        """Generates and returns the next exercise recommendation for a student.

        If a pending recommendation already exists, it is returned instead
        of creating a duplicate.
        """
        # 1. Check if there is already a pending recommendation
        pending = self.get_pending_recommendation(student_id)
        if pending:
            return pending

        # 2. Get student attempts in reverse chronological order
        attempts = (
            ExerciseAttempt.query.filter_by(student_id=student_id)
            .order_by(ExerciseAttempt.created_at.desc())
            .all()
        )

        # 3. Calculate target category and difficulty
        target_type, target_diff = self._calculate_target(attempts)

        # 4. Select candidate exercise
        selected_exercise = self._select_exercise(student_id, target_type, target_diff, attempts)

        if not selected_exercise:
            return None

        # 5. Create and persist recommendation
        recommendation = Recommendation(
            student_id=student_id,
            exercise_id=selected_exercise.id,
            status="pending",
        )
        db.session.add(recommendation)
        db.session.commit()

        return recommendation

    def mark_recommendation_completed(self, student_id: int, exercise_id: int) -> bool:
        """Marks a recommendation as completed if the student attempts the exercise."""
        recommendation = Recommendation.query.filter_by(
            student_id=student_id, exercise_id=exercise_id, status="pending"
        ).first()
        if recommendation:
            recommendation.status = "completed"
            db.session.commit()
            return True
        return False
