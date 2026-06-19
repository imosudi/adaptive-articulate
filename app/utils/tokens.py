from typing import Optional

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


def get_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def generate_token(email: str, salt: str) -> str:
    """Generates a timed token containing the email."""
    ts = get_serializer()
    return ts.dumps(email, salt=salt)


def verify_token(token: str, salt: str, max_age: int = 3600) -> Optional[str]:
    """Verifies a timed token and returns the email if valid, or None if expired/invalid."""
    ts = get_serializer()
    try:
        email = str(ts.loads(token, salt=salt, max_age=max_age))
        return email
    except (SignatureExpired, BadSignature):
        return None
