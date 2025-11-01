"""Интеграция логирования видео в Airtable"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from integrations.airtable.airtable_logger import session_logger

async def log_video_start(user_id, session_id, model, aspect_ratio, duration, prompt):
    """Логирование начала генерации видео"""
    return await session_logger.log_session_start(
        user_id=user_id,
        session_id=session_id,
        video_type="text",
        model=model,
        aspect_ratio=aspect_ratio,
        duration=duration,
        prompt=prompt
    )

async def log_video_complete(session_id, status, output_url=None, processing_time=None, error_message=None):
    """Логирование завершения генерации видео"""
    return await session_logger.log_session_complete(
        session_id=session_id,
        video_type="text",
        status=status,
        output_url=output_url,
        processing_time=processing_time,
        error_message=error_message
    )
