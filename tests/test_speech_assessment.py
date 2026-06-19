import io
import os
from unittest.mock import MagicMock, patch

import pytest
from flask import url_for
from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.models.attempt import ExerciseAttempt
from app.models.exercise import Exercise
from app.models.student import StudentProfile
from app.services.assessment_service import AssessmentService
from app.services.speech_assessment.engine import WhisperSpeechAssessmentEngine


# Helper to generate a valid in-memory WAV file with a RIFF/WAVE header
def create_in_memory_wav(
    content=b"\x00\x00\x00\x00", rate=16000, channels=1, width=2
) -> io.BytesIO:
    bio = io.BytesIO()
    data_size = len(content)
    bio.write(b"RIFF")
    bio.write((36 + data_size).to_bytes(4, "little"))
    bio.write(b"WAVE")
    bio.write(b"fmt ")
    bio.write((16).to_bytes(4, "little"))
    bio.write((1).to_bytes(2, "little"))
    bio.write((channels).to_bytes(2, "little"))
    bio.write((rate).to_bytes(4, "little"))
    bio.write((rate * channels * width).to_bytes(4, "little"))
    bio.write((channels * width).to_bytes(2, "little"))
    bio.write((width * 8).to_bytes(2, "little"))
    bio.write(b"data")
    bio.write((data_size).to_bytes(4, "little"))
    bio.write(content)
    bio.seek(0)
    return bio


@pytest.fixture
def mock_whisper_engine():
    with patch("app.services.speech_assessment.engine.whisper.load_model") as mock_load:
        mock_model = MagicMock()
        mock_load.return_value = mock_model
        engine = WhisperSpeechAssessmentEngine()
        yield engine, mock_model


def test_speech_assessment_engine_alignment(mock_whisper_engine):
    engine, mock_model = mock_whisper_engine

    # Case 1: Perfect match
    mock_model.transcribe.return_value = {"text": "hello world"}
    results = engine.assess(None, duration=1.0, prompt_text="hello world")
    assert results["accuracy_score"] == 100.0
    assert results["completeness_score"] == 100.0
    assert results["overall_score"] == 100.0

    # Case 2: Partial match
    mock_model.transcribe.return_value = {"text": "hello"}
    results = engine.assess(None, duration=1.0, prompt_text="hello world")
    assert results["completeness_score"] == 50.0
    assert results["accuracy_score"] < 100.0

    # Case 3: Empty transcript
    mock_model.transcribe.return_value = {"text": ""}
    results = engine.assess(None, duration=1.0, prompt_text="hello world")
    assert results["accuracy_score"] == 0.0
    assert results["completeness_score"] == 0.0
    assert results["overall_score"] == 0.0


def test_audio_validation():
    service = AssessmentService()

    # Case 1: Valid WAV
    wav_bio = create_in_memory_wav()
    file_storage = FileStorage(stream=wav_bio, filename="test.wav", content_type="audio/wav")
    is_valid, err = service.validate_audio_file(
        file_storage, content_length=len(wav_bio.getvalue())
    )
    assert is_valid is True

    # Case 2: File size too large
    is_valid, err = service.validate_audio_file(file_storage, content_length=6 * 1024 * 1024)
    assert is_valid is False
    assert "size limit" in err

    # Case 3: Unsupported extension
    invalid_file = FileStorage(stream=io.BytesIO(b"abc"), filename="test.txt")
    is_valid, err = service.validate_audio_file(invalid_file, content_length=3)
    assert is_valid is False
    assert "extension" in err

    # Case 4: Mismatched magic bytes
    bad_wav = FileStorage(stream=io.BytesIO(b"RIFFxxxxNOTWxxxx"), filename="test.wav")
    is_valid, err = service.validate_audio_file(bad_wav, content_length=16)
    assert is_valid is False
    assert "format" in err


def test_assess_endpoint(client, user_service, exercise_service):
    # Setup student user
    student = user_service.create_user(
        "student_rec@example.com", "password", "student", is_verified=True
    )
    # Setup exercise
    exercise = exercise_service.create_exercise("Test Prompt", "word", "easy", "apple")

    # Login
    client.post(
        "/auth/login",
        data={"email": "student_rec@example.com", "password": "password"},
        follow_redirects=True,
    )

    # Mock Whisper assessment in AssessmentService
    with (
        patch("app.services.assessment_service.AssessmentService.load_wav_to_numpy") as mock_load,
        patch("app.services.speech_assessment.engine.whisper.load_model") as mock_whisper,
    ):

        # Mock load WAV data
        mock_load.return_value = (None, 2.0)  # dummy array and duration

        # Mock Whisper model transcription
        mock_model = MagicMock()
        mock_whisper.return_value = mock_model
        mock_model.transcribe.return_value = {"text": "apple"}

        wav_bio = create_in_memory_wav()
        response = client.post(
            f"/recordings/assess/{exercise.id}",
            data={"audio": (wav_bio, "test.wav")},
            content_type="multipart/form-data",
        )

        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["success"] is True
        assert json_data["accuracy_score"] == 100.0
        assert json_data["transcribed_text"] == "apple"


def test_serve_file_security(client, user_service, exercise_service):
    # Setup users
    student1 = user_service.create_user(
        "stud1@example.com", "password", "student", is_verified=True
    )
    student2 = user_service.create_user(
        "stud2@example.com", "password", "student", is_verified=True
    )
    therapist = user_service.create_user(
        "therapist1@example.com", "password", "therapist", is_verified=True
    )

    # Update student profile assigning student1 to therapist
    student1.student_profile.assigned_therapist_id = therapist.id
    db.session.commit()

    exercise = exercise_service.create_exercise("Secure Prompt", "word", "easy", "pear")

    # Create dummy attempt for student1
    attempt = ExerciseAttempt(
        student_id=student1.id,
        exercise_id=exercise.id,
        audio_path="private_uploads/attempts/attempt_999.wav",
        transcription="pear",
        accuracy_score=100.0,
        fluency_score=100.0,
        completeness_score=100.0,
        overall_score=100.0,
    )
    db.session.add(attempt)
    db.session.commit()

    # Create dummy file on disk
    upload_dir = os.path.join(client.application.root_path, "private_uploads/attempts")
    os.makedirs(upload_dir, exist_ok=True)
    dummy_file_path = os.path.join(upload_dir, f"attempt_{attempt.id}.wav")
    with open(dummy_file_path, "wb") as f:
        f.write(create_in_memory_wav().getvalue())

    try:
        # Case 1: Student1 tries to fetch their own file -> 200
        client.post(
            "/auth/login",
            data={"email": "stud1@example.com", "password": "password"},
            follow_redirects=True,
        )
        res = client.get(f"/recordings/file/{attempt.id}")
        assert res.status_code == 200
        client.get("/auth/logout")

        # Case 2: Student2 tries to fetch Student1's file -> 403
        client.post(
            "/auth/login",
            data={"email": "stud2@example.com", "password": "password"},
            follow_redirects=True,
        )
        res = client.get(f"/recordings/file/{attempt.id}")
        assert res.status_code == 403
        client.get("/auth/logout")

        # Case 3: Assigned therapist tries to fetch student1's file -> 200
        client.post(
            "/auth/login",
            data={"email": "therapist1@example.com", "password": "password"},
            follow_redirects=True,
        )
        res = client.get(f"/recordings/file/{attempt.id}")
        assert res.status_code == 200
        client.get("/auth/logout")

    finally:
        # Cleanup file
        if os.path.exists(dummy_file_path):
            os.remove(dummy_file_path)
