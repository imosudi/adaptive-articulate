import io
from unittest.mock import MagicMock, patch

from app.extensions import db


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


def test_api_login(client, user_service):
    # Setup user
    user = user_service.create_user(
        "api_user@example.com", "password123", "student", is_verified=True
    )

    # 1. Test failed login
    response = client.post(
        "/api/v1/auth/login", json={"email": "api_user@example.com", "password": "wrongpassword"}
    )
    assert response.status_code == 401

    # 2. Test successful login
    response = client.post(
        "/api/v1/auth/login", json={"email": "api_user@example.com", "password": "password123"}
    )
    assert response.status_code == 200
    json_data = response.get_json()
    assert "token" in json_data
    assert json_data["role"] == "student"
    assert json_data["email"] == "api_user@example.com"

    # Check that token was persisted to database
    db.session.refresh(user)
    assert user.api_token == json_data["token"]


def test_api_exercise_list_and_detail(client, user_service, exercise_service):
    # Setup user and exercises
    student = user_service.create_user(
        "api_student@example.com", "password123", "student", is_verified=True
    )
    student.api_token = "student_token_123"
    db.session.commit()

    ex1 = exercise_service.create_exercise("Sound Easy", "sound", "easy", "ah")
    exercise_service.create_exercise("Word Hard", "word", "hard", "apple")

    headers = {"X-API-KEY": "student_token_123"}

    # 1. Fetch list
    response = client.get("/api/v1/exercises", headers=headers)
    assert response.status_code == 200
    json_data = response.get_json()
    assert len(json_data) == 2

    # 2. Fetch list with category filter
    response = client.get("/api/v1/exercises?category=sound", headers=headers)
    assert response.status_code == 200
    json_data = response.get_json()
    assert len(json_data) == 1
    assert json_data[0]["title"] == "Sound Easy"

    # 3. Fetch list with difficulty filter
    response = client.get("/api/v1/exercises?difficulty=hard", headers=headers)
    assert response.status_code == 200
    json_data = response.get_json()
    assert len(json_data) == 1
    assert json_data[0]["title"] == "Word Hard"

    # 4. Fetch detail
    response = client.get(f"/api/v1/exercises/{ex1.id}", headers=headers)
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["title"] == "Sound Easy"
    assert json_data["prompt_text"] == "ah"

    # 5. Fetch non-existent detail
    response = client.get("/api/v1/exercises/9999", headers=headers)
    assert response.status_code == 404


def test_api_exercise_rbac(client, user_service, exercise_service):
    # Setup users
    student = user_service.create_user(
        "api_stud_rbac@example.com", "password", "student", is_verified=True
    )
    student.api_token = "stud_token"

    therapist = user_service.create_user(
        "api_ther_rbac@example.com", "password", "therapist", is_verified=True
    )
    therapist.api_token = "ther_token"
    db.session.commit()

    ex = exercise_service.create_exercise("Sound Easy", "sound", "easy", "ah")

    # 1. Student tries to create/update/delete exercise -> 403
    stud_headers = {"X-API-KEY": "stud_token"}
    create_res = client.post(
        "/api/v1/exercises",
        json={"title": "New Sound", "type": "sound", "difficulty": "easy", "prompt_text": "oh"},
        headers=stud_headers,
    )
    assert create_res.status_code == 403

    update_res = client.put(
        f"/api/v1/exercises/{ex.id}",
        json={"title": "Sound Mod", "type": "sound", "difficulty": "easy", "prompt_text": "ah"},
        headers=stud_headers,
    )
    assert update_res.status_code == 403

    delete_res = client.delete(f"/api/v1/exercises/{ex.id}", headers=stud_headers)
    assert delete_res.status_code == 403

    # 2. Therapist manages exercises -> Success
    ther_headers = {"X-API-KEY": "ther_token"}
    create_res = client.post(
        "/api/v1/exercises",
        json={"title": "New Sound", "type": "sound", "difficulty": "easy", "prompt_text": "oh"},
        headers=ther_headers,
    )
    assert create_res.status_code == 201
    new_ex_id = create_res.get_json()["id"]

    update_res = client.put(
        f"/api/v1/exercises/{new_ex_id}",
        json={
            "title": "New Sound Mod",
            "type": "sound",
            "difficulty": "easy",
            "prompt_text": "oh!",
        },
        headers=ther_headers,
    )
    assert update_res.status_code == 200
    assert update_res.get_json()["title"] == "New Sound Mod"

    delete_res = client.delete(f"/api/v1/exercises/{new_ex_id}", headers=ther_headers)
    assert delete_res.status_code == 200


def test_api_attempt_submission_and_retrieval(client, user_service, exercise_service):
    # Setup users
    student = user_service.create_user(
        "api_stud_attempt@example.com", "password", "student", is_verified=True
    )
    student.api_token = "stud_token"

    therapist = user_service.create_user(
        "api_ther_attempt@example.com", "password", "therapist", is_verified=True
    )
    therapist.api_token = "ther_token"

    # Assign student to therapist caseload
    student.student_profile.assigned_therapist_id = therapist.id
    db.session.commit()

    ex = exercise_service.create_exercise("Sound Easy", "sound", "easy", "ah")

    # 1. Post attempt
    with (
        patch("app.services.assessment_service.AssessmentService.load_wav_to_numpy") as mock_load,
        patch("app.services.speech_assessment.engine.whisper.load_model") as mock_whisper,
    ):
        mock_load.return_value = (None, 2.0)
        mock_model = MagicMock()
        mock_whisper.return_value = mock_model
        mock_model.transcribe.return_value = {"text": "ah"}

        wav_bio = create_in_memory_wav()
        response = client.post(
            "/api/v1/attempts",
            data={"exercise_id": ex.id, "audio": (wav_bio, "test.wav")},
            content_type="multipart/form-data",
            headers={"Authorization": "Bearer stud_token"},
        )
        assert response.status_code == 201
        json_data = response.get_json()
        assert json_data["success"] is True
        assert json_data["transcription"] == "ah"
        assert json_data["accuracy_score"] == 100.0
        attempt_id = json_data["attempt_id"]

    # 2. Get attempts as student (only own attempts)
    response = client.get("/api/v1/attempts", headers={"X-API-KEY": "stud_token"})
    assert response.status_code == 200
    json_data = response.get_json()
    assert len(json_data) == 1
    assert json_data[0]["id"] == attempt_id

    # 3. Get attempts as therapist (caseload attempts)
    response = client.get("/api/v1/attempts", headers={"X-API-KEY": "ther_token"})
    assert response.status_code == 200
    json_data = response.get_json()
    assert len(json_data) == 1
    assert json_data[0]["id"] == attempt_id


def test_api_recommendations(client, user_service, exercise_service):
    # Setup student
    student = user_service.create_user(
        "api_rec_stud@example.com", "password", "student", is_verified=True
    )
    student.api_token = "stud_token"

    # Create exercise so recommendation service has something to recommend
    exercise_service.create_exercise("Sound Easy", "sound", "easy", "ah")
    db.session.commit()

    # Fetch recommendation
    response = client.get("/api/v1/recommendations", headers={"X-API-KEY": "stud_token"})
    assert response.status_code == 200
    json_data = response.get_json()
    assert len(json_data) == 1
    assert json_data[0]["is_completed"] is False
    assert json_data[0]["exercise_id"] is not None


def test_api_docs_redirect(client):
    response = client.get("/api/docs")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/api/v1/docs")
