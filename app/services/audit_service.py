from flask import has_request_context, request
from flask_login import current_user

from app.extensions import db
from app.models.audit import AuditLog


class AuditService:
    @staticmethod
    def log_audit(action: str, user_id: int = None, ip_address: str = None) -> AuditLog:
        """Logs an action to the AuditLog table."""
        # 1. Fallback user_id to current_user if not provided and user is authenticated
        if not user_id and has_request_context():
            try:
                if current_user and current_user.is_authenticated:
                    user_id = current_user.id
            except Exception:
                pass

        # 2. Fallback ip_address to request.remote_addr if in request context
        if not ip_address and has_request_context():
            try:
                ip_address = request.remote_addr
            except Exception:
                pass

        # 3. Create and save AuditLog entry
        log_entry = AuditLog(user_id=user_id, action=action, ip_address=ip_address)
        try:
            db.session.add(log_entry)
            db.session.commit()
        except Exception:
            db.session.rollback()
            # In case of DB issues, print or log, but don't crash request
            pass

        return log_entry
