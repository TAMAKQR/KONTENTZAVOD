"""Генератор видео через Replicate API"""
import asyncio
import json
import logging
from typing import Optional, List, Dict
import replicate
from replicate import Client
from config import REPLICATE_API_TOKEN, OPENAI_API_KEY
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class VideoGenerator:
    """Класс для генерации видео через Replicate API"""
    
    def __init__(self):
        self.replicate_token = REPLICATE_API_TOKEN
        self.replicate_client = Client(api_token=REPLICATE_API_TOKEN)
        self.openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        
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
        Улучшает промт через GPT-4 и разбивает на сцены
        
        Args:
            prompt: Оригинальный промт
            num_scenes: Количество сцен
            duration_per_scene: Длительность каждой сцены в секундах
            
        Returns:
            Dict с улучшенным промтом и сценами
        """
        try:
            system_message = f"""You are a professional video script writer. Analyze the user's prompt and break it down into exactly {num_scenes} connected scenes.

IMPORTANT: Return ONLY valid JSON, nothing else. No markdown, no explanations.

Return JSON with this exact structure:
{{
    "enhanced_prompt": "enhanced overall video description",
    "scenes": [
        {{
            "id": 1,
            "prompt": "detailed scene 1 prompt",
            "duration": {duration_per_scene},
            "atmosphere": "scene atmosphere"
        }}
    ]
}}

Rules:
- Each scene must flow smoothly to the next
- Each scene prompt must be 1-2 sentences, detailed and specific
- Duration: {duration_per_scene} seconds for all scenes
- Atmosphere: cinematic, dramatic, calm, energetic, etc
- Create exactly {num_scenes} scenes
- Scenes must connect logically and visually"""

            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": f"Create {num_scenes} connected video scenes from this prompt: {prompt}"}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            # Парсим JSON из ответа
            response_text = response.choices[0].message.content.strip()
            logger.info(f"📝 GPT ответ: {response_text[:200]}...")
            
            # Ищем JSON в ответе (может быть обернут в markdown)
            if "```json" in response_text:
                start_idx = response_text.find('{')
                end_idx = response_text.rfind('}') + 1
            elif "```" in response_text:
                start_idx = response_text.find('{')
                end_idx = response_text.rfind('}') + 1
            else:
                start_idx = response_text.find('{')
                end_idx = response_text.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                logger.error(f"❌ JSON не найден в ответе: {response_text}")
                raise ValueError("JSON not found in response")
            
            json_str = response_text[start_idx:end_idx]
            logger.info(f"🔍 Извлеченный JSON: {json_str[:100]}...")
            
            result = json.loads(json_str)
            
            # Валидация результата
            if "scenes" not in result:
                raise ValueError("'scenes' key not found in response")
            
            if not isinstance(result["scenes"], list):
                raise ValueError("'scenes' must be a list")
            
            if len(result["scenes"]) != num_scenes:
                logger.warning(f"⚠️ GPT создал {len(result['scenes'])} сцен вместо {num_scenes}")
            
            logger.info(f"✅ GPT улучшил промт, создано {len(result['scenes'])} сцен")
            
            # Переводим сцены на русский язык
            logger.info(f"🌍 Переводу сцены на русский язык...")
            result = await self._translate_scenes_to_russian(result)
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка при обработке GPT: {e}")
            logger.error(f"❌ Детали: {str(e)}")
            # Фоллбак - просто создаем сцены из оригинального промта
            logger.info(f"⚠️ Использую фоллбак: разделяю промт на {num_scenes} сцены")
            return {
                "enhanced_prompt": prompt,
                "scenes": [
                    {
                        "id": i + 1,
                        "prompt": f"{prompt} - Часть {i + 1}",
                        "duration": 5,
                        "atmosphere": "cinematic"
                    }
                    for i in range(num_scenes)
                ]
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
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a professional translator from English to Russian. Translate video scene descriptions accurately and naturally."},
                    {"role": "user", "content": translation_request}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            response_text = response.choices[0].message.content.strip()
            logger.info(f"🌍 GPT перевод ответ: {response_text[:150]}...")
            
            # Парсим переведенные сцены
            if "```json" in response_text:
                start_idx = response_text.find('{')
                end_idx = response_text.rfind('}') + 1
            elif "```" in response_text:
                start_idx = response_text.find('[')
                end_idx = response_text.rfind(']') + 1
                if start_idx == -1:
                    start_idx = response_text.find('{')
                    end_idx = response_text.rfind('}') + 1
            else:
                start_idx = response_text.find('[')
                end_idx = response_text.rfind(']') + 1
                if start_idx == -1:
                    start_idx = response_text.find('{')
                    end_idx = response_text.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                logger.warning(f"⚠️ Не удалось распарсить переведенные сцены, используем оригинальные")
                return scenes_result
            
            translated_text = response_text[start_idx:end_idx]
            translated_list = json.loads(translated_text)
            
            # Если это не список, преобразуем в список
            if not isinstance(translated_list, list):
                translated_list = [translated_list]
            
            # Применяем переводы к оригинальным сценам
            for i, scene in enumerate(scenes):
                if i < len(translated_list):
                    translated = translated_list[i]
                    if "prompt" in translated:
                        scene["prompt"] = translated["prompt"]
                    if "atmosphere" in translated:
                        scene["atmosphere"] = translated["atmosphere"]
            
            # Переводим enhanced_prompt если есть
            if "enhanced_prompt" in scenes_result:
                enhanced = scenes_result["enhanced_prompt"]
                enhanced_translation = await self._translate_text(enhanced)
                scenes_result["enhanced_prompt"] = enhanced_translation
            
            logger.info(f"✅ Сцены переведены на русский язык")
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
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a professional translator. Translate to Russian accurately."},
                    {"role": "user", "content": f"Translate to Russian: {text}"}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при переводе текста: {e}")
            return text

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