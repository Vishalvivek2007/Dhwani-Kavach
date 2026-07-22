import os
import sys

# faster-whisper (ctranslate2) and torch each bundle an Intel OpenMP runtime; on
# Windows both load the same libiomp5md.dll and the duplicate-init check aborts
# the process. They are the same runtime, so allowing the duplicate is safe here.
# Must be set before torch/ctranslate2 import. ponytail: env workaround; the clean
# fix is isolating STT in a subprocess — do that only if numerics ever look off.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

# Windows console defaults stdout/stderr to the system codepage (cp1252), which
# raises UnicodeEncodeError on non-Latin transcript text (Hindi/regional scam
# calls print through ws_analyze's debug log). Multilingual is a stated feature,
# so the console must not crash on it.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import asyncio

from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from app.routes.analyze import router as analyze_router
from app.routes.challenge import router as challenge_router
from app.routes.websocket import router as ws_router
from app.routes.rtc import router as rtc_router
from app.routes.cases import router as cases_router
from app.routes.campaigns import router as campaigns_router
from app.routes.governance import router as governance_router
from app import metrics

# Production hardening, opt-in via env so local demo stays open:
#   DHWANI_API_KEY   -> if set, /api/* requires header  x-api-key: <key>
#   DHWANI_ORIGINS   -> comma-separated allowed origins (default: * )
_API_KEY = os.environ.get("DHWANI_API_KEY", "")
_ORIGINS = [o.strip() for o in os.environ.get("DHWANI_ORIGINS", "*").split(",") if o.strip()]


async def require_key(x_api_key: str = Header(default="")):
    if _API_KEY and x_api_key != _API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")


app = FastAPI(title="Dhwani-Kavach API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

_guard = [Depends(require_key)] if _API_KEY else []
app.include_router(analyze_router, prefix="/api", dependencies=_guard)
app.include_router(challenge_router, prefix="/api", dependencies=_guard)
app.include_router(ws_router)
app.include_router(rtc_router)         # /ws/rtc/{room} — WebRTC signaling relay for the live-call demo
app.include_router(cases_router)      # defines full paths (/api/cases, /cases)
app.include_router(campaigns_router)   # /api/campaigns, /campaigns
app.include_router(governance_router)  # /governance, /api/governance, labelling


@app.on_event("startup")
async def _warm_models():
    # detector_v3 (ml/detector_v3.py) has no local checkpoint file -- it's
    # pulled from the HF Hub cache on first use (~1.2 GB). Prefetch it off
    # the event loop so the FIRST real request isn't the one paying for the
    # download; server still starts serving immediately either way.
    from ml import detector_v3
    asyncio.create_task(asyncio.to_thread(detector_v3.warm))


@app.get("/health")
async def health():
    return {"status": "ok", "service": "dhwani-kavach-backend"}


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics_endpoint():
    return metrics.render()
