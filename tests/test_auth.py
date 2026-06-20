


def test_register_student(client, user_service):
    # Test registration of a student
    response = client.post(
        "/auth/register",
        data={
            "email": "student@example.com",
            "password": "password123",
            "confirm_password": "password123",
            "role": "student",
            "date_of_birth_year": 2010,
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Registration successful!" in response.data

    user = user_service.get_user_by_email("student@example.com")
    assert user is not None
    assert user.role == "student"
    assert user.student_profile.date_of_birth_year == 2010
    assert not user.is_verified


def test_register_duplicate_email(client, user_service):
    # Setup: create existing user
    user_service.create_user("student@example.com", "password123", "student")

    # Try registering with duplicate email
    response = client.post(
        "/auth/register",
        data={
            "email": "student@example.com",
            "password": "password123",
            "confirm_password": "password123",
            "role": "student",
        },
    )
    assert response.status_code == 200
    assert b"Email is already registered" in response.data


def test_register_therapist_with_supervisor(client, user_service):
    # Setup: create supervisor user
    supervisor = user_service.create_user("supervisor@example.com", "password123", "therapist")
    # Change role to supervisor to verify
    user_service.change_user_role(supervisor.id, "supervisor")

    # Register therapist with supervisor
    response = client.post(
        "/auth/register",
        data={
            "email": "therapist@example.com",
            "password": "password123",
            "confirm_password": "password123",
            "role": "therapist",
            "supervisor_email": "supervisor@example.com",
            "license_note": "License #12345",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Registration successful!" in response.data

    therapist = user_service.get_user_by_email("therapist@example.com")
    assert therapist is not None
    assert therapist.therapist_profile.supervisor_id == supervisor.id
    assert therapist.therapist_profile.license_note == "License #12345"


def test_email_verification(client, user_service):
    user = user_service.create_user(
        "student@example.com", "password123", "student", is_verified=False
    )
    assert not user.is_verified

    from app.utils.tokens import generate_token

    token = generate_token(user.email, salt="email-verification")

    # Verify email
    response = client.get(f"/auth/verify/{token}", follow_redirects=True)
    assert response.status_code == 200
    assert b"Your email has been verified!" in response.data

    user = user_service.get_user_by_id(user.id)
    assert user.is_verified


def test_email_verification_invalid_token(client):
    response = client.get("/auth/verify/invalid-token", follow_redirects=True)
    assert response.status_code == 200
    assert b"The verification link is invalid or has expired." in response.data


def test_login_and_logout(client, user_service):
    user = user_service.create_user(
        "student@example.com", "password123", "student", is_verified=True
    )

    # Login successfully
    response = client.post(
        "/auth/login",
        data={"email": "student@example.com", "password": "password123"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Sign Out" in response.data or b"Analytics Dashboard Stub" in response.data

    # Logout
    response = client.get("/auth/logout", follow_redirects=True)
    assert response.status_code == 200
    assert b"Sign In" in response.data


def test_login_unverified(client, user_service):
    user = user_service.create_user(
        "student@example.com", "password123", "student", is_verified=False
    )

    # Login should redirect to unverified
    response = client.post(
        "/auth/login",
        data={"email": "student@example.com", "password": "password123"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Verify Your Email" in response.data


def test_password_reset(client, user_service):
    user = user_service.create_user(
        "student@example.com", "password123", "student", is_verified=True
    )

    # Request password reset
    response = client.post(
        "/auth/reset-password",
        data={"email": "student@example.com"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    from app.utils.tokens import generate_token

    token = generate_token(user.email, salt="password-reset")

    # Complete reset
    response = client.post(
        f"/auth/reset-password/{token}",
        data={"password": "newpassword123", "confirm_password": "newpassword123"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Your password has been reset!" in response.data

    # Attempt to log in with new password
    response = client.post(
        "/auth/login",
        data={"email": "student@example.com", "password": "newpassword123"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Sign Out" in response.data or b"Analytics Dashboard Stub" in response.data
