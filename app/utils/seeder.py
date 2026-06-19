import click
from flask.cli import with_appcontext

from app.services.exercise_service import ExerciseService
from app.services.user_service import UserService


@click.command("seed-db")
@with_appcontext
def seed_db() -> None:
    """Seeds the database with initial users and exercises."""
    click.echo("Seeding database...")
    user_service = UserService()
    exercise_service = ExerciseService()

    # 1. Create Users
    # Admin
    admin = user_service.get_user_by_email("admin@example.com")
    if not admin:
        admin = user_service.create_user(
            email="admin@example.com",
            password="admin1234",
            role="admin",
            is_verified=True,
        )
        click.echo("Created admin user: admin@example.com")
    else:
        click.echo("Admin user already exists.")

    # Supervisor
    supervisor = user_service.get_user_by_email("supervisor@example.com")
    if not supervisor:
        supervisor = user_service.create_user(
            email="supervisor@example.com",
            password="password123",
            role="therapist",
            is_verified=True,
        )
        user_service.change_user_role(supervisor.id, "supervisor")
        click.echo("Created supervisor user: supervisor@example.com")
    else:
        click.echo("Supervisor user already exists.")

    # Therapist
    therapist = user_service.get_user_by_email("therapist@example.com")
    if not therapist:
        therapist = user_service.create_user(
            email="therapist@example.com",
            password="password123",
            role="therapist",
            is_verified=True,
            supervisor_id=supervisor.id,
            license_note="SLP-12345 Certified",
        )
        click.echo("Created therapist user: therapist@example.com")
    else:
        click.echo("Therapist user already exists.")

    # Student
    student = user_service.get_user_by_email("student@example.com")
    if not student:
        student = user_service.create_user(
            email="student@example.com",
            password="password123",
            role="student",
            is_verified=True,
            assigned_therapist_id=therapist.id,
            date_of_birth_year=2012,
        )
        click.echo("Created student user: student@example.com")
    else:
        click.echo("Student user already exists.")

    # 2. Create Exercises
    exercises_data = [
        {
            "title": "Initial 's' phoneme",
            "type": "sound",
            "difficulty": "easy",
            "prompt_text": "s",
        },
        {
            "title": "Word - Sunshine",
            "type": "word",
            "difficulty": "easy",
            "prompt_text": "sunshine",
        },
        {
            "title": "Word - Articulation",
            "type": "word",
            "difficulty": "medium",
            "prompt_text": "articulate",
        },
        {
            "title": "Phrase - Purple Paper",
            "type": "phrase",
            "difficulty": "medium",
            "prompt_text": "purple paper",
        },
        {
            "title": "Sentence - Seashells",
            "type": "sentence",
            "difficulty": "hard",
            "prompt_text": "she sells seashells by the seashore",
        },
        {
            "title": "Reading - Rainbow Passage",
            "type": "reading",
            "difficulty": "hard",
            "prompt_text": (
                "When the sunlight strikes raindrops in the air, they act as a prism "
                "and form a rainbow. The rainbow is a division of white light into "
                "many beautiful colors. These take the shape of a long round arch, "
                "with its path high above, and its two ends apparently beyond the horizon."
            ),
        },
    ]

    for data in exercises_data:
        from app.models.exercise import Exercise

        existing = Exercise.query.filter_by(title=data["title"]).first()
        if not existing:
            exercise_service.create_exercise(
                title=data["title"],
                type=data["type"],
                difficulty=data["difficulty"],
                prompt_text=data["prompt_text"],
            )
            click.echo(f"Created exercise: {data['title']}")
        else:
            click.echo(f"Exercise already exists: {data['title']}")

    click.echo("Seeding complete!")
