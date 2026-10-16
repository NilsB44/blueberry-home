from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import event, inspect, text
from sqlmodel import Session, SQLModel, create_engine, select

from app.config import get_settings

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        url = get_settings().database_url
        if url.startswith("sqlite:///") and ":memory:" not in url:
            Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(url, connect_args={"check_same_thread": False})
        if url.startswith("sqlite"):
            event.listen(_engine, "connect", _sqlite_pragmas)
    return _engine


def _sqlite_pragmas(dbapi_conn, _record) -> None:
    # WAL lets readers and a writer work at the same time, which matters on an SD/NVMe-backed Pi.
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.close()


def init_db() -> None:
    # Import models so they register on SQLModel.metadata before create_all.
    from app.auth import models  # noqa: F401
    from app.modules.learn import models as learn_models  # noqa: F401
    from app.modules.network import models as network_models  # noqa: F401
    from app.modules.poker import models as poker_models  # noqa: F401
    from app.modules.security import models as security_models  # noqa: F401
    from app.modules.tetris import models as tetris_models  # noqa: F401

    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    _add_new_columns(engine)
    _ensure_owner(engine)


def _add_new_columns(engine) -> None:
    """create_all() makes missing tables but never alters existing ones. Until the schema
    needs real migrations, add new nullable columns in place so an existing hub.db keeps
    working after an upgrade."""
    existing = inspect(engine)
    with engine.begin() as conn:
        for table in SQLModel.metadata.sorted_tables:
            if not existing.has_table(table.name):
                continue
            have = {c["name"] for c in existing.get_columns(table.name)}
            for col in table.columns:
                if col.name not in have and col.nullable:
                    ddl = col.type.compile(dialect=engine.dialect)
                    conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {ddl}'))


def _ensure_owner(engine) -> None:
    """Hubs set up before there was an owner: the first admin becomes it."""
    from app.auth.models import User

    with Session(engine) as session:
        if session.exec(select(User).where(User.is_owner == True)).first():  # noqa: E712
            return
        first_admin = session.exec(select(User).where(User.is_admin).order_by(User.id)).first()
        if first_admin:
            first_admin.is_owner = True
            session.add(first_admin)
            session.commit()


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
