"""Генератор видео через Replicate API"""
import asyncio
import json
import logging
from typing import Optional, List, Dict
import replicate
from replicate import Client
import google.generativeai as genai
from config import REPLICATE_API_TOKEN, OPENAI_API_KEY, GEMINI_API_KEY

logger = logging.getLogger(__name__)


class VideoGenerator:
    """Класс для генерации видео через Replicate API"""
    
    def __init__(self):
        self.replicate_token = REPLICATE_API_TOKEN
        self.replicate_client = Client(api_token=REPLICATE_API_TOKEN)
        
        # Инициализируем Gemini
        genai.configure(api_key=GEMINI_API_KEY)
        # Используем gemini-2.5-flash - последняя доступная модель (1.5 была выведена из обслуживания)
        self.gemini_model = genai.GenerativeModel("gemini-2.5-flash")
        
        logger.info(f"✅ Gemini инициализирован вместо OpenAI")
        
        # Модели
        self.models = {
            "kling": "kwaivgi/kling-v2.5-turbo-pro",
            "sora": "openai/sora-2",
            "veo": "google/veo-3.1-fast"
        }
        
        # Параметры по умолчанию
        self.default_params = {
            "kling": {
                "duration": 5,
                "aspect_ratio": "16:9",
                "negative_prompt": ""
            },
            "sora": {
                "duration": 10,
                "aspect_ratio": "16:9"
            },
            "veo": {
                "duration": 8,
                "aspect_ratio": "16:9"
            }
        }

    async def enhance_prompt_with_gpt(self, prompt: str, num_scenes: int = 3, duration_per_scene: int = 5) -> Dict:
        """
        Улучшает промт через GPT-4 и разбивает на РАЗНЫЕ сцены
        
        Args:
            prompt: Оригинальный промт
            num_scenes: Количество сцен
            duration_per_scene: Длительность каждой сцены в секундах
            
        Returns:
            Dict с улучшенным промтом и уникальными сценами
        """
        try:
            # 📝 УЛУЧШЕННАЯ ИНСТРУКЦИЯ для GPT
            system_message = """You are a professional video director. Create unique, visually distinct scenes from a product/concept description.

RULES:
1. Return ONLY valid JSON, no markdown or explanations
2. Create DIFFERENT angles/moments for each scene (not repetition)
3. Each scene must have a unique visual perspective
4. Keep prompts concise but vivid (1-2 sentences)

REQUIRED JSON FORMAT - Return valid JSON array like this:
[
  {"id": 1, "prompt": "scene description with unique angle/moment", "duration": 5, "atmosphere": "cinematic"},
  {"id": 2, "prompt": "different perspective or progression", "duration": 5, "atmosphere": "dramatic"}
]"""

            user_message = f"""Break this into {num_scenes} VISUALLY DIFFERENT scenes (not parts of same scene):

CONCEPT: {prompt}

IMPORTANT: 
- Scene 1: Opening/approach view
- Scene 2: Detail/close-up or different angle  
- Scene 3+: Progression or new perspective
- Each must show something new, not repeat

Create {num_scenes} unique scenes with {duration_per_scene}sec each."""

            # Используем Gemini вместо OpenAI
            full_message = f"{system_message}\n\nUSER: {user_message}"
            
            response = await asyncio.to_thread(
                self.gemini_model.generate_content,
                full_message
            )
            
            response_text = response.text.strip()
            logger.info(f"🤖 Gemini ответ получен")
            logger.info(f"📝 GPT ответ получен, длина: {len(response_text)} символов")
            
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
                result = {"scenes": [json.loads(json_str)]}
            else:
                json_str = response_text[start_idx:end_idx]
                scenes_list = json.loads(json_str)
                result = {
                    "enhanced_prompt": prompt,
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
                        "prompt": f"{prompt} - угол {i + 1}",
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
            
            # ⚠️ Лучший фоллбак - создаем РАЗНЫЕ сцены вручную
            logger.info(f"⚠️ Создаю {num_scenes} РАЗНЫХ сцен автоматически...")
            scenes = [
                {
                    "id": 1,
                    "prompt": f"{prompt} - общий план",
                    "duration": duration_per_scene,
                    "atmosphere": "cinematic"
                },
                {
                    "id": 2,
                    "prompt": f"{prompt} - крупный план деталей",
                    "duration": duration_per_scene,
                    "atmosphere": "dramatic"
                }
            ]
            
            # Добавляем третью и последующие сцены если нужно
            if num_scenes > 2:
                scenes.append({
                    "id": 3,
                    "prompt": f"{prompt} - финальный ракурс",
                    "duration": duration_per_scene,
                    "atmosphere": "cinematic"
                })
            
            for i in range(3, num_scenes):
                scenes.append({
                    "id": i + 1,
                    "prompt": f"{prompt} - перспектива {i}",
                    "duration": duration_per_scene,
                    "atmosphere": "cinematic"
                })
            
            # Логируем каждую созданную сцену
            for scene in scenes:
                logger.info(f"   ✅ Сцена {scene['id']}: '{scene['prompt']}'")
            
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
            
            translation_request = f"""Translate the following video scenes to Russian. 
Keep the same JSON structure. Translate ONLY the "prompt" and "atmosphere" fields.

Scenes to translate:
{json.dumps(scenes_to_translate, ensure_ascii=False, indent=2)}

Return ONLY valid JSON with translated content, nothing else."""
            
            system_prompt = "You are a professional translator from English to Russian. Translate video scene descriptions accurately and naturally."
            full_message = f"{system_prompt}\n\n{translation_request}"
            
            # Используем Gemini для перевода
            response = await asyncio.to_thread(
                self.gemini_model.generate_content,
                full_message
            )
            
            response_text = response.text.strip()
            logger.info(f"🤖 Gemini перевод ответ: {response_text[:150]}...")
            
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
            logger.warning(f"⚠️ Возвращаю оригинальные сцены без перевода")
            return scenes_result
    
    async def _translate_text(self, text: str) -> str:
        """
        Переводит текст на русский язык
        
        Args:
            text: Текст для перевода
            
        Returns:
            Переведенный текст
        """
        try:
            system_prompt = "You are a professional translator. Translate to Russian accurately."
            full_message = f"{system_prompt}\n\nTranslate to Russian: {text}"
            
            # Используем Gemini для перевода
            response = await asyncio.to_thread(
                self.gemini_model.generate_content,
                full_message
            )
            
            return response.text.strip()
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при переводе текста: {e}")
            return text

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
            logger.info(f"🎬 Сцена {scene_number}: Анализирую фото через Gemini Vision...")
            
            # Создаем промт для Gemini Vision
            vision_prompt = f"""You are a professional video director. Analyze this product/subject image and create an improved video prompt.

ORIGINAL PROMPT: {original_prompt}

Based on what you see in the image:
1. Describe the visual style, lighting, and composition
2. Suggest the best camera movement for a video
3. Create a dynamic video prompt that builds on this visual

Return ONLY the enhanced video prompt (2-3 sentences), nothing else."""

            # Используем Gemini с изображением
            image_content = [
                vision_prompt,
                {
                    "mime_type": "image/jpeg",
                    "data": image_url  # URL изображения
                }
            ]
            
            response = await asyncio.to_thread(
                self.gemini_model.generate_content,
                [vision_prompt, {"mime_type": "image/jpeg", "data": image_url}] if image_url.startswith('http') else vision_prompt
            )
            
            enhanced_prompt = response.text.strip()
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
        scene_number: int = 1
    ) -> Dict:
        """
        Генерирует одну сцену видео
        
        Args:
            prompt: Промт для видео
            model: Модель (kling, sora, veo)
            duration: Длительность в секундах
            aspect_ratio: Соотношение сторон
            start_image_url: URL начального фрейма (для связности)
            scene_number: Номер сцены для логирования
            
        Returns:
            Dict с результатом или ошибкой
        """
        try:
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
            
            # Добавляем специфичные параметры
            if model == "kling":
                input_params["negative_prompt"] = ""
                if start_image_url:
                    input_params["start_image"] = start_image_url
                    logger.info(f"   Используется start_image для связности")
            elif model == "veo":
                if start_image_url:
                    input_params["last_frame_url"] = start_image_url
                    logger.info(f"   Используется last_frame_url для связности")
            
            logger.info(f"🎬 Сцена {scene_number}: Отправляю запрос на Replicate API...")
            logger.info(f"   Model ID: {model_id}")
            
            # Используем синхронный replicate.run в потоке
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