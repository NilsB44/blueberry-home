from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlmodel import Session

from app.auth.models import AuthSession, User
from app.auth.security import hash_token
from app.db import get_session

COOKIE_NAME = "hub_session"

DbSession = Annotated[Session, Depends(get_session)]


SEEN_EVERY = timedelta(minutes=5)


def session_for_token(db: Session, token: str | None) -> AuthSession | None:
    if not token:
        return None
    session = db.get(AuthSession, hash_token(token))
    if session is None or _aware(session.expires_at) < datetime.now(UTC):
        return None
    return session


def user_for_token(db: Session, token: str | None) -> User | None:
    """The person a session cookie belongs to, or None if it's missing or expired."""
    session = session_for_token(db, token)
    return db.get(User, session.user_id) if session else None


def current_user(
    request: Request,
    db: DbSession,
    token: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
) -> User:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not logged in")
    session = session_for_token(db, token)
    user = db.get(User, session.user_id) if session else None
    if session is None or user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired")
    now = datetime.now(UTC)
    if session.last_seen_at is None or now - _aware(session.last_seen_at) > SEEN_EVERY:
        session.last_seen_at = now
        session.last_ip = request.client.host[:64] if request.client else None
        db.add(session)
        db.commit()
        db.refresh(user)
    return user


def admin_user(user: Annotated[User, Depends(current_user)]) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admins only")
    return user


def owner_user(user: Annotated[User, Depends(current_user)]) -> User:
    if not user.is_owner:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the hub's owner can do this")
    return user


def _aware(dt: datetime) -> datetime:
    # SQLite drops tzinfo on round-trip; values are always written in UTC.
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


CurrentUser = Annotated[User, Depends(current_user)]
AdminUser = Annotated[User, Depends(admin_user)]
OwnerUser = Annotated[User, Depends(owner_user)]
