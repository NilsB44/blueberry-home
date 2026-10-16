"""LAN file sharing: a shared space for the household plus a private space per user.

Files live on disk under HUB_FILES_DIR (shared/ and home/<user id>/), so the same folders can
also be exposed as a Samba network drive or synced with Syncthing (see docs/files.md).
Uploads stream straight to disk, one file per request, so phones can send large videos
without the Pi holding them in memory.
"""

import mimetypes
import os
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.auth.deps import CurrentUser
from app.config import get_settings

router = APIRouter(prefix="/api/files", tags=["files"])

Space = Literal["shared", "home"]
Kind = Literal["dir", "image", "video", "audio", "pdf", "text", "other"]

# Types the browser may show inline. Everything else downloads, so an uploaded HTML or SVG
# file can never run scripts on the hub's origin.
INLINE = ("image/jpeg", "image/png", "image/gif", "image/webp", "image/avif", "image/heic")
INLINE_PREFIXES = ("video/", "audio/")
TEXT_SUFFIXES = {".txt", ".md", ".csv", ".log", ".json", ".yaml", ".yml"}


class Entry(BaseModel):
    name: str
    kind: Kind
    size: int
    modified: datetime


class Listing(BaseModel):
    space: Space
    path: str
    entries: list[Entry]


class Usage(BaseModel):
    total: int
    used: int
    free: int
    max_upload: int


class NewFolder(BaseModel):
    path: str = ""
    name: str = Field(min_length=1, max_length=255)


class Rename(BaseModel):
    path: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=255)


class Move(BaseModel):
    path: str = Field(min_length=1)
    to_space: Space
    to_dir: str = ""


def space_root(space: Space, user_id: int) -> Path:
    base = get_settings().files_dir
    root = base / "shared" if space == "shared" else base / "home" / str(user_id)
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def resolve(root: Path, rel: str) -> Path:
    """Map a client path onto disk, refusing anything that escapes the space."""
    if "\0" in rel:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Bad path")
    target = (root / rel.strip("/")).resolve()
    if target != root and root not in target.parents:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Bad path")
    return target


