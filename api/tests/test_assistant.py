import json

import httpx
import pytest

from app.main import app
from app.modules.assistant.router import ollama_client


def use_fake_ollama(handler):
    async def override():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://ollama"
        ) as c:
            yield c

    app.dependency_overrides[ollama_client] = override


@pytest.fixture
def chat_body():
    return {"messages": [{"role": "user", "content": "Bonjour?"}]}


def test_status_online(admin_client):
    use_fake_ollama(lambda req: httpx.Response(200, json={"models": [{"name": "qwen3:4b"}]}))
    body = admin_client.get("/api/assistant/status").json()
    assert body["online"] is True
    assert body["models"] == ["qwen3:4b"]


def test_status_offline(admin_client):
    def down(req):
        raise httpx.ConnectError("refused")

    use_fake_ollama(down)
    assert admin_client.get("/api/assistant/status").json()["online"] is False


def test_chat_streams_text_and_sends_system_prompt(admin_client, chat_body):
    seen = {}

    def handler(req):
        seen["payload"] = json.loads(req.content)
        lines = [
            {"message": {"content": "Bon"}, "done": False},
            {"message": {"content": "jour !"}, "done": False},
            {"message": {"content": ""}, "done": True},
        ]
        return httpx.Response(200, text="\n".join(json.dumps(x) for x in lines))

    use_fake_ollama(handler)
    resp = admin_client.post("/api/assistant/chat", json=chat_body)
    assert resp.status_code == 200
    assert resp.text == "Bonjour !"
    assert seen["payload"]["messages"][0]["role"] == "system"
    assert seen["payload"]["messages"][1] == {"role": "user", "content": "Bonjour?"}
    assert seen["payload"]["model"] == "qwen3:4b"


def test_chat_offline_returns_503(admin_client, chat_body):
    def down(req):
        raise httpx.ConnectError("refused")

    use_fake_ollama(down)
    assert admin_client.post("/api/assistant/chat", json=chat_body).status_code == 503


def test_chat_model_error_returns_502(admin_client, chat_body):
    use_fake_ollama(lambda req: httpx.Response(404, json={"error": "model not found"}))
    resp = admin_client.post("/api/assistant/chat", json=chat_body)
    assert resp.status_code == 502
    assert "model not found" in resp.json()["detail"]


def test_chat_requires_login(client, chat_body):
    assert client.post("/api/assistant/chat", json=chat_body).status_code == 401
