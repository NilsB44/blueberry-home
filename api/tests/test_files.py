import pytest

from app.config import get_settings


@pytest.fixture
def files(admin_client, tmp_path, monkeypatch):
    monkeypatch.setenv("HUB_FILES_DIR", str(tmp_path))
    get_settings.cache_clear()
    return admin_client


def upload(c, name, data, space="shared", path=""):
    return c.put(f"/api/files/{space}/upload", params={"name": name, "path": path}, content=data)


def names(c, space="shared", path=""):
    body = c.get(f"/api/files/{space}/list", params={"path": path}).json()
    return [e["name"] for e in body["entries"]]


def test_requires_login(client):
    assert client.get("/api/files/shared/list").status_code == 401


def test_upload_list_download(files, tmp_path):
    resp = upload(files, "notes.txt", b"hello")
    assert resp.status_code == 201
    assert resp.json()["kind"] == "text"
    assert (tmp_path / "shared" / "notes.txt").read_bytes() == b"hello"
    assert names(files) == ["notes.txt"]

    raw = files.get("/api/files/shared/raw", params={"path": "notes.txt"})
    assert raw.content == b"hello"
    assert raw.headers["content-disposition"].startswith("inline")
    assert raw.headers["content-security-policy"] == "sandbox"


def test_ranges_for_video_seeking(files):
    upload(files, "clip.mp4", bytes(range(256)) * 4)
    resp = files.get(
        "/api/files/shared/raw", params={"path": "clip.mp4"}, headers={"Range": "bytes=10-19"}
    )
    assert resp.status_code == 206
    assert resp.content == bytes(range(10, 20))


def test_html_is_never_rendered_inline(files):
    upload(files, "page.html", b"<script>alert(1)</script>")
    raw = files.get("/api/files/shared/raw", params={"path": "page.html"})
    assert raw.headers["content-disposition"].startswith("attachment")


def test_upload_never_overwrites(files):
    upload(files, "a.jpg", b"1")
    upload(files, "a.jpg", b"2")
    upload(files, "a.jpg", b"3")
    assert names(files) == ["a (1).jpg", "a (2).jpg", "a.jpg"]


def test_folders_rename_move_delete(files):
    assert files.post("/api/files/shared/folder", json={"name": "Photos"}).status_code == 201
    assert files.post("/api/files/shared/folder", json={"name": "Photos"}).status_code == 409
    upload(files, "x.png", b"png", path="Photos")
    assert names(files, path="Photos") == ["x.png"]

    files.post("/api/files/shared/rename", json={"path": "Photos/x.png", "name": "y.png"})
    assert names(files, path="Photos") == ["y.png"]

    moved = files.post(
        "/api/files/shared/move", json={"path": "Photos/y.png", "to_space": "home", "to_dir": ""}
    )
    assert moved.json() == {"space": "home", "path": "y.png"}
    assert names(files, "home") == ["y.png"]
    assert names(files, path="Photos") == []

    assert files.delete("/api/files/shared", params={"path": "Photos"}).status_code == 204
    assert names(files) == []


def test_cannot_move_folder_into_itself(files):
    files.post("/api/files/shared/folder", json={"name": "A"})
    files.post("/api/files/shared/folder", json={"path": "A", "name": "B"})
    resp = files.post(
        "/api/files/shared/move", json={"path": "A", "to_space": "shared", "to_dir": "A/B"}
    )
    assert resp.status_code == 400


@pytest.mark.parametrize("path", ["..", "../..", "../home", "/etc", "a/../../x"])
def test_paths_cannot_escape(files, path):
    resp = files.get("/api/files/shared/list", params={"path": path})
    assert resp.status_code in (400, 404)
    assert files.delete("/api/files/shared", params={"path": path}).status_code in (400, 404)


@pytest.mark.parametrize("name", ["..", ".", "a/b", "a\\b", ""])
def test_bad_names(files, name):
    assert upload(files, name, b"x").status_code in (400, 422)


def test_root_cannot_be_deleted(files):
    assert files.delete("/api/files/shared", params={"path": ""}).status_code == 404


def test_symlink_out_of_space_is_refused(files, tmp_path):
    (tmp_path / "secret.txt").write_text("nope")
    (tmp_path / "shared").mkdir(exist_ok=True)
    (tmp_path / "shared" / "link").symlink_to(tmp_path)
    resp = files.get("/api/files/shared/raw", params={"path": "link/secret.txt"})
    assert resp.status_code == 400


def test_home_is_private(files):
    upload(files, "diary.txt", b"private", space="home")
    guest = {"username": "sam", "display_name": "Sam", "password": "guest password 1"}
    files.post("/api/users", json=guest)
    files.post("/api/auth/logout")
    files.post("/api/auth/login", json={"username": "sam", "password": guest["password"]})
    assert names(files, "home") == []
    upload(files, "shared.txt", b"hi")
    assert names(files) == ["shared.txt"]


def test_upload_size_limit(files, monkeypatch):
    monkeypatch.setenv("HUB_MAX_UPLOAD_MB", "1")
    get_settings.cache_clear()
    assert upload(files, "big.bin", b"x" * (2 << 20)).status_code == 413
    assert names(files) == []


def test_usage(files):
    body = files.get("/api/files/usage").json()
    assert body["free"] > 0 and body["max_upload"] == 8192 << 20


def test_upload_with_a_garbled_length_is_not_a_server_error(client):
    client.post("/api/auth/device")
    resp = client.put(
        "/api/files/home/upload?name=a.txt", content=b"hi", headers={"content-length": "abc"}
    )
    assert resp.status_code < 500
