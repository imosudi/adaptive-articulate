from app.models.exercise import Exercise


def login_as(client, email, password="password123"):
    return client.post(
        "/auth/login",
        data={"email": email, "password": password},
        follow_redirects=True,
    )


def test_exercise_service_crud(app_instance, exercise_service):
    # Test ExerciseService CRUD operations
    # Create
    exercise = exercise_service.create_exercise(
        title="Word - Sunshine",
        type="word",
        difficulty="easy",
        prompt_text="sunshine",
    )
    assert exercise.id is not None
    assert exercise.title == "Word - Sunshine"
    assert exercise.type == "word"
    assert exercise.difficulty == "easy"
    assert exercise.prompt_text == "sunshine"
    assert exercise.reference_audio_path is None

    # Read by id
    retrieved = exercise_service.get_exercise_by_id(exercise.id)
    assert retrieved is not None
    assert retrieved.title == "Word - Sunshine"

    # Read all
    all_ex = exercise_service.get_all_exercises()
    assert len(all_ex) == 1

    # Read by type
    by_type = exercise_service.get_exercises_by_type("word")
    assert len(by_type) == 1
    assert by_type[0].title == "Word - Sunshine"

    # Update
    updated = exercise_service.update_exercise(
        exercise.id,
        title="Word - Sun",
        difficulty="medium",
        prompt_text="sun",
    )
    assert updated is not None
    assert updated.title == "Word - Sun"
    assert updated.difficulty == "medium"
    assert updated.prompt_text == "sun"

    # Delete
    deleted = exercise_service.delete_exercise(exercise.id)
    assert deleted is True

    # Try to read after delete
    retrieved_after = exercise_service.get_exercise_by_id(exercise.id)
    assert retrieved_after is None


def test_exercises_list_view_requires_login(client):
    # Try to access exercise list without logging in
    response = client.get("/exercises/", follow_redirects=True)
    assert b"Sign In" in response.data


def test_exercises_route_rbac_student(client, user_service, exercise_service):
    # Create student and exercise
    student = user_service.create_user(
        "student@example.com", "password123", "student", is_verified=True
    )
    exercise = exercise_service.create_exercise(
        title="Initial 's' phoneme",
        type="sound",
        difficulty="easy",
        prompt_text="s",
    )

    login_res = login_as(client, "student@example.com")
    # List exercises - should succeed
    response = client.get("/exercises/")
    assert response.status_code == 200
    assert b"Initial &#39;s&#39; phoneme" in response.data
    assert b"Start Practising" in response.data
    assert b"Edit" not in response.data  # Should not see therapist edit button

    # Try to access create exercise - should be forbidden/redirected
    response = client.get("/exercises/create")
    assert response.status_code == 403

    # Try to post to create exercise
    response = client.post(
        "/exercises/create",
        data={
            "title": "Hack",
            "type": "word",
            "difficulty": "hard",
            "prompt_text": "hack",
        },
    )
    assert response.status_code == 403


def test_exercises_route_rbac_therapist(client, user_service, exercise_service):
    # Create therapist
    therapist = user_service.create_user(
        "therapist@example.com", "password123", "therapist", is_verified=True
    )

    login_as(client, "therapist@example.com")

    # Create exercise via POST
    response = client.post(
        "/exercises/create",
        data={
            "title": "Sentence - Seashells",
            "type": "sentence",
            "difficulty": "hard",
            "prompt_text": "she sells seashells",
            "reference_audio_path": "audio/seashells.wav",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Exercise created successfully!" in response.data
    assert b"Sentence - Seashells" in response.data
    assert b"Edit" in response.data  # Can edit

    # Find created exercise
    ex = Exercise.query.filter_by(title="Sentence - Seashells").first()
    assert ex is not None
    assert ex.difficulty == "hard"

    # Edit exercise
    response = client.post(
        f"/exercises/edit/{ex.id}",
        data={
            "title": "Sentence - Seashells Updated",
            "type": "sentence",
            "difficulty": "medium",
            "prompt_text": "she sells seashells updated",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Exercise updated successfully!" in response.data
    assert b"Sentence - Seashells Updated" in response.data

    # Delete exercise
    response = client.post(f"/exercises/delete/{ex.id}", follow_redirects=True)
    assert response.status_code == 200
    assert b"Exercise deleted successfully." in response.data

    # Verify deleted
    from app.extensions import db

    deleted_ex = db.session.get(Exercise, ex.id)
    assert deleted_ex is None
