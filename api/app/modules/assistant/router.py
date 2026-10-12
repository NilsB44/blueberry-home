"""Chat with a local model served by Ollama.

The API proxies to Ollama rather than exposing it, so the model is only reachable by logged-in
users and Ollama's own port never leaves the Docker network.
"""

import json
from collections.abc import AsyncIterator
from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.auth.deps import CurrentUser
from app.config import get_settings

router = APIRouter(prefix="/api/assistant", tags=["assistant"])

SYSTEM_PROMPT = (
    "You are the assistant on a home server called Blueberry Home. Be concise and practical. "
    "The user is a software engineer learning French, interested in poker, finance, plants, "
    "reading and gaming."
)


async def ollama_client() -> AsyncIterator[httpx.AsyncClient]:
    # Generous read timeout: a 4B model on a Pi can take a while to produce the first token.
    timeout = httpx.Timeout(10.0, read=300.0)
    async with httpx.AsyncClient(base_url=get_settings().ollama_url, timeout=timeout) as client:
        yield client


Ollama = Annotated[httpx.AsyncClient, Depends(ollama_client)]


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=8000)


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1, max_length=50)
    model: str | None = None


class AssistantStatus(BaseModel):
    online: bool
    default_model: str
    models: list[str]


@router.get("/status")
async def assistant_status(_: CurrentUser, client: Ollama) -> AssistantStatus:
    default = get_settings().assistant_model
    try:
        resp = await client.get("/api/tags")
        resp.raise_for_status()
    except httpx.HTTPError:
        return AssistantStatus(online=False, default_model=default, models=[])
    models = [m["name"] for m in resp.json().get("models", [])]
    return AssistantStatus(online=True, default_model=default, models=models)


@router.post("/chat")
async def chat(body: ChatRequest, _: CurrentUser, client: Ollama) -> StreamingResponse:
    """Stream the reply as plain text chunks."""
    payload = {
        "model": body.model or get_settings().assistant_model,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}]
        + [m.model_dump() for m in body.messages],
        "stream": True,
    }
    request = client.build_request("POST", "/api/chat", json=payload)
    try:
        resp = await client.send(request, stream=True)
    except httpx.HTTPError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Model server offline") from exc
    if resp.status_code != 200:
        detail = (await resp.aread()).decode(errors="replace")[:500]
        await resp.aclose()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Model server error: {detail}")

    async def tokens() -> AsyncIterator[str]:
        try:
            async for line in resp.aiter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                if text := chunk.get("message", {}).get("content"):
                    yield text
                if chunk.get("done"):
                    break
        finally:
            await resp.aclose()

    return StreamingResponse(tokens(), media_type="text/plain; charset=utf-8")
