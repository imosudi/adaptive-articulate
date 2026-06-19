import pytest

from app.extensions import db
from app.models.attempt import ExerciseAttempt
from app.models.exercise import Exercise
from app.models.recommendation import Recommendation
from app.services.exercise_service import ExerciseService
from app.services.recommendation_service import RecommendationService
from app.services.user_service import UserService


@pytest.fixture
def user_service():
    return UserService()


@pytest.fixture
def exercise_service():
    return ExerciseService()


@pytest.fixture
def rec_service():
    return RecommendationService()


@pytest.fixture
def setup_data(user_service, exercise_service):
    # Setup student
    student = user_service.create_user(
        "rec_student@example.com", "password", "student", is_verified=True
    )

    # Setup a bunch of exercises across difficulties and types
    ex_sound_easy1 = exercise_service.create_exercise("Sound Easy 1", "sound", "easy", "ah")
    ex_sound_easy2 = exercise_service.create_exercise("Sound Easy 2", "sound", "easy", "oo")
    ex_sound_med = exercise_service.create_exercise("Sound Medium 1", "sound", "medium", "sh")
    ex_sound_hard = exercise_service.create_exercise("Sound Hard 1", "sound", "hard", "th")

    ex_word_easy = exercise_service.create_exercise("Word Easy 1", "word", "easy", "apple")

    return {
        "student": student,
        "ex_sound_easy1": ex_sound_easy1,
        "ex_sound_easy2": ex_sound_easy2,
        "ex_sound_med": ex_sound_med,
        "ex_sound_hard": ex_sound_hard,
        "ex_word_easy": ex_word_easy,
    }


def test_recommend_new_student(client, rec_service, setup_data):
    """A student with no attempts should get an easy sound exercise recommended."""
    student = setup_data["student"]

    rec = rec_service.recommend_next(student.id)
    assert rec is not None
    assert rec.status == "pending"
    assert rec.exercise.type == "sound"
    assert rec.exercise.difficulty == "easy"


def test_recommend_prevent_duplicate_pending(client, rec_service, setup_data):
    """If a student has a pending recommendation, the service should return it instead of creating a duplicate."""
    student = setup_data["student"]

    rec1 = rec_service.recommend_next(student.id)
    rec2 = rec_service.recommend_next(student.id)

    assert rec1.id == rec2.id
    assert Recommendation.query.filter_by(student_id=student.id).count() == 1


def test_recommend_low_performance(client, rec_service, exercise_service, setup_data):
    """If a student gets < 70% on average, recommend an easier exercise of same type."""
    student = setup_data["student"]
    ex_sound_med = setup_data["ex_sound_med"]

    # Student attempts medium difficulty and gets low score (60%)
    attempt = ExerciseAttempt(
        student_id=student.id,
        exercise_id=ex_sound_med.id,
        audio_path="dummy.wav",
        transcription="sh",
        overall_score=60.0,
    )
    db.session.add(attempt)
    db.session.commit()

    rec = rec_service.recommend_next(student.id)
    assert rec is not None
    assert rec.exercise.type == "sound"
    assert rec.exercise.difficulty == "easy"


def test_recommend_mid_performance(client, rec_service, exercise_service, setup_data):
    """If a student gets between 70% and 85% average, recommend similar difficulty level."""
    student = setup_data["student"]
    ex_sound_easy1 = setup_data["ex_sound_easy1"]

    # Student attempts easy and gets 75%
    attempt = ExerciseAttempt(
        student_id=student.id,
        exercise_id=ex_sound_easy1.id,
        audio_path="dummy.wav",
        transcription="ah",
        overall_score=75.0,
    )
    db.session.add(attempt)
    db.session.commit()

    rec = rec_service.recommend_next(student.id)
    assert rec is not None
    assert rec.exercise.type == "sound"
    assert rec.exercise.difficulty == "easy"
    # Should recommend the other easy sound exercise (not completed yet)
    assert rec.exercise_id == setup_data["ex_sound_easy2"].id


def test_recommend_high_performance_graduates_difficulty(
    client, rec_service, exercise_service, setup_data
):
    """If student gets > 85% average, recommend next higher difficulty level of same type."""
    student = setup_data["student"]
    ex_sound_easy1 = setup_data["ex_sound_easy1"]

    # Student attempts easy and gets 95%
    attempt = ExerciseAttempt(
        student_id=student.id,
        exercise_id=ex_sound_easy1.id,
        audio_path="dummy.wav",
        transcription="ah",
        overall_score=95.0,
    )
    db.session.add(attempt)
    db.session.commit()

    rec = rec_service.recommend_next(student.id)
    assert rec is not None
    assert rec.exercise.type == "sound"
    assert rec.exercise.difficulty == "medium"


def test_recommend_high_performance_graduates_category(
    client, rec_service, exercise_service, setup_data
):
    """If student gets > 85% average on a hard exercise, recommend next category at easy level."""
    student = setup_data["student"]
    ex_sound_hard = setup_data["ex_sound_hard"]

    # Student attempts hard sound and gets 90%
    attempt = ExerciseAttempt(
        student_id=student.id,
        exercise_id=ex_sound_hard.id,
        audio_path="dummy.wav",
        transcription="th",
        overall_score=90.0,
    )
    db.session.add(attempt)
    db.session.commit()

    rec = rec_service.recommend_next(student.id)
    assert rec is not None
    assert rec.exercise.type == "word"
    assert rec.exercise.difficulty == "easy"


def test_mark_recommendation_completed(client, rec_service, setup_data):
    """Should correctly mark pending recommendation status as completed."""
    student = setup_data["student"]
    ex_sound_easy1 = setup_data["ex_sound_easy1"]

    # Set up pending recommendation
    rec = Recommendation(student_id=student.id, exercise_id=ex_sound_easy1.id, status="pending")
    db.session.add(rec)
    db.session.commit()

    success = rec_service.mark_recommendation_completed(student.id, ex_sound_easy1.id)
    assert success is True
    assert rec.status == "completed"
