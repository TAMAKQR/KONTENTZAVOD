"""Конфигурация системных промтов для ИИ"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

PROMPTS_FILE = Path(__file__).parent.parent / "prompts.json"

DEFAULT_PROMPTS = {
    "gemini_scene_breakdown": """You are a professional video director. Create unique, visually distinct scenes from a product/concept description.

RULES:
1. Return ONLY valid JSON, no markdown or explanations
2. Create DIFFERENT angles/moments for each scene (not repetition)
3. Each scene must have a unique visual perspective
4. Keep prompts concise but vivid (1-2 sentences)

REQUIRED JSON FORMAT - Return valid JSON array like this:
[
  {"id": 1, "prompt": "scene description with unique angle/moment", "duration": 5, "atmosphere": "cinematic"},
  {"id": 2, "prompt": "different perspective or progression", "duration": 5, "atmosphere": "dramatic"}
]""",
    
    "gemini_scene_user_message": """Break this into {num_scenes} VISUALLY DIFFERENT scenes (not parts of same scene):

CONCEPT: {prompt}

IMPORTANT: 
- Scene 1: Opening/approach view
- Scene 2: Detail/close-up or different angle  
- Scene 3+: Progression or new perspective
- Each must show something new, not repeat

Create {num_scenes} unique scenes with {duration_per_scene}sec each.""",
    
    "gemini_translation": """You are a professional translator from English to Russian. Translate video scene descriptions accurately and naturally.""",
    
    "gemini_translation_request": """Translate the following video scenes to Russian. 
Keep the same JSON structure. Translate ONLY the "prompt" and "atmosphere" fields.

Scenes to translate:
{scenes_json}

Return ONLY valid JSON with translated content, nothing else."""
}


class PromptsManager:
    """Управление системными промтами"""
    
    def __init__(self):
        self.prompts = self._load_prompts()
    
    def _load_prompts(self) -> dict:
        """Загрузить промты из файла или использовать дефолтные"""
        if PROMPTS_FILE.exists():
            try:
                with open(PROMPTS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Не удалось загрузить промты: {e}")
                return DEFAULT_PROMPTS.copy()
        return DEFAULT_PROMPTS.copy()
    
    def save_prompts(self):
        """Сохранить промты в файл"""
        try:
            with open(PROMPTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.prompts, f, ensure_ascii=False, indent=2)
            logger.info("✅ Промты сохранены")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения промтов: {e}")
            return False
    
    def get_prompt(self, key: str) -> str:
        """Получить промт по ключу"""
        return self.prompts.get(key, DEFAULT_PROMPTS.get(key, ""))
    
    def set_prompt(self, key: str, value: str) -> bool:
        """Установить промт"""
        self.prompts[key] = value
        return self.save_prompts()
    
    def get_all_prompts(self) -> dict:
        """Получить все промты"""
        return self.prompts.copy()
    
    def reset_prompt(self, key: str) -> bool:
        """Восстановить дефолтный промт"""
        if key in DEFAULT_PROMPTS:
            self.prompts[key] = DEFAULT_PROMPTS[key]
            return self.save_prompts()
        return False
    
    def reset_all(self) -> bool:
        """Восстановить все дефолтные промты"""
        self.prompts = DEFAULT_PROMPTS.copy()
        return self.save_prompts()


prompts_manager = PromptsManager()
