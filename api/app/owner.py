"""Show or move who owns the hub. Run on the Pi, so only someone with access to the Pi itself
can change it (for example after the owner's phone was replaced or its browser data cleared):

    docker compose exec api python -m app.owner              # list people
    docker compose exec api python -m app.owner <username>   # make them the owner
"""

import sys

from sqlmodel import Session, select

from app.auth.models import User
from app.db import get_engine, init_db
from app.modules.security.events import log_event


def main(argv: list[str]) -> int:
    init_db()
    with Session(get_engine()) as session:
        users = list(session.exec(select(User).order_by(User.id)))
        if not argv:
            for u in users:
                tags = [t for t, on in (("owner", u.is_owner), ("admin", u.is_admin)) if on]
                print(f"{u.username:32} {u.display_name:24} {', '.join(tags)}")
            return 0
        new = next((u for u in users if u.username == argv[0].lower()), None)
        if new is None:
            print(f"No one is called @{argv[0]}. Run without arguments to list people.")
            return 1
        for u in users:
            u.is_owner = u.id == new.id or None
            session.add(u)
        new.is_admin = True
        session.commit()
        log_event(session, "owner", f"@{new.username} became the owner (from the Pi)")
        print(f"@{new.username} ({new.display_name}) now owns the hub.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
