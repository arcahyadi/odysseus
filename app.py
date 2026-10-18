# app.py — slim orchestrator
import asyncio
import mimetypes
import os
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


def register_static_mime_types() -> None:
    mimetypes.add_type("text/javascript", ".js")
    mimetypes.add_type("application/javascript", ".mjs")


register_static_mime_types()

if os.name == "nt":
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from dotenv import load_dotenv

load_dotenv(encoding="utf-8-sig")

import logging
import logging.handlers
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware

from core.auth import AuthManager
from core.constants import (
    BASE_DIR,
    DATA_DIR,
    STATIC_DIR,
)
from core.exceptions import (
    InvalidFileUploadError,
    LLMServiceError,
    SessionNotFoundError,
    WebSearchError,
)
from core.middleware import SecurityHeadersMiddleware
from src.generated_images import GENERATED_IMAGE_HEADERS, resolve_generated_image_path

# ── Logging ─────────────────────────────────────────────────────────
_root_logger = logging.getLogger()
_root_logger.setLevel(logging.INFO)
_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
for _h in list(_root_logger.handlers):
    _root_logger.removeHandler(_h)
_console_h = logging.StreamHandler()
_console_h.setFormatter(_formatter)
_root_logger.addHandler(_console_h)
try:
    _log_dir = os.path.join(DATA_DIR, "logs")
    os.makedirs(_log_dir, exist_ok=True)
    _log_file = os.path.join(_log_dir, "app.log")
    _file_h = logging.handlers.RotatingFileHandler(_log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    _file_h.setFormatter(_formatter)
    _root_logger.addHandler(_file_h)
except Exception as e:
    _root_logger.warning(f"Failed to initialize file logging handler (falling back to console-only): {e}")

logger = logging.getLogger(__name__)

# ── FastAPI app ─────────────────────────────────────────────────────
app = FastAPI(
    title="AI Chat Application",
    description="Comprehensive AI chat with memory, research, and multi-modal capabilities",
    version="1.0.0",
)

# ── CORS ────────────────────────────────────────────────────────────
CORS_ALLOW_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"]
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost,http://127.0.0.1").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=CORS_ALLOW_METHODS,
    allow_headers=[
        "Accept",
        "Authorization",
        "Content-Type",
        "X-API-Key",
        "X-Auth-Token",
        "X-Odysseus-Internal-Token",
        "X-Odysseus-Owner",
        "X-Requested-With",
        "X-TZ-Offset",
    ],
)

# ── GZip ────────────────────────────────────────────────────────────
app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=6)

# ── Security headers ────────────────────────────────────────────────
app.add_middleware(SecurityHeadersMiddleware)

# ── Request timeout (fallback for hung handlers) ────────────────────
REQUEST_HARD_TIMEOUT = float(os.getenv("REQUEST_HARD_TIMEOUT", "45"))
_TIMEOUT_EXEMPT_PREFIXES = (
    "/api/chat",
    "/api/shell/stream",
    "/api/research",
    "/api/model/download",
    "/api/model/probe",
    "/api/model-endpoints",
    "/api/cookbook/setup",
    "/api/upload",
    "/api/image",
    "/api/memory/audit",
)


class _RequestTimeoutMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path or ""
        if any(path.startswith(p) for p in _TIMEOUT_EXEMPT_PREFIXES):
            return await call_next(request)
        try:
            return await asyncio.wait_for(call_next(request), timeout=REQUEST_HARD_TIMEOUT)
        except TimeoutError:
            return JSONResponse(
                {"detail": f"Request exceeded {REQUEST_HARD_TIMEOUT:.0f}s timeout"},
                status_code=504,
            )


app.add_middleware(_RequestTimeoutMiddleware)

# ── Auth middleware ─────────────────────────────────────────────────
auth_manager = AuthManager()
app.state.auth_manager = auth_manager

import re as _re

# Paths the auth middleware lets through unauthenticated. The dynamic task
# webhook trigger (POST /api/tasks/{task_id}/webhook/{token}) is public — the
# path-embedded webhook_token is the credential and the route handler in
# routes/task_routes.py validates it against the row (issue #621).
AUTH_EXEMPT_PATTERNS = [
    _re.compile(r"^/api/tasks/[^/]+/webhook/[^/]+/?$"),
]

from core.auth_middleware import setup_auth

setup_auth(app, auth_manager, exempt_patterns=AUTH_EXEMPT_PATTERNS)

# ── Static files ────────────────────────────────────────────────────
os.makedirs(STATIC_DIR, exist_ok=True)


class _RevalidatingStatic(StaticFiles):
    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        if path.endswith((".js", ".css", ".html")):
            resp.headers["Cache-Control"] = "no-cache"
        return resp


app.mount("/static", _RevalidatingStatic(directory=STATIC_DIR), name="static")


# ── Generated images endpoint ───────────────────────────────────────
@app.get("/api/generated-image/{filename}")
async def serve_generated_image(filename: str, request: Request):
    img_path = resolve_generated_image_path(filename)
    try:
        from core.database import GalleryImage as _GI
        from core.database import SessionLocal as _SL
        from src.auth_helpers import get_current_user

        _user = get_current_user(request)
        if _user:
            _db = _SL()
            try:
                _row = _db.query(_GI).filter(_GI.filename == filename).first()
                if _row is not None and _row.owner and _row.owner != _user:
                    raise HTTPException(status_code=404, detail="Image not found")
            finally:
                _db.close()
    except HTTPException:
        raise
    except Exception as _e:
        logger.warning("Image ownership verification failed for %r", filename, exc_info=_e)
    ext = filename.rsplit(".", 1)[-1].lower()
    mime = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
        "gif": "image/gif",
        "mp4": "video/mp4",
        "mov": "video/quicktime",
        "webm": "video/webm",
        "mkv": "video/x-matroska",
        "m4v": "video/mp4",
    }.get(ext, "application/octet-stream")
    return FileResponse(str(img_path), media_type=mime, headers=GENERATED_IMAGE_HEADERS)


