"""Интеграция логирования редактирования фото в Airtable"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from integrations.airtable.simple_airtable_logger import simple_logger

async def log_photo_start(user_id, session_id, prompt):
    """Логирование начала редактирования фото"""
    name = f"Photo Edit: {session_id}"
    notes = f"User: {user_id}\nPrompt: {prompt[:500]}"
    return await simple_logger.log_record("photo", name, notes)

async def log_photo_complete(session_id, status, output_url=None, processing_time=None, error_message=None):
    """Логирование завершения редактирования фото"""
    name = f"Photo Edit Complete: {session_id}"
    notes = f"Status: {status}\nOutput: {output_url or 'N/A'}\nTime: {processing_time or 0}s"
    if error_message:
        notes += f"\nError: {error_message}"
    return await simple_logger.log_record("photo", name, notes)
