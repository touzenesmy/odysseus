# routes/stt_routes.py
"""STT API routes — multi-provider (local Whisper, API endpoint, browser)."""

import asyncio
import logging

from fastapi import APIRouter, HTTPException, UploadFile, File

from src.upload_limits import read_upload_limited, STT_MAX_AUDIO_BYTES

logger = logging.getLogger(__name__)


def setup_stt_routes(stt_service):
    """Setup STT routes with the provided STT service"""
    router = APIRouter(prefix="/api/stt", tags=["stt"])

    @router.get("/stats")
    async def get_stt_stats():
        """Get STT service statistics (off the loop — for 'local' this can
        be the first Whisper model load, a multi-second block)."""
        try:
            return await asyncio.to_thread(stt_service.get_stats)
        except Exception as e:
            logger.error(f"Failed to get STT stats: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/transcribe")
    async def transcribe_audio(file: UploadFile = File(...)):
        """Transcribe uploaded audio file to text"""
        try:
            # Off the event loop: the check warms the Whisper model (first
            # call) and the transcription is a ~1–2 s CPU burst.
            if not await asyncio.to_thread(lambda: stt_service.available):
                raise HTTPException(
                    status_code=503,
                    detail={"message": "STT service not available or set to browser mode"}
                )

            audio_bytes = await read_upload_limited(file, STT_MAX_AUDIO_BYTES, "Audio file")
            if not audio_bytes:
                raise HTTPException(status_code=400, detail={"message": "Empty audio file"})

            text = await asyncio.to_thread(stt_service.transcribe, audio_bytes)
            if text is None:
                raise HTTPException(
                    status_code=500,
                    detail={"message": "Transcription failed"}
                )

            return {"text": text}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Transcription error: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail={"message": f"Transcription failed: {str(e)}"}
            )

    return router