# ── YouTube init ────────────────────────────────────────────────────
from services.youtube import init_youtube

init_youtube()

# ── RAG ─────────────────────────────────────────────────────────────
from src.rag_singleton import get_rag_manager

rag_manager = get_rag_manager()
rag_available = rag_manager is not None
app.state.rag_manager = rag_manager
app.state.rag_available = rag_available
if rag_available:
    logger.info("Vector document RAG initialized")
else:
    logger.info(
        "Vector document RAG not available at startup (ChromaDB may not be reachable yet — routes will retry lazily)"
    )

# ── Component initialization ────────────────────────────────────────
from src.app_initializer import initialize_managers
from src.config import config

components = initialize_managers(BASE_DIR, rag_manager)

session_manager = components["session_manager"]
app.state.session_manager = session_manager

from src.assistant_log import set_session_manager as _set_asst_sm

_set_asst_sm(session_manager)

from core.models import set_session_manager_instance

set_session_manager_instance(session_manager)

memory_manager = components["memory_manager"]
memory_vector = components.get("memory_vector")
app.state.memory_manager = memory_manager
app.state.memory_vector = memory_vector

upload_handler = components["upload_handler"]
app.state.upload_handler = upload_handler

personal_docs_mgr = components["personal_docs_manager"]
app.state.personal_docs_manager = personal_docs_mgr

api_key_manager = components["api_key_manager"]
app.state.api_key_manager = api_key_manager

preset_manager = components["preset_manager"]
app.state.preset_manager = preset_manager

chat_processor = components["chat_processor"]
app.state.chat_processor = chat_processor

research_handler = components["research_handler"]
app.state.research_handler = research_handler

chat_handler = components["chat_handler"]
app.state.chat_handler = chat_handler

model_discovery = components["model_discovery"]
app.state.model_discovery = model_discovery

skills_manager = components["skills_manager"]
app.state.skills_manager = skills_manager

# TTS
from services.tts import get_tts_service

tts_service = get_tts_service()
app.state.tts_service = tts_service
logger.info("TTS service initialized (provider managed via admin settings)")

# STT
from services.stt import get_stt_service

stt_service = get_stt_service()
app.state.stt_service = stt_service
logger.info("STT service initialized (provider managed via settings)")


# ── Exception handlers ──────────────────────────────────────────────
@app.exception_handler(SessionNotFoundError)
async def session_not_found_handler(request: Request, exc: SessionNotFoundError):
    return JSONResponse(status_code=404, content={"error": "SESSION_NOT_FOUND", "message": str(exc)})


@app.exception_handler(InvalidFileUploadError)
async def invalid_file_upload_handler(request: Request, exc: InvalidFileUploadError):
    return JSONResponse(status_code=400, content={"error": "INVALID_FILE_UPLOAD", "message": str(exc)})


@app.exception_handler(LLMServiceError)
async def llm_service_error_handler(request: Request, exc: LLMServiceError):
    return JSONResponse(status_code=502, content={"error": "LLM_SERVICE_ERROR", "message": str(exc)})


@app.exception_handler(WebSearchError)
async def web_search_error_handler(request: Request, exc: WebSearchError):
    return JSONResponse(status_code=502, content={"error": "WEB_SEARCH_ERROR", "message": str(exc)})


# ── Webhook manager ─────────────────────────────────────────────────
from src.webhook_manager import WebhookManager

webhook_manager = WebhookManager(api_key_manager=api_key_manager)
app.state.webhook_manager = webhook_manager

# ── Task scheduler ──────────────────────────────────────────────────
from src.task_scheduler import TaskScheduler

task_scheduler = TaskScheduler(session_manager)
app.state.task_scheduler = task_scheduler

from src.event_bus import set_task_scheduler

set_task_scheduler(task_scheduler)

# ── MCP manager ─────────────────────────────────────────────────────
from src.agent_tools import set_mcp_manager
from src.mcp_manager import McpManager

mcp_manager = McpManager()
app.state.mcp_manager = mcp_manager
set_mcp_manager(mcp_manager)
logger.info("MCP routes initialized")

# ── AI interaction tools ────────────────────────────────────────────
from src.ai_interaction import set_memory_manager as set_ai_memory_manager
from src.ai_interaction import set_rag_manager as set_ai_rag_manager
from src.ai_interaction import set_session_manager as set_ai_session_manager

set_ai_session_manager(session_manager)
set_ai_memory_manager(memory_manager, memory_vector)
set_ai_rag_manager(rag_manager, personal_docs_mgr)
logger.info("AI interaction tools initialized (session, memory, RAG, UI control)")

# ── Config accessor for route_loader ────────────────────────────────
app.state.config = config

# ── Register all routes ─────────────────────────────────────────────
from core.route_loader import register_all_routes

register_all_routes(app)


# ── Lifespan ────────────────────────────────────────────────────────
@asynccontextmanager
async def _lifespan(app):
    from core.startup import run_shutdown as _run_shutdown
    from core.startup import run_startup as _run_startup

    await _run_startup(app)
    yield
    await _run_shutdown(app)


app.router.lifespan_context = _lifespan

# ── Main ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    bind_host = os.getenv("APP_BIND", "127.0.0.1")
    bind_port = int(os.getenv("APP_PORT", "7000"))

    uvicorn.run(app, host=bind_host, port=bind_port, log_level="info")
