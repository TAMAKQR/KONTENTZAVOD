"""Генератор видео через Replicate API"""
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Optional, List, Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

import replicate
from replicate import Client
from openai import AsyncOpenAI
from src.config import REPLICATE_API_TOKEN, GROK_API_KEY
from src.prompts_config import prompts_manager

logger = logging.getLogger(__name__)


class VideoGenerator:
    """Класс для генерации видео через Replicate API"""
    
    def __init__(self):
        self.replicate_token = REPLICATE_API_TOKEN
        self.replicate_client = Client(api_token=REPLICATE_API_TOKEN)
        
        # Инициализируем Groq API
        self.grok_client = AsyncOpenAI(
            api_key=GROK_API_KEY,
            base_url="https://api.groq.com/openai/v1"
        )
        
        logger.info(f"✅ Groq API инициализирован (llama-3.3-70b-versatile)")
        
        # Модели
        self.models = {
            "kling": "kwaivgi/kling-v2.5-turbo-pro",
            "veo": "google/veo-3.1-fast"
        }
        
        # Параметры по умолчанию
        self.default_params = {
            "kling": {
                "duration": 5,
                "aspect_ratio": "16:9",
                "negative_prompt": ""
            },
            "veo": {
                "duration": 8,
                "aspect_ratio": "16:9"
            }
        }

    async def enhance_prompt_with_gemini(self, prompt: str, num_scenes: int = 3, duration_per_scene: int = 5) -> Dict:
        """
        Улучшает промт через Gemini AI и разбивает на РАЗНЫЕ сцены
        
        Args:
            prompt: Оригинальный промт
            num_scenes: Количество сцен
            duration_per_scene: Длительность каждой сцены в секундах
            
        Returns:
            Dict с улучшенным промтом и уникальными сценами
        """
        try:
            enhanced_prompt = prompt
            
            # 🎯 Сначала улучшаем исходный промт
            try:
                enhance_response = await self.grok_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": f"Improve this video description to make it more vivid, specific, and suitable for AI video generation. Keep it concise (1-2 sentences):\n\n{prompt}"}],
                    temperature=0.5
                )
                enhanced_prompt = enhance_response.choices[0].message.content.strip()
                logger.info(f"✨ Промт улучшен: {enhanced_prompt[:100]}...")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось улучшить промт: {e}, используем оригинал")
                enhanced_prompt = prompt
            
            # 📝 ИНСТРУКЦИЯ для Gemini из конфига
            system_message = prompts_manager.get_prompt("gemini_scene_breakdown")
            
            user_template = prompts_manager.get_prompt("gemini_scene_user_message")
            user_message = user_template.format(num_scenes=num_scenes, prompt=enhanced_prompt, duration_per_scene=duration_per_scene)

            # Используем Groq для разбиения промта на сцены
            full_message = f"{system_message}\n\nUSER: {user_message}"
            
            response = await self.grok_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": full_message}],
                temperature=0.7
            )
            
            response_text = response.choices[0].message.content.strip()
            logger.info(f"🤖 Groq ответ получен, длина: {len(response_text)} символов")
            
            # Парсим JSON - ищем массив
            start_idx = response_text.find('[')
            end_idx = response_text.rfind(']') + 1
            
            if start_idx == -1 or end_idx == 0:
                # Если нет массива, ищем объект
                start_idx = response_text.find('{')
                end_idx = response_text.rfind('}') + 1
                
                if start_idx == -1 or end_idx == 0:
                    logger.error(f"❌ JSON не найден в ответе: {response_text[:200]}")
                    raise ValueError("JSON not found in response")
                
                # Если один объект - оборачиваем в массив
                json_str = response_text[start_idx:end_idx]
                result = {
                    "enhanced_prompt": enhanced_prompt,
                    "scenes": [json.loads(json_str)]
                }
            else:
                json_str = response_text[start_idx:end_idx]
                scenes_list = json.loads(json_str)
                result = {
                    "enhanced_prompt": enhanced_prompt,
                    "scenes": scenes_list if isinstance(scenes_list, list) else [scenes_list]
                }
            
            # Валидация и нормализация
            if "scenes" not in result:
                result["scenes"] = result if isinstance(result, list) else [result]
            
            if not isinstance(result["scenes"], list):
                result["scenes"] = [result["scenes"]]
            
            # Обеспечиваем ровно num_scenes сцен
            actual_scenes = result.get("scenes", [])
            if len(actual_scenes) < num_scenes:
                logger.warning(f"⚠️ GPT создал {len(actual_scenes)} вместо {num_scenes}, дополняю...")
                # Добавляем недостающие сцены как вариации
                for i in range(len(actual_scenes), num_scenes):
                    actual_scenes.append({
                        "id": i + 1,
                        "prompt": f"{enhanced_prompt} - угол {i + 1}",
                        "duration": duration_per_scene,
                        "atmosphere": "cinematic"
                    })
            elif len(actual_scenes) > num_scenes:
                actual_scenes = actual_scenes[:num_scenes]
            
            result["scenes"] = actual_scenes
            
            # Присваиваем ID и длительность
            for i, scene in enumerate(result["scenes"]):
                scene["id"] = i + 1
                scene["duration"] = duration_per_scene
                if "atmosphere" not in scene:
                    scene["atmosphere"] = "cinematic"
            
            logger.info(f"✅ GPT создал {len(result['scenes'])} сцен")
            
            # Логируем сцены ДО перевода
            for i, scene in enumerate(result['scenes']):
                logger.info(f"   📝 Сцена {i+1} (ДО перевода): '{scene.get('prompt', '')}'")
            
            # Переводим сцены на русский язык
            logger.info(f"🌍 Переводу сцены на русский...")
            result = await self._translate_scenes_to_russian(result)
            
            # Логируем сцены ПОСЛЕ перевода
            for i, scene in enumerate(result['scenes']):
                logger.info(f"   🇷🇺 Сцена {i+1} (ПОСЛЕ перевода): '{scene.get('prompt', '')}'")
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Ошибка парсинга JSON: {e}")
            logger.error(f"❌ Ответ: {response_text[:300]}")
            raise
        except Exception as e:
            logger.error(f"❌ Ошибка при обработке GPT: {e}")
            logger.error(f"❌ Детали: {str(e)}")
            
            # ⚠️ Fallback - создаем разнообразные сцены с разными ракурсами и стилями
            logger.warning(f"⚠️ Groq не ответил, создаю {num_scenes} сцен с автоматическими вариациями...")
            
            scene_variations = [
                ("общий план, широкий кадр", "cinematic"),
                ("крупный план деталей и текстуры", "dramatic"),
                ("динамичный кадр, движение камеры", "action"),
                ("закрытый кадр, фокус на главном", "focus"),
                ("панорамный кадр, раскрывающий всю суть", "cinematic"),
                ("финальный кадр, завершающий сюжет", "climax")
            ]
            
            scenes = []
            for i in range(num_scenes):
                if i < len(scene_variations):
                    variation, atmosphere = scene_variations[i]
                else:
                    variation = f"ракурс {i+1}"
                    atmosphere = "cinematic"
                
                scene_prompt = prompt if variation in prompt else f"{prompt} - {variation}"
                
                scenes.append({
                    "id": i + 1,
                    "prompt": scene_prompt,
                    "duration": duration_per_scene,
                    "atmosphere": atmosphere
                })
            
            # Логируем каждую созданную сцену
            for scene in scenes:
                logger.info(f"   ⚠️ Сцена {scene['id']}: '{scene['prompt'][:80]}'")
            
            return {
                "enhanced_prompt": prompt,
                "scenes": scenes
            }
    
    async def _translate_scenes_to_russian(self, scenes_result: Dict) -> Dict:
        """
        Переводит все сцены на русский язык
        
        Args:
            scenes_result: Dict со сценами и enhanced_prompt
            
        Returns:
            Dict с переведенными сценами
        """
        try:
            scenes = scenes_result.get("scenes", [])
            if not scenes:
                return scenes_result
            
            logger.info(f"🌍 _translate_scenes_to_russian: получил {len(scenes)} сцен")
            for i, scene in enumerate(scenes):
                prompt_text = scene.get('prompt', '')[:100]
                logger.info(f"   INPUT Сцена {i+1}: '{prompt_text}'")
            
            # Подготавливаем текст для перевода
            scenes_to_translate = []
            for scene in scenes:
                scenes_to_translate.append({
                    "id": scene.get("id"),
                    "prompt": scene.get("prompt"),
                    "atmosphere": scene.get("atmosphere", "")
                })
            
            system_prompt = prompts_manager.get_prompt("gemini_translation")
            
            translation_template = prompts_manager.get_prompt("gemini_translation_request")
            translation_request = translation_template.format(
                scenes_json=json.dumps(scenes_to_translate, ensure_ascii=False, indent=2)
            )
            
            full_message = f"{system_prompt}\n\n{translation_request}"
            
            response = await self.grok_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": full_message}],
                temperature=0.3
            )
            
            response_text = response.choices[0].message.content.strip()
            logger.info(f"🤖 Groq перевод ответ: {response_text[:150]}...")
            
            # Парсим переведенные сцены - удаляем markdown backticks
            cleaned_response = response_text
            if "```json" in cleaned_response:
                cleaned_response = cleaned_response.replace("```json", "").replace("```", "")
            elif "```" in cleaned_response:
                cleaned_response = cleaned_response.replace("```", "")
            
            cleaned_response = cleaned_response.strip()
            
            # Ищем JSON (может быть список или объект)
            translated_list = None
            try:
                # Сначала попробуем как список
                start_idx = cleaned_response.find('[')
                if start_idx != -1:
                    # Считаем скобки чтобы найти конец
                    bracket_count = 0
                    end_idx = start_idx
                    for i, char in enumerate(cleaned_response[start_idx:]):
                        if char == '[':
                            bracket_count += 1
                        elif char == ']':
                            bracket_count -= 1
                            if bracket_count == 0:
                                end_idx = start_idx + i + 1
                                break
                    
                    if end_idx > start_idx:
                        translated_text = cleaned_response[start_idx:end_idx]
                        translated_list = json.loads(translated_text)
                
                # Если не список, попробуем как объект
                if translated_list is None:
                    start_idx = cleaned_response.find('{')
                    if start_idx != -1:
                        bracket_count = 0
                        end_idx = start_idx
                        for i, char in enumerate(cleaned_response[start_idx:]):
                            if char == '{':
                                bracket_count += 1
                            elif char == '}':
                                bracket_count -= 1
                                if bracket_count == 0:
                                    end_idx = start_idx + i + 1
                                    break
                        
                        if end_idx > start_idx:
                            translated_text = cleaned_response[start_idx:end_idx]
                            translated_list = json.loads(translated_text)
            
            except json.JSONDecodeError as je:
                logger.warning(f"⚠️ JSON парсинг ошибка: {je}")
                logger.warning(f"⚠️ Чистый ответ: {cleaned_response[:200]}...")
                return scenes_result
            
            if translated_list is None:
                logger.warning(f"⚠️ Не удалось распарсить переведенные сцены, используем оригинальные")
                return scenes_result
            
            # Если это не список, преобразуем в список
            if not isinstance(translated_list, list):
                translated_list = [translated_list]
            
            # Применяем переводы к оригинальным сценам
            for i, scene in enumerate(scenes):
                if i < len(translated_list):
                    translated = translated_list[i]
                    if "prompt" in translated and translated["prompt"]:
                        scene["prompt"] = translated["prompt"]
                    if "atmosphere" in translated and translated["atmosphere"]:
                        scene["atmosphere"] = translated["atmosphere"]
                else:
                    logger.warning(f"⚠️ Перевод не получен для сцены {i+1}, оставляю оригинальный текст")
            
            # Переводим enhanced_prompt если есть
            if "enhanced_prompt" in scenes_result:
                enhanced = scenes_result["enhanced_prompt"]
                enhanced_translation = await self._translate_text(enhanced)
                scenes_result["enhanced_prompt"] = enhanced_translation
            
            logger.info(f"✅ Сцены переведены на русский язык")
            
            # 🔒 Убеждаемся, что у каждой сцены есть промт
            for i, scene in enumerate(scenes):
                if not scene.get('prompt'):
                    logger.error(f"❌ КРИТИЧНО: Сцена {i+1} потеряла промт! Это баг в переводе")
                    # Пытаемся восстановить из оригинала
                    if i < len(scenes_to_translate):
                        original_prompt = scenes_to_translate[i].get('prompt', f'Сцена {i+1}')
                        scene['prompt'] = original_prompt
                        logger.warning(f"   ✅ Восстановлен оригинальный промт: '{original_prompt[:50]}'")
            
            # Логируем результат после перевода
            for i, scene in enumerate(scenes):
                prompt_text = scene.get('prompt', '')[:100]
                logger.info(f"   OUTPUT Сцена {i+1}: '{prompt_text}'")
            
            return scenes_result
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при переводе сцен: {e}")
            logger.warning(f"⚠️ Пытаюсь использовать встроенный словарь для перевода...")
            
            try:
                scenes = scenes_result.get("scenes", [])
                for i, scene in enumerate(scenes):
                    original_prompt = scene.get("prompt", "")
                    if original_prompt:
                        translated_prompt = self._simple_fallback_translate(original_prompt)
                        scene["prompt"] = translated_prompt
                        logger.info(f"   ✅ Сцена {i+1} переведена (словарь): '{translated_prompt[:50]}'")
                
                return scenes_result
            except Exception as fallback_e:
                logger.warning(f"⚠️ Словарь перевод failed: {fallback_e}")
                logger.warning(f"⚠️ Возвращаю оригинальные сцены без перевода")
                return scenes_result
    
    def _simple_fallback_translate(self, text: str) -> str:
        """Встроенный словарь для быстрого перевода без API"""
        translations = {
            "panoramic shot": "панорамный кадр",
            "steppe": "степь",
            "sun-drenched": "залитый солнцем",
            "slowly focusing": "медленно фокусируясь",
            "weathered hand": "загорелая рука",
            "offering": "предлагающая",
            "warm": "тепло",
            "inviting": "приглашающе",
            "shot": "кадр",
            "hand": "рука",
            "piece": "кусок",
            "close-up": "крупный план",
            "texture": "текстура",
            "stitched": "сшитый",
            "garment": "одежда",
            "camera": "камера",
            "pans": "панорамирует",
            "reveal": "показывает",
            "confident": "уверенный",
            "expression": "выражение",
            "time-lapse": "ускоренная съёмка",
            "diverse": "разнообразные",
            "models": "модели",
            "walking": "идущие",
            "vibrant": "яркий",
            "city street": "городская улица",
            "showcasing": "демонстрируя",
            "outfits": "наряды",
            "collection": "коллекция",
            "wide shot": "широкий план",
            "dynamic": "динамичный",
            "motion": "движение",
            "detail": "деталь",
            "texture": "текстура",
            "dramatic": "драматичный",
            "cinematic": "кинематографичный"
        }
        
        result = text.lower()
        for en, ru in translations.items():
            result = result.replace(en.lower(), ru)
        
        return result
    
    async def _translate_text(self, text: str) -> str:
        """
        Переводит текст на русский язык через Gemini с fallback
        
        Args:
            text: Текст для перевода
            
        Returns:
            Переведенный текст
        """
        try:
            response = await self.grok_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": f"Translate to Russian accurately: {text}"}],
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка Groq при переводе: {e}")
            logger.warning(f"🔄 Использую встроенный словарь для перевода...")
            
            fallback_translation = self._simple_fallback_translate(text)
            logger.warning(f"   Переведено через словарь: '{fallback_translation[:50]}'")
            return fallback_translation

    async def enhance_video_prompt_with_image(self, image_url: str, original_prompt: str, scene_number: int = 1) -> str:
        """
        Анализирует фото через Gemini Vision и улучшает промт для видео
        Это новый подход: сначала фото генерируется, потом Gemini его анализирует и создает промт для видео
        
        Args:
            image_url: URL сгенерированного фото
            original_prompt: Оригинальный промт сцены
            scene_number: Номер сцены для логирования
            
        Returns:
            Улучшенный промт для видео на основе анализа фото
        """
        try:
            logger.info(f"🎬 Сцена {scene_number}: Анализирую фото через Groq...")
            
            vision_prompt = f"""You are a professional video director. Analyze this product/subject image and create an improved video prompt.

ORIGINAL PROMPT: {original_prompt}

Based on what you see in the image:
1. Describe the visual style, lighting, and composition
2. Suggest the best camera movement for a video
3. Create a dynamic video prompt that builds on this visual

Return ONLY the enhanced video prompt (2-3 sentences), nothing else."""

            response = await self.grok_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": vision_prompt},
                            {"type": "image_url", "image_url": {"url": image_url}} if image_url.startswith('http') else {"type": "text", "text": ""}
                        ] if image_url.startswith('http') else [{"type": "text", "text": vision_prompt}]
                    }
                ],
                temperature=0.7
            )
            
            enhanced_prompt = response.choices[0].message.content.strip()
            logger.info(f"✅ Сцена {scene_number}: Промт улучшен через Vision анализ")
            logger.info(f"   Улучшенный промт: {enhanced_prompt[:100]}...")
            
            return enhanced_prompt
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при анализе фото (сцена {scene_number}): {e}")
            logger.warning(f"   Используем оригинальный промт")
            return original_prompt

    async def generate_scene(
        self,
        prompt: str,
        model: str = "kling",
        duration: int = 5,
        aspect_ratio: str = "16:9",
        start_image_url: Optional[str] = None,
        scene_number: int = 1,
        require_image: bool = False,
        resolution: str = "1080p",
        generate_audio: bool = True,
        negative_prompt: str = ""
    ) -> Dict:
        """
        Генерирует одну сцену видео
        
        Args:
            prompt: Промт для видео
            model: Модель (kling, veo)
            duration: Длительность в секундах
            aspect_ratio: Соотношение сторон
            start_image_url: URL начального фрейма (для связности)
            scene_number: Номер сцены для логирования
            require_image: Требуется ли изображение для генерации (для image-to-video режима)
            resolution: Разрешение видео (только для Veo: 720p, 1080p)
            generate_audio: Генерировать ли звук (только для Veo)
            negative_prompt: Отрицательный промт (для Kling и Veo)
            
        Returns:
            Dict с результатом или ошибкой
        """
        try:
            # 🔴 КРИТИЧЕСКОЕ ЛОГИРОВАНИЕ В НАЧАЛЕ
            logger.info(f"🎬 🎬 🎬 [GENERATE_SCENE ВЫЗВАНА] 🎬 🎬 🎬")
            logger.info(f"   prompt = {prompt[:50]}...")
            logger.info(f"   model = {model}")
            logger.info(f"   start_image_url = {start_image_url}")
            logger.info(f"   start_image_url type = {type(start_image_url).__name__}")
            logger.info(f"   require_image = {require_image}")
            logger.info(f"   require_image AND NOT start_image_url = {require_image and not start_image_url}")
            
            # ❌ ОШИБКА: Если требуется изображение, но его нет - не генерируем
            if require_image and not start_image_url:
                error_msg = f"❌ ОШИБКА: Для режима image-to-video обязательно нужно изображение! Загрузи фото перед генерацией."
                logger.error(error_msg)
                logger.error(f"   require_image={require_image}, start_image_url={start_image_url}")
                return {
                    "status": "error",
                    "error": error_msg,
                    "code": "MISSING_IMAGE"
                }
            
            model_id = self.models.get(model, self.models["kling"])
            
            # Подготавливаем параметры в зависимости от модели
            input_params = {
                "prompt": prompt,
                "duration": duration,
                "aspect_ratio": aspect_ratio
            }
            
            logger.info(f"🎬 Сцена {scene_number}: Подготавливаю параметры для {model}")
            logger.info(f"   Промт: {prompt[:60]}...")
            logger.info(f"   Параметры: duration={duration}s, aspect_ratio={aspect_ratio}")
            logger.info(f"   IMAGE_URL получен: {start_image_url}")  # 👈 ДЛЯ ОТЛАДКИ
            
            # Добавляем специфичные параметры
            if "kling" in model.lower():
                input_params["negative_prompt"] = negative_prompt if negative_prompt else ""
                if start_image_url:
                    input_params["image"] = start_image_url  # 📌 Kling использует параметр "image"
                    logger.info(f"   ✅ Используется image для связности: {start_image_url[:80]}...")
                    logger.info(f"   ✓ Проверка: 'image' в input_params? {'image' in input_params}")
                    logger.info(f"   ✓ input_params['image'] = {input_params.get('image', 'NOT FOUND')}")
                else:
                    logger.info(f"   ⚠️ image_url пуст или None - видео генерируется БЕЗ начального фрейма")
            elif "veo" in model.lower():
                # ✅ Veo 3.1 полная поддержка всех параметров
                if start_image_url:
                    input_params["image"] = start_image_url
                    logger.info(f"   ✅ Veo: Используется image для анимации: {start_image_url[:80]}...")
                else:
                    logger.info(f"   ⚠️ Veo: image_url пуст - генерируется text-to-video")
                
                # Добавляем параметры Veo
                input_params["resolution"] = resolution  # 720p или 1080p
                input_params["generate_audio"] = generate_audio  # True/False
                
                if negative_prompt:
                    input_params["negative_prompt"] = negative_prompt
                    logger.info(f"   ❌ Veo: negative_prompt: {negative_prompt[:50]}...")
                
                logger.info(f"   🎬 Veo: resolution={resolution}, audio={generate_audio}")
            
            logger.info(f"🎬 Сцена {scene_number}: Отправляю запрос на Replicate API...")
            logger.info(f"   Model ID: {model_id}")
            logger.info(f"   📤 JSON параметры отправляются: {json.dumps(input_params, ensure_ascii=False, indent=2)}")  # 👈 ДЛЯ ОТЛАДКИ
            logger.info(f"   🔍 Финальная проверка input_params перед API:")
            logger.info(f"      - 'image' в params? {'image' in input_params}")
            logger.info(f"      - 'prompt' в params? {'prompt' in input_params}")
            logger.info(f"      - 'duration' в params? {'duration' in input_params}")
            logger.info(f"      - 'aspect_ratio' в params? {'aspect_ratio' in input_params}")
            
            # Используем синхронный replicate.run в потоке
            logger.info(f"🔄 Вызываю replicate.run() с параметрами...")
            logger.info(f"   input_params = {input_params}")
            logger.info(f"=" * 80)
            logger.info(f"📋 Model ID: {model_id}")
            logger.info(f"📋 JSON payload:")
            logger.info(json.dumps(input_params, ensure_ascii=False, indent=2))
            logger.info(f"=" * 80)
            
            # 🚀 РЕАЛЬНЫЙ API ВЫЗОВ
            loop = asyncio.get_event_loop()
            output = await loop.run_in_executor(
                None,
                lambda: self.replicate_client.run(
                    model_id,
                    input=input_params
                )
            )
            
            output_str = str(output) if output else "None"
            logger.info(f"✅ Сцена {scene_number}: Видео сгенерировано!")
            logger.info(f"   URL: {output_str[:80]}...")
            logger.info(f"   Полный ответ Replicate: {output}")
            
            return {
                "status": "success",
                "video_url": output_str,
                "model": model,
                "duration": duration,
                "scene_number": scene_number
            }
            
        except Exception as e:
            logger.error(f"❌ Сцена {scene_number}: Ошибка генерации видео!")
            logger.error(f"   Ошибка: {str(e)}")
            logger.error(f"   Тип: {type(e).__name__}")
            import traceback
            logger.error(f"   Traceback: {traceback.format_exc()}")
            return {
                "status": "error",
                "error": str(e),
                "model": model,
                "scene_number": scene_number
            }

    async def generate_multiple_scenes(
        self,
        scenes: List[Dict],
        model: str = "kling",
        start_image_url: Optional[str] = None,
        scene_image_urls: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Генерирует несколько сцен параллельно
        
        Args:
            scenes: Список сцен с промтами
            model: Модель для генерации
            start_image_url: URL начального фрейма (для первой сцены, если нет scene_image_urls)
            scene_image_urls: Список URLs изображений - по одному для каждой сцены (приоритет над start_image_url)
            
        Returns:
            Список результатов генерации
        """
        logger.info(f"🎬 Начинаю параллельную генерацию {len(scenes)} сцен через {model}...")
        
        # ✅ ИСПРАВЛЕНИЕ: Теперь поддерживаем фото для КАЖДОЙ сцены
        if scene_image_urls:
            logger.info(f"📸 Передаю {len(scene_image_urls)} фото - по одному для каждой сцены")
            if len(scene_image_urls) != len(scenes):
                logger.warning(f"⚠️ Количество фото ({len(scene_image_urls)}) != количество сцен ({len(scenes)})")
        
        tasks = []
        
        for i, scene in enumerate(scenes):
            # Выбираем фото для этой сцены
            scene_image = None
            if scene_image_urls and i < len(scene_image_urls):
                scene_image = scene_image_urls[i]
            elif start_image_url and i == 0:
                scene_image = start_image_url
            
            if scene_image:
                logger.info(f"📸 Сцена {i+1}: будет использовать загруженное фото")
            
            task = self.generate_scene(
                prompt=scene["prompt"],
                model=model,
                duration=scene.get("duration", 5),
                aspect_ratio=scene.get("aspect_ratio", "16:9"),
                start_image_url=scene_image,  # ✅ Передаем фото для ЭТОЙ сцены (не только первой!)
                scene_number=i + 1
            )
            tasks.append(task)
        
        # Генерируем ВСЕ сцены параллельно (asyncio.gather)
        # Это НАМНОГО быстрее чем последовательно!
        logger.info(f"⚡ Отправляю {len(tasks)} запросов параллельно на Replicate API...")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Проверяем результаты на ошибки
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"❌ Сцена {i + 1}: Исключение: {result}")
                processed_results.append({
                    "status": "error",
                    "error": str(result),
                    "scene_number": i + 1
                })
            else:
                processed_results.append(result)
        
        logger.info(f"✅ Параллельная генерация завершена. Результаты: {len(processed_results)} сцен")
        return processed_results

    async def generate_photo(
        self,
        prompt: str,
        model: str = "google/nano-banana",
        reference_url: Optional[str] = None,
        scene_number: int = 1
    ) -> Dict:
        """
        Генерирует фото через google/nano-banana
        
        Args:
            prompt: Промт для генерации фото
            model: Модель (google/nano-banana или google/imagen-4)
            reference_url: URL фото-референса для стилизации
            scene_number: Номер сцены для логирования
            
        Returns:
            Dict с результатом или ошибкой
        """
        try:
            logger.info(f"📸 Сцена {scene_number}: Генерирую фото через {model}...")
            logger.info(f"   Промт: {prompt[:60]}...")
            
            # Подготавливаем параметры
            input_params = {
                "prompt": prompt,
            }
            
            # Если есть референс, добавляем его
            if reference_url and model == "google/nano-banana":
                input_params["image"] = reference_url
                input_params["strength"] = 0.7  # Сила применения стиля референса
                logger.info(f"   Используется referencias для стилизации")
            
            logger.info(f"🎬 Сцена {scene_number}: Отправляю запрос на Replicate API...")
            logger.info(f"   Model: {model}")
            
            # Используем синхронный replicate.run в потоке
            loop = asyncio.get_event_loop()
            output = await loop.run_in_executor(
                None,
                lambda: self.replicate_client.run(
                    model,
                    input=input_params
                )
            )
            
            output_str = str(output) if output else "None"
            logger.info(f"✅ Сцена {scene_number}: Фото сгенерировано!")
            logger.info(f"   URL: {output_str[:80]}...")
            
            return {
                "status": "success",
                "photo_url": output_str,
                "model": model,
                "scene_number": scene_number
            }
            
        except Exception as e:
            logger.error(f"❌ Сцена {scene_number}: Ошибка генерации фото!")
            logger.error(f"   Ошибка: {str(e)}")
            logger.error(f"   Тип: {type(e).__name__}")
            import traceback
            logger.error(f"   Traceback: {traceback.format_exc()}")
            return {
                "status": "error",
                "error": str(e),
                "model": model,
                "scene_number": scene_number
            }