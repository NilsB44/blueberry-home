from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlmodel import func, select

from app.auth.deps import COOKIE_NAME, AdminUser, CurrentUser, DbSession
from app.auth.models import AuthSession, User
from app.auth.security import hash_password, hash_token, new_token, verify_password
from app.config import get_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])
users_router = APIRouter(prefix="/api/users", tags=["users"])

USERNAME_PATTERN = r"^[a-z0-9_.-]+$"


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=1, max_length=256)


class NewUser(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=USERNAME_PATTERN)
    display_name: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=10, max_length=256)
    is_admin: bool = False


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str
    is_admin: bool


class SetupStatus(BaseModel):
    needs_setup: bool


def _out(user: User) -> UserOut:
    return UserOut(
        id=user.id, username=user.username, display_name=user.display_name, is_admin=user.is_admin
    )


def _user_count(db: DbSession) -> int:
    return db.exec(select(func.count()).select_from(User)).one()


def _start_session(db: DbSession, response: Response, user: User) -> None:
    settings = get_settings()
    token = new_token()
    expires = datetime.now(UTC) + timedelta(days=settings.session_days)
    db.add(AuthSession(token_hash=hash_token(token), user_id=user.id, expires_at=expires))
    db.commit()
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=settings.session_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


@router.get("/setup")
def setup_status(db: DbSession) -> SetupStatus:
    return SetupStatus(needs_setup=_user_count(db) == 0)


@router.post("/setup", status_code=status.HTTP_201_CREATED)
def setup(body: NewUser, db: DbSession, response: Response) -> UserOut:
    """Create the first account. Only works while the hub has no users; that account is admin."""
    if _user_count(db) > 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "Already set up")
    user = User(
        username=body.username,
        display_name=body.display_name,
        password_hash=hash_password(body.password),
        is_admin=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    _start_session(db, response, user)
    return _out(user)


@router.post("/login")
def login(body: Credentials, db: DbSession, response: Response) -> UserOut:
    user = db.exec(select(User).where(User.username == body.username.lower())).first()
    if not verify_password(user.password_hash if user else None, body.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong username or password")
    _start_session(db, response, user)
    return _out(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    db: DbSession,
    response: Response,
    token: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
) -> None:
    if token and (session := db.get(AuthSession, hash_token(token))):
        db.delete(session)
        db.commit()
    response.delete_cookie(COOKIE_NAME, path="/")


@router.get("/me")
def me(user: CurrentUser) -> UserOut:
    return _out(user)


@users_router.get("")
def list_users(_: AdminUser, db: DbSession) -> list[UserOut]:
    return [_out(u) for u in db.exec(select(User).order_by(User.id))]


@users_router.post("", status_code=status.HTTP_201_CREATED)
def create_user(body: NewUser, _: AdminUser, db: DbSession) -> UserOut:
    if db.exec(select(User).where(User.username == body.username)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Username taken")
    user = User(
        username=body.username,
        display_name=body.display_name,
        password_hash=hash_password(body.password),
        is_admin=body.is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _out(user)
