import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.auth.deps import CurrentUser
from app.auth.network import LocalNetworkOnly
from app.auth.router import router as auth_router
from app.auth.router import users_router
from app.config import get_settings
from app.db import init_db
from app.modules import MODULES, ModuleInfo
from app.modules.assistant.router import router as assistant_router
from app.modules.files.router import router as files_router
from app.modules.learn.router import router as learn_router
from app.modules.poker.router import router as poker_router
from app.modules.security import scheduler
from app.modules.security.router import router as security_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    task = asyncio.create_task(scheduler.loop()) if get_settings().security_schedule else None
    yield
    if task:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(
    title="Blueberry Home",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(LocalNetworkOnly)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(assistant_router)
app.include_router(files_router)
app.include_router(learn_router)
app.include_router(poker_router)
app.include_router(security_router)


@app.get("/api/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/modules", tags=["meta"])
def modules(user: CurrentUser) -> list[ModuleInfo]:
    return [m for m in MODULES if user.is_admin or not m.admin_only]
