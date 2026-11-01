from sqlalchemy import inspect, text
from sqlmodel import create_engine

from app import db as db_module


def test_new_nullable_columns_are_added_to_existing_tables(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/old.db")
    with engine.begin() as conn:
        # poker_game as it would be before the settled_at column existed.
        conn.execute(text("CREATE TABLE poker_game (id INTEGER PRIMARY KEY, name VARCHAR)"))
    monkeypatch.setattr(db_module, "_engine", engine)
    db_module.init_db()
    columns = {c["name"] for c in inspect(engine).get_columns("poker_game")}
    assert "settled_at" in columns
