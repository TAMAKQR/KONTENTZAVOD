"""
Логирование в простые Airtable таблицы (с полями Name и Notes)
"""
import os
import logging
from datetime import datetime
from typing import Optional
import aiohttp
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")

SIMPLE_TABLE_IDS = {
    "animation": os.getenv("AIRTABLE_ANIMATION_TABLE_ID"),
    "photo": os.getenv("AIRTABLE_PHOTO_TABLE_ID"),
    "photo_ai": os.getenv("AIRTABLE_AI_PHOTO_TABLE_ID"),
}


def get_table_url(table_type: str) -> Optional[str]:
    """Получить URL таблицы"""
    table_id = SIMPLE_TABLE_IDS.get(table_type)
    if not table_id:
        return None
    return f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{table_id}"


class SimpleAirtableLogger:
    """Логирование в простые таблицы"""
    
    def __init__(self):
        self.enabled = bool(AIRTABLE_API_KEY and AIRTABLE_BASE_ID)
        if not self.enabled:
            logger.warning("⚠️ Simple Airtable logging disabled: missing API key or Base ID")
    
    async def log_record(
        self,
        table_type: str,
        name: str,
        notes: str = ""
    ) -> bool:
        """Логирование записи в простую таблицу"""
        if not self.enabled:
            return False
        
        table_url = get_table_url(table_type)
        if not table_url:
            logger.warning(f"⚠️ Table type '{table_type}' not configured")
            return False
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {AIRTABLE_API_KEY}",
                    "Content-Type": "application/json"
                }
                
                data = {
                    "records": [
                        {
                            "fields": {
                                "Name": name[:200],
                                "Notes": notes[:1000] if notes else ""
                            }
                        }
                    ]
                }
                
                async with session.post(table_url, json=data, headers=headers) as resp:
                    response_text = await resp.text()
                    if resp.status in [200, 201]:
                        logger.info(f"✅ Record logged to {table_type}")
                        return True
                    else:
                        logger.warning(f"⚠️ Airtable logging failed: {resp.status}")
                        logger.debug(f"Response: {response_text}")
                        return False
        except Exception as e:
            logger.error(f"❌ Error logging to Airtable: {e}")
            return False


simple_logger = SimpleAirtableLogger()
