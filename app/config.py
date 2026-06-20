import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-12345")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{BASE_DIR}/adaptive_articulate.db"
    )

    # Upload Settings
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024  # 25 MB
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", str(BASE_DIR / "uploads"))

    # Cache Configuration
    CACHE_TYPE = "SimpleCache"
    CACHE_DEFAULT_TIMEOUT = 300

    # Rate Limiter
    RATELIMIT_STORAGE_URI = "memory://"
    RATELIMIT_DEFAULT_LIMITS = ["200 per day", "50 per hour"]

    # Security Cookies
    SESSION_COOKIE_SECURE = False  # Set to True in ProdConfig with HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = False
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"


class DevConfig(Config):
    DEBUG = True


class TestConfig(Config):
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False


class ProdConfig(Config):
    DEBUG = False
    # In production, require actual secure cookies
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True

    # Parse and enforce PostgreSQL for production database
    _raw_db_url = os.environ.get("DATABASE_URL", "")
    if _raw_db_url:
        if _raw_db_url.startswith("postgres://"):
            _raw_db_url = _raw_db_url.replace("postgres://", "postgresql://", 1)
        SQLALCHEMY_DATABASE_URI = _raw_db_url
    else:
        # Fallback to local PostgreSQL database
        SQLALCHEMY_DATABASE_URI = (
            "postgresql://postgres:postgres@localhost:5432/adaptive_articulate"
        )

    # Validate that SQLite or other non-Postgres databases are not used in production
    if not SQLALCHEMY_DATABASE_URI.startswith("postgresql"):
        raise ValueError(
            f"Production database must use PostgreSQL. Provided URI: {SQLALCHEMY_DATABASE_URI}"
        )
