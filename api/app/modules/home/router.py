"""Each person's home-screen arrangement: which apps sit in which folders, and in what order.

The web app owns the meaning of the layout; the API only checks its shape and size and stores it,
so a layout that names an app that no longer exists is fine (the web app drops it).
"""

from typing import Annotated, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.auth.deps import CurrentUser, DbSession
from app.auth.models import utcnow
from app.modules.home.models import HomeLayout

router = APIRouter(prefix="/api/home", tags=["home"])

Id = Annotated[str, Field(min_length=1, max_length=64)]


class LayoutApp(BaseModel):
    type: Literal["app"]
    id: Id


class LayoutFolder(BaseModel):
    type: Literal["folder"]
    id: Id
    name: str = Field(min_length=1, max_length=40)
    apps: list[Id] = Field(max_length=100)


class Layout(BaseModel):
    items: list[Annotated[LayoutApp | LayoutFolder, Field(discriminator="type")]] = Field(
        max_length=200
    )


@router.get("/layout")
def get_layout(user: CurrentUser, db: DbSession) -> Layout | None:
    row = db.get(HomeLayout, user.id)
    return Layout.model_validate_json(row.data) if row else None


@router.put("/layout")
def put_layout(layout: Layout, user: CurrentUser, db: DbSession) -> Layout:
    row = db.get(HomeLayout, user.id) or HomeLayout(user_id=user.id, data="")
    row.data = layout.model_dump_json()
    row.updated_at = utcnow()
    db.add(row)
    db.commit()
    return layout


@router.delete("/layout", status_code=204)
def reset_layout(user: CurrentUser, db: DbSession) -> None:
    row = db.get(HomeLayout, user.id)
    if row:
        db.delete(row)
        db.commit()
