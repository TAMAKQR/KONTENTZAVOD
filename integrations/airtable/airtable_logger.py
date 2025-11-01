"""
Логирование сессий в Airtable
"""
import os
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from urllib.parse import quote
import aiohttp
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_ID = os.getenv("AIRTABLE_TABLE_ID")

AIRTABLE_TABLE_IDS = {
    "text": os.getenv("AIRTABLE_VIDEO_TABLE_ID", os.getenv("AIRTABLE_TABLE_ID")),
    "text_photo": os.getenv("AIRTABLE_VIDEO_TABLE_ID", os.getenv("AIRTABLE_TABLE_ID")),
    "text_photo_ai": os.getenv("AIRTABLE_AI_PHOTO_TABLE_ID"),
    "animation": os.getenv("AIRTABLE_ANIMATION_TABLE_ID"),
    "photo_edit": os.getenv("AIRTABLE_PHOTO_TABLE_ID"),
    "photo": os.getenv("AIRTABLE_PHOTO_TABLE_ID"),
}

def get_table_url(video_type: str) -> str:
    """Получить URL таблицы для типа видео"""
    table_id = AIRTABLE_TABLE_IDS.get(video_type, AIRTABLE_TABLE_ID)
    return f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{table_id}"

FIELD_NAMES = {
    "Session ID": "Session ID",
    "User ID": "User ID",
    "Video Type": "Video Type",
    "Model": "Model",
    "Aspect Ratio": "Aspect Ratio",
    "Duration": "Duration",
    "Prompt": "Prompt",
    "PromptAI": "PromptAI",
    "Status": "Status",
    "Output": "Output ",
    "Processing Time": "Processing Time",
    "Error Message": "Error Message",
    "Created At": "Created At",
    "Completed At": "Completed At",
    "Scene Videos": "Scene Videos",
    "Scene Photos": "Scene Photos"
}


