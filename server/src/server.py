"""FastAPI service for the inline LLM REST tools recipe."""

import logging
import os
import random
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, Literal, Optional

from dotenv import load_dotenv

_base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_base_dir, ".env.local"), override=True)
load_dotenv(os.path.join(_base_dir, ".env"), override=True)

from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agora_agent.agentkit.token import generate_convo_ai_token
from agent import Agent
from http_tools import router as http_tools_router

logger = logging.getLogger("uvicorn.error")


def _log_route_error(route: str, exc: Exception, **context) -> None:
    safe_context = {key: value for key, value in context.items() if value is not None}
    logger.exception(
        "Request failed route=%s context=%s error_type=%s error=%s",
        route,
        safe_context,
        type(exc).__name__,
        exc,
    )


def _to_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, RuntimeError):
        return HTTPException(status_code=500, detail=str(exc))
    return HTTPException(status_code=500, detail=f"Internal error: {exc}")


try:
    agent = Agent()
except ValueError as exc:
    logger.exception("Failed to initialize Agent. Check environment variables: %s", exc)
    agent = None


@asynccontextmanager
async def _lifespan(_app):
    try:
        yield
    finally:
        if agent is not None:
            await agent.close()

app = FastAPI(
    title="Agora Inline LLM REST Tools Recipe Service",
    version="1.0.0",
    description="Agora Conversational AI with inline synchronous REST tools.",
    lifespan=_lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(http_tools_router)
router = APIRouter()


class StartAgentRequest(BaseModel):
    channelName: str
    rtcUid: int
    userUid: int
    parameters: Optional[Dict[str, Any]] = None
    agentMode: Literal["pipeline", "realtime"] = "pipeline"


class StopAgentRequest(BaseModel):
    agentId: str


def _generate_channel_name() -> str:
    return f"inline-rest-tools-{int(time.time())}-{random.randint(1000, 9999)}"


@router.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok", "service": "inline-rest-tools"}


@router.get("/get_config")
async def get_config(
    channel: Optional[str] = Query(default=None),
    uid: Optional[int] = Query(default=None),
):
    if agent is None:
        raise HTTPException(status_code=500, detail="Service not properly configured")
    try:
        user_uid = random.randint(1000, 9999999) if uid is None or uid <= 0 else uid
        agent_uid = str(random.randint(10000000, 99999999))
        channel_name = channel or _generate_channel_name()
        token = generate_convo_ai_token(
            app_id=os.getenv("AGORA_APP_ID"),
            app_certificate=os.getenv("AGORA_APP_CERTIFICATE"),
            channel_name=channel_name,
            uid=user_uid,
            token_expire=3600,
        )
        return {
            "code": 0,
            "data": {
                "app_id": os.getenv("AGORA_APP_ID"),
                "token": token,
                "uid": str(user_uid),
                "channel_name": channel_name,
                "agent_uid": agent_uid,
            },
            "msg": "success",
        }
    except Exception as exc:
        _log_route_error("/get_config", exc, channel=channel, uid=uid)
        raise _to_http_error(exc)


@router.post("/startAgent")
async def start_agent(request: StartAgentRequest):
    if agent is None:
        raise HTTPException(status_code=500, detail="Service not properly configured")
    try:
        codec = request.parameters.get("output_audio_codec") if request.parameters else None
        result = await agent.start(
            channel_name=request.channelName,
            agent_uid=request.rtcUid,
            user_uid=request.userUid,
            output_audio_codec=codec,
            agent_mode=request.agentMode,
        )
        return {"code": 0, "msg": "success", "data": result}
    except Exception as exc:
        _log_route_error(
            "/startAgent",
            exc,
            channelName=request.channelName,
            rtcUid=request.rtcUid,
            userUid=request.userUid,
        )
        raise _to_http_error(exc)


@router.post("/stopAgent")
async def stop_agent(request: StopAgentRequest):
    if agent is None:
        raise HTTPException(status_code=500, detail="Service not properly configured")
    try:
        await agent.stop(request.agentId)
        return {"code": 0, "msg": "success"}
    except Exception as exc:
        _log_route_error("/stopAgent", exc, agentId=request.agentId)
        raise _to_http_error(exc)


app.include_router(router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
