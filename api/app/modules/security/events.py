from sqlmodel import Session

from app.modules.security.models import SecurityEvent


def log_event(
    session: Session,
    action: str,
    detail: str = "",
    user_id: int | None = None,
    ip: str | None = None,
) -> None:
    session.add(
        SecurityEvent(
            action=action, detail=detail[:300], user_id=user_id, ip=(ip or None) and ip[:64]
        )
    )
    session.commit()
