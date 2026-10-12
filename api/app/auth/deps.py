from datetime import UTC, datetime
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlmodel import Session

from app.auth.models import AuthSession, User
from app.auth.security import hash_token
from app.db import get_session

COOKIE_NAME = "hub_session"

DbSession = Annotated[Session, Depends(get_session)]


def current_user(
    db: DbSession, token: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None
) -> User:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not logged in")
    session = db.get(AuthSession, hash_token(token))
    if session is None or _aware(session.expires_at) < datetime.now(UTC):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired")
    user = db.get(User, session.user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not logged in")
    return user


def admin_user(user: Annotated[User, Depends(current_user)]) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admins only")
    return user


def _aware(dt: datetime) -> datetime:
    # SQLite drops tzinfo on round-trip; values are always written in UTC.
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


CurrentUser = Annotated[User, Depends(current_user)]
AdminUser = Annotated[User, Depends(admin_user)]