def check_name(name: str) -> str:
    name = name.strip()
    if (
        not name
        or name in (".", "..")
        or "/" in name
        or "\\" in name
        or "\0" in name
        or len(name.encode()) > 255
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid name")
    return name


def free_name(folder: Path, name: str) -> Path:
    """photo.jpg, then photo (1).jpg, photo (2).jpg, ... so uploads never overwrite."""
    target = folder / name
    stem, suffix = Path(name).stem, Path(name).suffix
    n = 1
    while target.exists():
        target = folder / f"{stem} ({n}){suffix}"
        n += 1
    return target


def kind_of(path: Path) -> Kind:
    if path.is_dir():
        return "dir"
    mime = mimetypes.guess_type(path.name)[0] or ""
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("video/"):
        return "video"
    if mime.startswith("audio/"):
        return "audio"
    if mime == "application/pdf":
        return "pdf"
    if path.suffix.lower() in TEXT_SUFFIXES:
        return "text"
    return "other"


def rel_to(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix() if path != root else ""


def root_dep(space: Space, user: CurrentUser) -> Path:
    return space_root(space, user.id)


Root = Annotated[Path, Depends(root_dep)]


@router.get("/usage")
def usage(_: CurrentUser) -> Usage:
    base = get_settings().files_dir
    base.mkdir(parents=True, exist_ok=True)
    du = shutil.disk_usage(base)
    return Usage(
        total=du.total, used=du.used, free=du.free, max_upload=get_settings().max_upload_mb << 20
    )


@router.get("/{space}/list")
def list_dir(space: Space, root: Root, path: str = "") -> Listing:
    folder = resolve(root, path)
    if not folder.is_dir():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such folder")
    entries = []
    for p in folder.iterdir():
        if p.name.startswith(".hub-upload-"):
            continue
        st = p.stat()
        entries.append(
            Entry(
                name=p.name,
                kind=kind_of(p),
                size=0 if p.is_dir() else st.st_size,
                modified=datetime.fromtimestamp(st.st_mtime, UTC),
            )
        )
    entries.sort(key=lambda e: (e.kind != "dir", e.name.lower()))
    return Listing(space=space, path=rel_to(root, folder), entries=entries)


@router.get("/{space}/raw")
def download(root: Root, path: str, download: bool = False) -> FileResponse:
    target = resolve(root, path)
    if not target.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such file")
    mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    inline = not download and (mime in INLINE or mime.startswith(INLINE_PREFIXES))
    if not download and mime == "application/pdf":
        inline = True
    if not download and target.suffix.lower() in TEXT_SUFFIXES:
        mime, inline = "text/plain; charset=utf-8", True
    disposition = "inline" if inline else "attachment"
    return FileResponse(
        target,
        media_type=mime,
        headers={
            "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(target.name)}",
            "Content-Security-Policy": "sandbox",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=3600",
        },
    )


@router.put("/{space}/upload", status_code=status.HTTP_201_CREATED)
async def upload(request: Request, root: Root, name: str, path: str = "") -> Entry:
    folder = resolve(root, path)
    if not folder.is_dir():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such folder")
    name = check_name(name)
    limit = get_settings().max_upload_mb << 20
    declared = request.headers.get("content-length")
    if declared and int(declared) > limit:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "File is too large")
    if declared and int(declared) > shutil.disk_usage(folder).free - (256 << 20):
        raise HTTPException(status.HTTP_507_INSUFFICIENT_STORAGE, "Not enough free space")

    # Write to a hidden temp file in the same folder, then rename: a dropped connection
    # never leaves half a file behind under the real name.
    fd, tmp = tempfile.mkstemp(prefix=".hub-upload-", dir=folder)
    size = 0
    try:
        with os.fdopen(fd, "wb") as out:
            async for chunk in request.stream():
                size += len(chunk)
                if size > limit:
                    raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "File is too large")
                out.write(chunk)
        target = free_name(folder, name)
        os.replace(tmp, target)
        os.chmod(target, 0o644)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    st = target.stat()
    return Entry(
        name=target.name,
        kind=kind_of(target),
        size=st.st_size,
        modified=datetime.fromtimestamp(st.st_mtime, UTC),
    )


@router.post("/{space}/folder", status_code=status.HTTP_201_CREATED)
def new_folder(body: NewFolder, root: Root) -> dict:
    parent = resolve(root, body.path)
    if not parent.is_dir():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such folder")
    target = parent / check_name(body.name)
    if target.exists():
        raise HTTPException(status.HTTP_409_CONFLICT, "Something with that name already exists")
    target.mkdir()
    return {"path": rel_to(root, target)}


@router.post("/{space}/rename")
def rename(body: Rename, root: Root) -> dict:
    source = resolve(root, body.path)
    if source == root or not source.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    target = source.parent / check_name(body.name)
    if target.exists():
        raise HTTPException(status.HTTP_409_CONFLICT, "Something with that name already exists")
    source.rename(target)
    return {"path": rel_to(root, target)}


@router.post("/{space}/move")
def move(body: Move, root: Root, user: CurrentUser) -> dict:
    """Move between folders or between spaces, e.g. from My files to Shared."""
    source = resolve(root, body.path)
    if source == root or not source.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    dest_root = space_root(body.to_space, user.id)
    dest_dir = resolve(dest_root, body.to_dir)
    if not dest_dir.is_dir():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such folder")
    if dest_dir == source or source in dest_dir.parents:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Can't move a folder into itself")
    target = free_name(dest_dir, source.name)
    shutil.move(source, target)
    return {"space": body.to_space, "path": rel_to(dest_root, target)}


@router.delete("/{space}", status_code=status.HTTP_204_NO_CONTENT)
def delete(root: Root, path: str) -> None:
    target = resolve(root, path)
    if target == root or not target.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    if target.is_dir() and not target.is_symlink():
        shutil.rmtree(target)
    else:
        target.unlink()
