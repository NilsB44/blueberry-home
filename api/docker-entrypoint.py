"""Container entrypoint: make the mounted data folders writable, then drop root.

Docker creates missing bind-mount folders (./data/api, ./data/files) owned by root, which the
unprivileged app user couldn't write to. Fixing ownership of the top folder here, then
switching to the hub user, makes a fresh `docker compose up` just work.
"""

import os
import pwd
import sys

DATA_DIRS = ("/srv/data", "/srv/files")

if os.getuid() == 0:
    hub = pwd.getpwnam("hub")
    for d in DATA_DIRS:
        os.makedirs(d, exist_ok=True)
        os.chown(d, hub.pw_uid, hub.pw_gid)
    os.setgroups([])
    os.setgid(hub.pw_gid)
    os.setuid(hub.pw_uid)

os.execvp(sys.argv[1], sys.argv[1:])
