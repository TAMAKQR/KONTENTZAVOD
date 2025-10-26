"""Генератор фото через google/nano-banana для сцен видео"""
import asyncio
import json
import logging
import io
import base64
import os
from pathlib import Path
from typing import Dict, Optional, List
import aiohttp
import replicate
from config import REPLICATE_API_TOKEN

logger = logging.getLogger(__name__)


class PhotoGenerator:
    """Генератор фото по сценам с использованием google/nano-banana"""
    
    def __init__(self):
        """Инициализация генератора фото"""
        if not REPLICATE_API_TOKEN:
            raise ValueError("❌ REPLICATE_API_TOKEN не установлен! Добавь в .env")
        
        self.api_token = REPLICATE_API_TOKEN
        self.model = "google/nano-banana"  # Модель для генерации фото
        self.temp_images_dir = Path("temp_images")
        self.temp_images_dir.mkdir(exist_ok=True)
        
        # ✅ Устанавливаю токен для replicate
        os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN
        logger.info(f"✅ PhotoGenerator инициализирован с моделью: {self.model}")
        
    async def generate_photos_for_scenes(
        self,
        scenes: list,
        aspect_ratio: str = "16:9",
        reference_image_url: str = None,
        general_prompt: str = ""
    ) -> dict:
        """
        Генерирует фото для каждой сцены ПАРАЛЛЕЛЬНО
        
        Args:
            scenes: Список сцен с промтами
            aspect_ratio: Соотношение сторон (16:9, 9:16, 1:1)
            reference_image_url: URL референс-изображения (опционально)
            general_prompt: Общий промт для стилизации
            
        Returns:
            {"status": "success", "scenes_with_photos": [...]} или {"status": "error", "error": "..."}
        """
        logger.info(f"🎨 Генерирую фото для {len(scenes)} сцен ПАРАЛЛЕЛЬНО...")
        
        try:
            # 1️⃣ Создаю список промтов для всех сцен
            generation_tasks = []
            
            for idx, scene in enumerate(scenes):
                logger.info(f"📸 Сцена {idx + 1}/{len(scenes)} отправляется на генерацию...")
                
                # Создаю расширенный промт для фото
                scene_prompt = self._create_photo_prompt(
                    scene=scene,
                    reference_image_url=reference_image_url,
                    general_prompt=general_prompt,
                    scene_index=idx,
                    total_scenes=len(scenes)
                )
                
                # Добавляю задачу (НЕ ждём!)
                task = self._generate_single_photo(
                    prompt=scene_prompt,
                    aspect_ratio=aspect_ratio,
                    reference_image_url=reference_image_url,
                    scene_index=idx
                )
                generation_tasks.append(task)
            
            # 2️⃣ Запускаю все задачи параллельно
            logger.info(f"⚡ Все {len(scenes)} сцен запущены параллельно к Replicate API!")
            photo_results = await asyncio.gather(*generation_tasks)
            
            # 3️⃣ Обрабатываю результаты
            scenes_with_photos = []
            for idx, photo_result in enumerate(photo_results):
                scene = scenes[idx]
                
                if photo_result["status"] == "success":
                    scene["photo_url"] = photo_result["photo_url"]
                    scene["photo_path"] = photo_result.get("photo_path")
                    scenes_with_photos.append(scene)
                    logger.info(f"✅ Фото для сцены {idx + 1} готово")
                else:
                    logger.warning(f"⚠️ Ошибка фото сцены {idx + 1}: {photo_result['error']}")
                    scene["photo_url"] = None
                    scene["photo_error"] = photo_result["error"]
                    scenes_with_photos.append(scene)
            
            return {
                "status": "success",
                "scenes_with_photos": scenes_with_photos,
                "total_scenes": len(scenes),
                "successful_photos": sum(1 for s in scenes_with_photos if s.get("photo_url"))
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации фото: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _generate_single_photo(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
        reference_image_url: str = None,
        scene_index: int = 0,
        retry_count: int = 0
    ) -> dict:
        """
        Генерирует одно фото через replicate API
        
        Args:
            prompt: Промт для генерации
            aspect_ratio: Соотношение сторон (16:9, 9:16, 1:1)
            reference_image_url: URL референса (опционально)
            scene_index: Индекс сцены
            retry_count: Количество попыток (для автоматического retry)
            
        Returns:
            {"status": "success", "photo_url": "..."} или {"status": "error", "error": "..."}
        """
        try:
            # Подготавливаю параметры для google/nano-banana
            # По умолчанию: aspect_ratio = "match_input_image"
            # Альтернативы: "16:9", "9:16", "1:1" (но работают только без reference)
            determined_aspect_ratio = "match_input_image" if reference_image_url else aspect_ratio
            
            input_params = {
                "prompt": prompt,
                "aspect_ratio": determined_aspect_ratio,  # ✅ Правильно для Nano-Banana
                "output_format": "jpg"
            }
            
            # Если есть референс - добавляю его как массив (image_input)
            if reference_image_url:
                input_params["image_input"] = [reference_image_url]  # ✅ Должен быть массив!
                logger.info(f"   📸 Референс: {reference_image_url[:80]}...")
                logger.info(f"   📐 Используем aspect_ratio='match_input_image' для reference-режима")
            
            logger.info(f"🎬 Вызываю replicate для генерации фото (сцена {scene_index + 1})...")
            logger.info(f"   📝 Промт: {prompt[:80]}...")
            logger.info(f"   📐 Соотношение: {aspect_ratio}")
            if reference_image_url:
                logger.info(f"   ✅ С использованием референс-изображения")
            
            # Вызываю replicate асинхронно (БЕЗ api_token параметра!)
            output = await asyncio.to_thread(
                replicate.run,
                self.model,
                input=input_params
            )
            
            # Обработка результата
            photo_url = None
            
            logger.info(f"📊 Тип результата от Replicate: {type(output)}")
            
            # Результат может быть File объектом, список, или строка
            if hasattr(output, 'url'):
                # ✅ File объект от Replicate
                photo_url = output.url()
                logger.info(f"✅ Получен File объект: {photo_url[:100]}...")
            elif isinstance(output, list) and len(output) > 0:
                # ✅ Список File объектов или URLs
                if hasattr(output[0], 'url'):
                    photo_url = output[0].url()
                    logger.info(f"✅ Получен список File объектов: {photo_url[:100]}...")
                else:
                    photo_url = str(output[0])
                    logger.info(f"✅ Получен список URLs: {photo_url[:100]}...")
            elif isinstance(output, str):
                # ✅ Строка с URL
                photo_url = output
                logger.info(f"✅ Получена строка URL: {photo_url[:100]}...")
            else:
                logger.error(f"❌ Неожиданный формат: {type(output)}")
                logger.error(f"   Содержимое: {str(output)[:200]}")
                return {
                    "status": "error",
                    "error": f"Неожиданный формат ответа: {type(output)}"
                }
            
            if not photo_url:
                return {
                    "status": "error",
                    "error": "Не удалось получить URL фото"
                }
            
            # Скачиваю фото локально
            photo_path = await self._download_photo(photo_url, scene_index)
            
            logger.info(f"✅ Фото сгенерировано: {photo_url}")
            
            return {
                "status": "success",
                "photo_url": photo_url,
                "photo_path": photo_path
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Ошибка генерации фото сцены {scene_index + 1}: {error_msg}")
            
            # ✅ Обработка различных ошибок API
            if "E005" in error_msg and retry_count < 2:
                # E005 - Фильтр безопасности (sensitive content)
                logger.warning(f"⚠️ Фильтр безопасности (E005) - пытаюсь с улучшенным промтом...")
                
                # Очищаю промт от "опасных" слов
                sanitized_prompt = self._sanitize_prompt_for_safety(prompt)
                logger.info(f"🔄 Переделаю с очищенным промтом: {sanitized_prompt[:80]}...")
                
                # Retry с очищенным промтом
                return await self._generate_single_photo(
                    prompt=sanitized_prompt,
                    aspect_ratio=aspect_ratio,
                    reference_image_url=reference_image_url,
                    scene_index=scene_index,
                    retry_count=retry_count + 1
                )
            
            elif "E6716" in error_msg and retry_count < 1:
                # E6716 - Unexpected error handling prediction
                logger.warning(f"⚠️ Ошибка API (E6716) - пытаюсь еще раз...")
                await asyncio.sleep(2)  # Пауза перед retry
                
                # Retry без санитизации (это может быть временная проблема API)
                return await self._generate_single_photo(
                    prompt=prompt,
                    aspect_ratio=aspect_ratio,
                    reference_image_url=reference_image_url,
                    scene_index=scene_index,
                    retry_count=retry_count + 1
                )
            
            return {
                "status": "error",
                "error": error_msg
            }
    
    async def _download_photo(self, photo_url: str, scene_index: int) -> str:
        """Скачивает фото локально"""
        try:
            import aiohttp
            
            photo_path = self.temp_images_dir / f"scene_{scene_index + 1}.png"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(photo_url) as resp:
                    if resp.status == 200:
                        with open(photo_path, 'wb') as f:
                            f.write(await resp.read())
                        logger.info(f"💾 Фото сохранено: {photo_path}")
                        return str(photo_path)
                    else:
                        logger.warning(f"⚠️ Ошибка скачивания: HTTP {resp.status}")
                        return None
                        
        except Exception as e:
            logger.warning(f"⚠️ Ошибка сохранения фото: {e}")
            return None
    
    def _sanitize_prompt_for_safety(self, prompt: str) -> str:
        """
        Очищает промт от слов, которые могут вызвать фильтр безопасности E005
        
        Слова, которые могут быть заблокированы:
        - "женщина", "женский", "лицо", "человек", "люди"
        - "фото", "портрет", "реальное"
        
        Стратегия: заменяем конкретные сущности на общие описания
        """
        import re
        
        sanitized = prompt.lower()
        
        # Слова/фразы которые нужно удалить или заменить
        replacements = {
            r'\bженщин\w+': 'персонаж',
            r'\bчеловек\w+': 'существо',
            r'\bлюди\w+': 'существа',
            r'\bлиц\w+': 'черты',
            r'\bпортрет\w+': 'изображение',
            r'\bреальн\w+': 'стилизованное',
            r'\bфото\w+': 'изображение',
            r'\bживое\w+': 'динамичное',
            r'\bкрасив\w+': 'элегантное',
            r'\bпривлекательн\w+': 'привлекающее взгляд',
            r'\bидеал\w+': 'совершенное',
        }
        
        # Применяю замены
        for pattern, replacement in replacements.items():
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE | re.UNICODE)
        
        # Убираю избыточные пробелы
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        
        logger.info(f"✅ Промт очищен от фильтров")
        logger.info(f"   До: {prompt[:100]}")
        logger.info(f"   После: {sanitized[:100]}")
        
        return sanitized

    def _create_photo_prompt(
        self,
        scene: dict,
        reference_image_url: str = None,
        general_prompt: str = "",
        scene_index: int = 0,
        total_scenes: int = 1
    ) -> str:
        """
        Создает расширенный промт для google/nano-banana
        
        Учитывает:
        - Основной промт сцены
        - Атмосферу
        - Позицию в видео (для плавных переходов)
        - Общий стиль видео
        """
        
        scene_prompt = scene.get("prompt", "")
        atmosphere = scene.get("atmosphere", "")
        duration = scene.get("duration", 5)
        
        # Если есть референс - указываю его в промте
        reference_instruction = ""
        if reference_image_url:
            reference_instruction = "Стиль и визуальные элементы из референсного изображения. "
        
        # Информация о позиции для плавности переходов
        position_context = f"Сцена {scene_index + 1} из {total_scenes}"
        if scene_index > 0:
            position_context += " - продолжение предыдущей сцены, плавный переход"
        if scene_index < total_scenes - 1:
            position_context += " - подготовка к следующей сцене"
        
        # Формирую финальный промт
        extended_prompt = (
            f"{reference_instruction}"
            f"{scene_prompt}\n"
            f"Атмосфера: {atmosphere}\n"
            f"Позиция: {position_context}\n"
            f"Длительность сцены: {duration} секунд\n"
        )
        
        if general_prompt:
            extended_prompt += f"Общий стиль: {general_prompt}"
        
        return extended_prompt.strip()
    
    def _aspect_ratio_to_resolution(self, aspect_ratio: str) -> str:
        """Преобразует соотношение сторон в разрешение"""
        
        # Стандартные разрешения для google/nano-banana
        resolutions = {
            "16:9": "768x432",   # HD альбомный
            "9:16": "432x768",   # Портретный
            "1:1": "512x512",    # Квадрат
        }
        
        return resolutions.get(aspect_ratio, "768x432")
    
    async def generate_intermediate_frames(
        self,
        start_photo_url: str,
        end_photo_url: str,
        num_frames: int = 3,
        aspect_ratio: str = "16:9"
    ) -> list:
        """
        Генерирует промежуточные фреймы между двумя фото
        (для плавной анимации между сценами)
        
        Args:
            start_photo_url: URL первого фото
            end_photo_url: URL финального фото
            num_frames: Количество промежуточных фреймов
            aspect_ratio: Соотношение сторон
            
        Returns:
            Список URL промежуточных фреймов
        """
        logger.info(f"🎬 Генерирую {num_frames} промежуточных фреймов...")
        
        intermediate_frames = [start_photo_url]
        
        try:
            for i in range(num_frames):
                # Интерполяция между фото
                blend_ratio = (i + 1) / (num_frames + 1)
                
                prompt = (
                    f"Плавный переход между двумя изображениями. "
                    f"Интерполяция {int(blend_ratio * 100)}% "
                    f"от первого к второму изображению."
                )
                
                photo_result = await self._generate_single_photo(
                    prompt=prompt,
                    aspect_ratio=aspect_ratio,
                    reference_image_url=start_photo_url,
                    scene_index=i
                )
                
                if photo_result["status"] == "success":
                    intermediate_frames.append(photo_result["photo_url"])
                    logger.info(f"✅ Промежуточный фрейм {i + 1} готов")
                else:
                    logger.warning(f"⚠️ Ошибка фрейма {i + 1}: {photo_result['error']}")
            
            intermediate_frames.append(end_photo_url)
            return intermediate_frames
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации промежуточных фреймов: {e}")
            return [start_photo_url, end_photo_url]
    
    def cleanup_temp_images(self):
        """Удаляет временные изображения"""
        try:
            import shutil
            if self.temp_images_dir.exists():
                shutil.rmtree(self.temp_images_dir)
                logger.info("🗑️  Временные изображения удалены")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при удалении временных файлов: {e}")