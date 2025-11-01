"""Интеграция обновления параметров видео в Airtable"""
import sys
import logging
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from integrations.airtable.airtable_logger import session_logger

logger = logging.getLogger(__name__)

async def update_video_parameters(session_id, model=None, aspect_ratio=None, duration=None, prompt=None):
    """Обновить параметры видео сессии"""
    logger.debug(f"Updating video parameters: session_id={session_id}, model={model}, aspect={aspect_ratio}, duration={duration}")
    return await session_logger.update_session_parameters(
        session_id=session_id,
        video_type="text",
        model=model,
        aspect_ratio=aspect_ratio,
        duration=duration,
        prompt=prompt
    )
