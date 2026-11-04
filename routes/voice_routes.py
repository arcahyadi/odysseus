"""
routes/voice_routes.py
======================
Thin API surface for the voice-first session feature.

Endpoints
---------
GET  /api/voice/status   — returns combined STT + TTS availability in one call
                           so the frontend can decide whether to show the voice
                           session button without two separate round-trips.

The heavy lifting (transcription, synthesis) stays in the existing
/api/stt/transcribe and /api/tts/synthesize endpoints, which the frontend
already knows how to call.  This route only adds the single "is voice usable?"
probe needed at session startup.
"""

import logging
from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/voice/status")
async def voice_status(request: Request):
    """
    Return a combined voice-capability object so the client can enable the
    voice session button in a single fetch.

    Response shape:
    {
      "voice_available": bool,   // true if BOTH stt and tts are ready
      "stt": {
        "available": bool,
        "provider":  str,        // "disabled" | "browser" | "local" | "endpoint:..."
        "model":     str,
      },
      "tts": {
        "available": bool,
        "provider":  str,
        "voice":     str,
        "speed":     float,
      }
    }
    """
    try:
        from services.stt import get_stt_service
        stt = get_stt_service()
        stt_stats = stt.get_stats()
    except Exception as exc:
        logger.debug("voice_status: STT stats error: %s", exc)
        stt_stats = {"available": False, "provider": "disabled", "model": ""}

    try:
        from services.tts import get_tts_service
        tts = get_tts_service()
        tts_stats = tts.get_stats()
    except Exception as exc:
        logger.debug("voice_status: TTS stats error: %s", exc)
        tts_stats = {"available": False, "provider": "disabled", "voice": "", "speed": 1.0}

    stt_ok = bool(stt_stats.get("available"))
    tts_ok = bool(tts_stats.get("available"))

    return {
        "voice_available": stt_ok and tts_ok,
        "stt": {
            "available": stt_ok,
            "provider":  stt_stats.get("provider", "disabled"),
            "model":     stt_stats.get("model", ""),
        },
        "tts": {
            "available": tts_ok,
            "provider":  tts_stats.get("provider", "disabled"),
            "voice":     tts_stats.get("voice", ""),
            "speed":     tts_stats.get("speed", 1.0),
        },
    }