class AirtableSessionLogger:
    """Логирование сессий в Airtable"""
    
    def __init__(self):
        self.enabled = bool(AIRTABLE_API_KEY and AIRTABLE_BASE_ID and AIRTABLE_TABLE_ID)
        if not self.enabled:
            logger.warning("⚠️ Airtable logging disabled: missing API key, Base ID, or Table ID")
    
    async def log_session_start(
        self,
        user_id: int,
        session_id: str,
        video_type: str,
        model: str = "",
        aspect_ratio: str = "",
        duration: int = 0,
        prompt: str = "",
        prompt_ai: str = "",
    ) -> bool:
        """Логирование начала сессии"""
        if not self.enabled:
            return False
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {AIRTABLE_API_KEY}",
                    "Content-Type": "application/json"
                }
                
                table_url = get_table_url(video_type)
                
                fields = {
                    FIELD_NAMES["Session ID"]: session_id,
                    FIELD_NAMES["User ID"]: user_id,
                    FIELD_NAMES["Video Type"]: video_type,
                    FIELD_NAMES["Status"]: "Started",
                    FIELD_NAMES["Created At"]: datetime.now().strftime("%Y-%m-%d"),
                }
                
                if model:
                    fields[FIELD_NAMES["Model"]] = model
                if aspect_ratio:
                    fields[FIELD_NAMES["Aspect Ratio"]] = aspect_ratio
                if duration:
                    fields[FIELD_NAMES["Duration"]] = duration
                if prompt:
                    fields[FIELD_NAMES["Prompt"]] = prompt[:500]
                if prompt_ai:
                    fields[FIELD_NAMES["PromptAI"]] = prompt_ai[:2000]
                
                data = {
                    "records": [
                        {
                            "fields": fields
                        }
                    ]
                }
                
                async with session.post(table_url, json=data, headers=headers) as resp:
                    response_text = await resp.text()
                    if resp.status in [200, 201]:
                        logger.info(f"✅ Session {session_id} logged to Airtable")
                        return True
                    else:
                        logger.warning(f"⚠️ Airtable logging failed: {resp.status}")
                        logger.warning(f"   Response: {response_text[:200]}")
                        return False
        except Exception as e:
            logger.error(f"❌ Error logging to Airtable: {e}")
            return False
    
    async def update_session_parameters(
        self,
        session_id: str,
        video_type: str,
        model: Optional[str] = None,
        aspect_ratio: Optional[str] = None,
        duration: Optional[int] = None,
        prompt: Optional[str] = None,
        prompt_ai: Optional[str] = None
    ) -> bool:
        """Обновить параметры сессии"""
        if not self.enabled:
            return False
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {AIRTABLE_API_KEY}",
                    "Content-Type": "application/json"
                }
                
                table_url = get_table_url(video_type)
                logger.debug(f"Update params for {session_id}: model={model}, aspect_ratio={aspect_ratio}, duration={duration}")
                
                filter_formula = f"{{Session ID}}='{session_id}'"
                search_url = f"{table_url}?filterByFormula={quote(filter_formula)}"
                
                async with session.get(search_url, headers=headers) as resp:
                    if resp.status != 200:
                        response_text = await resp.text()
                        logger.warning(f"⚠️ Search failed for session {session_id}: HTTP {resp.status}")
                        logger.warning(f"   Response: {response_text[:200]}")
                        return False
                    
                    data = await resp.json()
                    if not data.get('records'):
                        logger.warning(f"⚠️ No records found for session {session_id}. Filter: {filter_formula}")
                        return False
                    
                    record_id = data['records'][0]['id']
                    logger.debug(f"Found record {record_id} for session {session_id}")
                    
                    update_fields = {}
                    if model:
                        update_fields[FIELD_NAMES["Model"]] = model
                    if aspect_ratio:
                        update_fields[FIELD_NAMES["Aspect Ratio"]] = aspect_ratio
                    if duration:
                        update_fields[FIELD_NAMES["Duration"]] = duration
                    if prompt:
                        update_fields[FIELD_NAMES["Prompt"]] = prompt[:500]
                    if prompt_ai:
                        update_fields[FIELD_NAMES["PromptAI"]] = prompt_ai[:2000]
                    
                    if not update_fields:
                        return True
                    
                    update_data = {"fields": update_fields}
                    
                    update_url = f"{table_url}/{record_id}"
                    async with session.patch(update_url, json=update_data, headers=headers) as update_resp:
                        if update_resp.status in [200, 201]:
                            logger.info(f"✅ Session {session_id} parameters updated in Airtable")
                            return True
                        else:
                            logger.warning(f"⚠️ Update parameters failed: {update_resp.status}")
                            return False
        except Exception as e:
            logger.error(f"❌ Error updating parameters: {e}")
            return False
    
    async def log_session_update(
        self,
        session_id: str,
        video_type: str,
        update_fields: Dict[str, Any]
    ) -> bool:
        """Обновить произвольные поля сессии"""
        if not self.enabled:
            return False
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {AIRTABLE_API_KEY}",
                    "Content-Type": "application/json"
                }
                
                table_url = get_table_url(video_type)
                
                filter_formula = f"{{Session ID}}='{session_id}'"
                search_url = f"{table_url}?filterByFormula={quote(filter_formula)}"
                
                async with session.get(search_url, headers=headers) as resp:
                    if resp.status != 200:
                        response_text = await resp.text()
                        logger.warning(f"⚠️ Failed to find record for session {session_id}: HTTP {resp.status}")
                        logger.warning(f"   Response: {response_text[:200]}")
                        return False
                    
                    data = await resp.json()
                    if not data.get('records'):
                        logger.warning(f"⚠️ No record found for session {session_id}. Filter: {filter_formula}")
                        return False
                    
                    record_id = data['records'][0]['id']
                    
                    mapped_fields = {}
                    for key, value in update_fields.items():
                        if key in FIELD_NAMES:
                            mapped_fields[FIELD_NAMES[key]] = value
                        else:
                            mapped_fields[key] = value
                    
                    update_data = {"fields": mapped_fields}
                    
                    update_url = f"{table_url}/{record_id}"
                    async with session.patch(update_url, json=update_data, headers=headers) as update_resp:
                        if update_resp.status in [200, 201]:
                            logger.info(f"✅ Session {session_id} updated in Airtable")
                            return True
                        else:
                            response_text = await update_resp.text()
                            logger.warning(f"⚠️ Update failed: {update_resp.status}")
                            logger.warning(f"   Response: {response_text[:200]}")
                            return False
        except Exception as e:
            logger.error(f"❌ Error updating session: {e}")
            return False
    
    async def log_session_complete(
        self,
        session_id: str,
        video_type: str,
        status: str,
        output_url: Optional[str] = None,
        processing_time: Optional[float] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """Логирование завершения сессии"""
        if not self.enabled:
            return False
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {AIRTABLE_API_KEY}",
                    "Content-Type": "application/json"
                }
                
                table_url = get_table_url(video_type)
                
                filter_formula = f"{{Session ID}}='{session_id}'"
                search_url = f"{table_url}?filterByFormula={quote(filter_formula)}"
                
                async with session.get(search_url, headers=headers) as resp:
                    if resp.status != 200:
                        response_text = await resp.text()
                        logger.warning(f"⚠️ Failed to find record for session {session_id}: HTTP {resp.status}")
                        logger.warning(f"   Response: {response_text[:200]}")
                        return False
                    
                    data = await resp.json()
                    if not data.get('records'):
                        logger.warning(f"⚠️ No record found for session {session_id}. Filter: {filter_formula}")
                        return False
                    
                    record_id = data['records'][0]['id']
                    
                    # Обновляем запись
                    update_fields = {
                        FIELD_NAMES["Status"]: status,
                        FIELD_NAMES["Completed At"]: datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                    }
                    
                    if output_url:
                        update_fields[FIELD_NAMES["Output"]] = output_url
                    
                    if processing_time:
                        update_fields[FIELD_NAMES["Processing Time"]] = processing_time
                    
                    if error_message:
                        update_fields[FIELD_NAMES["Error Message"]] = error_message[:500]
                    
                    logger.debug(f"Update fields: {update_fields}")
                    
                    update_data = {
                        "fields": update_fields
                    }
                    
                    update_url = f"{table_url}/{record_id}"
                    async with session.patch(update_url, json=update_data, headers=headers) as update_resp:
                        update_response = await update_resp.text()
                        if update_resp.status in [200, 201]:
                            logger.info(f"✅ Session {session_id} updated in Airtable")
                            return True
                        else:
                            logger.warning(f"⚠️ Update failed: {update_resp.status}")
                            logger.debug(f"Update response: {update_response}")
                            logger.debug(f"Update data: {update_data}")
                            return False
        except Exception as e:
            logger.error(f"❌ Error updating Airtable: {e}")
            return False
    
    async def log_scene_artifacts(
        self,
        session_id: str,
        video_type: str,
        scene_videos: Optional[list] = None,
        scene_photos: Optional[list] = None
    ) -> bool:
        """Логирование ссылок на видео и фото сцен в JSON формате"""
        if not self.enabled:
            return False
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {AIRTABLE_API_KEY}",
                    "Content-Type": "application/json"
                }
                
                table_url = get_table_url(video_type)
                
                filter_formula = f"{{Session ID}}='{session_id}'"
                search_url = f"{table_url}?filterByFormula={quote(filter_formula)}"
                
                async with session.get(search_url, headers=headers) as resp:
                    if resp.status != 200:
                        response_text = await resp.text()
                        logger.warning(f"⚠️ Failed to find record for session {session_id}: HTTP {resp.status}")
                        logger.warning(f"   Response: {response_text[:200]}")
                        return False
                    
                    data = await resp.json()
                    if not data.get('records'):
                        logger.warning(f"⚠️ No record found for session {session_id}. Filter: {filter_formula}")
                        return False
                    
                    record_id = data['records'][0]['id']
                    
                    update_fields = {}
                    if scene_videos:
                        update_fields[FIELD_NAMES["Scene Videos"]] = json.dumps(scene_videos, ensure_ascii=False, indent=2)
                    if scene_photos:
                        update_fields[FIELD_NAMES["Scene Photos"]] = json.dumps(scene_photos, ensure_ascii=False, indent=2)
                    
                    if not update_fields:
                        return True
                    
                    update_data = {"fields": update_fields}
                    
                    update_url = f"{table_url}/{record_id}"
                    async with session.patch(update_url, json=update_data, headers=headers) as update_resp:
                        if update_resp.status in [200, 201]:
                            logger.info(f"✅ Scene artifacts logged for session {session_id}")
                            return True
                        else:
                            response_text = await update_resp.text()
                            logger.warning(f"⚠️ Failed to log scene artifacts: {update_resp.status}")
                            logger.warning(f"   Response: {response_text[:200]}")
                            return False
        except Exception as e:
            logger.error(f"❌ Error logging scene artifacts: {e}")
            return False


session_logger = AirtableSessionLogger()
