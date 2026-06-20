
from app.extensions import db
from app.models.attempt import ExerciseAttempt


def login_as(client, email, password="password123"):
    return client.post(
        "/auth/login",
        data={"email": email, "password": password},
        follow_redirects=True,
    )


def test_reports_index_access(client, user_service):
    # Setup users
    user_service.create_user(
        "student_rep@example.com", "password123", "student", is_verified=True
    )
    user_service.create_user(
        "therapist_rep@example.com", "password123", "therapist", is_verified=True
    )
    user_service.create_user(
        "supervisor_rep@example.com", "password123", "supervisor", is_verified=True
    )
    user_service.create_user(
        "admin_rep@example.com", "password123", "admin", is_verified=True
    )

    # 1. Anonymous user gets redirected to login
    response = client.get("/reports/")
    assert response.status_code == 302

    # 2. Student access reports landing
    login_as(client, "student_rep@example.com")
    response = client.get("/reports/")
    assert response.status_code == 200
    client.get("/auth/logout")

    # 3. Therapist access reports landing
    login_as(client, "therapist_rep@example.com")
    response = client.get("/reports/")
    assert response.status_code == 200
    client.get("/auth/logout")

    # 4. Supervisor access reports landing
    login_as(client, "supervisor_rep@example.com")
    response = client.get("/reports/")
    assert response.status_code == 200
    client.get("/auth/logout")

    # 5. Admin access reports landing
    login_as(client, "admin_rep@example.com")
    response = client.get("/reports/")
    assert response.status_code == 200
    client.get("/auth/logout")


def test_reports_individual_downloads(client, user_service, exercise_service):
    # Setup users
    student1 = user_service.create_user(
        "stud1_rep@example.com", "password123", "student", is_verified=True
    )
    student2 = user_service.create_user(
        "stud2_rep@example.com", "password123", "student", is_verified=True
    )
    therapist = user_service.create_user(
        "ther_rep@example.com", "password123", "therapist", is_verified=True
    )
    supervisor = user_service.create_user(
        "super_rep@example.com", "password123", "supervisor", is_verified=True
    )
    user_service.create_user(
        "adm_rep@example.com", "password123", "admin", is_verified=True
    )

    # Assign student1 to therapist, and therapist to supervisor
    student1.student_profile.assigned_therapist_id = therapist.id
    therapist.therapist_profile.supervisor_id = supervisor.id
    db.session.commit()

    # Create some exercise and attempt data
    ex = exercise_service.create_exercise("Sound Easy", "sound", "easy", "ah")
    attempt = ExerciseAttempt(
        student_id=student1.id,
        exercise_id=ex.id,
        audio_path="dummy.wav",
        transcription="ah",
        overall_score=88.0,
        accuracy_score=90.0,
        fluency_score=85.0,
        completeness_score=90.0,
    )
    db.session.add(attempt)
    db.session.commit()

    # CASE 1: Student downloads own PDF report -> Success
    login_as(client, "stud1_rep@example.com")
    response = client.get(f"/reports/download?student_id={student1.id}&format=pdf")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/pdf"
    assert response.data.startswith(b"%PDF")

    # CASE 2: Student downloads own CSV report -> Success
    response = client.get(f"/reports/download?student_id={student1.id}&format=csv")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "text/csv; charset=utf-8"
    assert b"Attempt ID" in response.data
    assert b"stud1_rep@example.com" in response.data

    # CASE 3: Student tries to download other student's report -> Forbidden
    response = client.get(f"/reports/download?student_id={student2.id}&format=pdf")
    assert response.status_code == 403
    client.get("/auth/logout")

    # CASE 4: Therapist downloads assigned student's report -> Success
    login_as(client, "ther_rep@example.com")
    response = client.get(f"/reports/download?student_id={student1.id}&format=pdf")
    assert response.status_code == 200

    # CASE 5: Therapist downloads unassigned student's report -> Forbidden
    response = client.get(f"/reports/download?student_id={student2.id}&format=pdf")
    assert response.status_code == 403
    client.get("/auth/logout")

    # CASE 6: Supervisor downloads supervised therapist's student report -> Success
    login_as(client, "super_rep@example.com")
    response = client.get(f"/reports/download?student_id={student1.id}&format=pdf")
    assert response.status_code == 200

    # CASE 7: Supervisor downloads unsupervised student report -> Forbidden
    response = client.get(f"/reports/download?student_id={student2.id}&format=pdf")
    assert response.status_code == 403
    client.get("/auth/logout")

    # CASE 8: Admin downloads any student report -> Success
    login_as(client, "adm_rep@example.com")
    response = client.get(f"/reports/download?student_id={student2.id}&format=pdf")
    assert response.status_code == 200

    # CASE 9: Invalid student ID format -> Bad Request (400)
    response = client.get("/reports/download?student_id=abc&format=pdf")
    assert response.status_code == 400

    # CASE 10: Non-existent student -> Not Found (404)
    response = client.get("/reports/download?student_id=99999&format=pdf")
    assert response.status_code == 404

    # CASE 11: Invalid format -> Bad Request (400)
    response = client.get(f"/reports/download?student_id={student1.id}&format=invalid")
    assert response.status_code == 400


def test_reports_caseload_downloads(client, user_service, exercise_service):
    # Setup users
    student = user_service.create_user(
        "student_cs@example.com", "password123", "student", is_verified=True
    )
    therapist = user_service.create_user(
        "therapist_cs@example.com", "password123", "therapist", is_verified=True
    )
    user_service.create_user(
        "admin_cs@example.com", "password123", "admin", is_verified=True
    )

    # Assign student to therapist
    student.student_profile.assigned_therapist_id = therapist.id
    db.session.commit()

    # CASE 1: Student tries caseload CSV -> 403
    login_as(client, "student_cs@example.com")
    response = client.get("/reports/download?caseload=true&format=csv")
    assert response.status_code == 403
    client.get("/auth/logout")

    # CASE 2: Therapist downloads caseload CSV -> 200
    login_as(client, "therapist_cs@example.com")
    response = client.get("/reports/download?caseload=true&format=csv")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "text/csv; charset=utf-8"
    assert b"Attempt ID" in response.data
    client.get("/auth/logout")

    # CASE 3: Admin downloads caseload CSV -> 200
    login_as(client, "admin_cs@example.com")
    response = client.get(f"/reports/download?caseload=true&format=csv&therapist_id={therapist.id}")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "text/csv; charset=utf-8"
