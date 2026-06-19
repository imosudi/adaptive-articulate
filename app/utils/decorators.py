from functools import wraps
from typing import Any, Callable

from flask import abort
from flask_login import current_user


def roles_required(*roles: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator that checks if the current logged-in user's role is in the allowed roles.
    Aborts with 403 Forbidden if the role is not allowed.
    """

    def decorator(f: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(f)
        def decorated_function(*args: Any, **kwargs: Any) -> Any:
            if not current_user.is_authenticated:
                abort(401)  # Unauthorized
            if current_user.role not in roles:
                abort(403)  # Forbidden
            return f(*args, **kwargs)

        return decorated_function

    return decorator
