import os
from pathlib import Path
from typing import Any, Optional

from flask import Flask, Response

from app.config import DevConfig, ProdConfig, TestConfig
from app.extensions import cache, csrf, db, limiter, login_manager, migrate


def create_app(config_name: Optional[str] = None) -> Flask:
    app = Flask(__name__)

    # 1. Load configuration
    if not config_name:
        config_name = os.environ.get("FLASK_ENV", "development")

    if config_name == "production":
        app.config.from_object(ProdConfig)
    elif config_name == "testing":
        app.config.from_object(TestConfig)
    else:
        app.config.from_object(DevConfig)

    # 2. Initialize Extensions
    db.init_app(app)

    # Import models to register on metadata
    from app.models.student import StudentProfile  # noqa: F401
    from app.models.therapist import TherapistProfile  # noqa: F401
    from app.models.user import User  # noqa: F401

    migrate.init_app(app, db)
    login_manager.init_app(app)
    limiter.init_app(app)
    cache.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str) -> Optional[Any]:
        from app.services.user_service import UserService

        return UserService().get_user_by_id(int(user_id))

    csrf.init_app(app)

    # 3. Create required directories
    upload_path = Path(app.config["UPLOAD_FOLDER"])
    for subfolder in ["recordings", "reference_audio", "reports", "temp"]:
        (upload_path / subfolder).mkdir(parents=True, exist_ok=True)

    # 4. Register Blueprints (defined in future steps)
    from app.admin.routes import admin_bp
    from app.analytics.routes import analytics_bp
    from app.api.routes import api_bp
    from app.auth.routes import auth_bp
    from app.exercises.routes import exercises_bp
    from app.recommendations.routes import recommendations_bp
    from app.recordings.routes import recordings_bp
    from app.reports.routes import reports_bp
    from app.users.routes import users_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(users_bp, url_prefix="/users")
    app.register_blueprint(exercises_bp, url_prefix="/exercises")
    app.register_blueprint(recordings_bp, url_prefix="/recordings")
    app.register_blueprint(analytics_bp, url_prefix="/analytics")
    app.register_blueprint(recommendations_bp, url_prefix="/recommendations")
    app.register_blueprint(reports_bp, url_prefix="/reports")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(api_bp, url_prefix="/api/v1")

    # 5. Security Headers
    @app.after_request
    def add_security_headers(response: Response) -> Response:
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Content-Security-Policy allowing standard layouts, Bootstrap 5 and Chart.js from CDNs
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data:; "
            "media-src 'self' blob:; "
            "connect-src 'self';"
        )
        return response

    return app
