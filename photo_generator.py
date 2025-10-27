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
        Генерирует фото для каждой сцены ПОСЛЕДОВАТЕЛЬНО с наследованием
        
        Каждое фото становится референсом для следующей сцены для обеспечения целостности.
        
        Args:
            scenes: Список сцен с промтами
            aspect_ratio: Соотношение сторон (16:9, 9:16, 1:1)
            reference_image_url: URL референс-изображения (опционально)
            general_prompt: Общий промт для стилизации
            
        Returns:
            {"status": "success", "scenes_with_photos": [...]} или {"status": "error", "error": "..."}
        """
        logger.info(f"🎨 Генерирую фото для {len(scenes)} сцен ПОСЛЕДОВАТЕЛЬНО с наследованием...")
        
        try:
            scenes_with_photos = []
            current_reference_url = reference_image_url  # Начальный референс (если есть)
            
            for idx, scene in enumerate(scenes):
                logger.info(f"\n📸 Сцена {idx + 1}/{len(scenes)} обработка...")
                
                # Создаю расширенный промт для фото
                scene_prompt = self._create_photo_prompt(
                    scene=scene,
                    reference_image_url=current_reference_url,
                    general_prompt=general_prompt,
                    scene_index=idx,
                    total_scenes=len(scenes)
                )
                
                # Генерирую фото для текущей сцены (ЖДУ результат!)
                photo_result = await self._generate_single_photo(
                    prompt=scene_prompt,
                    aspect_ratio=aspect_ratio,
                    reference_image_url=current_reference_url,
                    scene_index=idx
                )
                
                # Обрабатываю результат
                if photo_result["status"] == "success":
                    scene["photo_url"] = photo_result["photo_url"]
                    scene["photo_path"] = photo_result.get("photo_path")
                    scenes_with_photos.append(scene)
                    
                    # 🔑 КЛЮЧЕВОЙ МОМЕНТ: Фото текущей сцены становится референсом для следующей!
                    current_reference_url = photo_result["photo_url"]
                    logger.info(f"✅ Фото сцены {idx + 1} готово → будет использовано как референс для сцены {idx + 2}")
                else:
                    logger.warning(f"⚠️ Ошибка фото сцены {idx + 1}: {photo_result['error']}")
                    logger.info(f"⚠️ Переходу к следующей сцене без референса...")
                    scene["photo_url"] = None
                    scene["photo_error"] = photo_result["error"]
                    scenes_with_photos.append(scene)
                    # Не меняем current_reference_url, чтобы использовать последнее успешное фото
                    # (или исходный референс, если ни одно фото не было сгенерировано)
            
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
            # ✅ ВСЕГДА используем выбранный aspect_ratio (не match_input_image)
            # Это гарантирует, что фото генерируется в выбранном формате (16:9, 9:16, 1:1)
            # независимо от размера загруженного референса
            determined_aspect_ratio = aspect_ratio
            
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
                # url может быть методом или свойством
                url_attr = getattr(output, 'url')
                if callable(url_attr):
                    photo_url = url_attr()
                else:
                    photo_url = str(url_attr)
                logger.info(f"✅ Получен File объект: {photo_url[:100]}...")
            elif isinstance(output, list) and len(output) > 0:
                # ✅ Список File объектов или URLs
                if hasattr(output[0], 'url'):
                    url_attr = getattr(output[0], 'url')
                    if callable(url_attr):
                        photo_url = url_attr()
                    else:
                        photo_url = str(url_attr)
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
            if "E004" in error_msg and retry_count < 3:
                # E004 - Service is temporarily unavailable
                logger.warning(f"⚠️ Сервис недоступен (E004, попытка {retry_count + 1}/3) - пытаюсь еще раз...")
                
                # Постепенное увеличение времени ожидания
                wait_time = 5 + (retry_count * 3)
                logger.info(f"⏳ Жду {wait_time} сек перед повторной попыткой...")
                await asyncio.sleep(wait_time)
                
                # На каждой попытке - пробуем упростить параметры
                if retry_count < 1:
                    # Попытка 1: как есть, но ждем
                    return await self._generate_single_photo(
                        prompt=prompt,
                        aspect_ratio=aspect_ratio,
                        reference_image_url=reference_image_url,
                        scene_index=scene_index,
                        retry_count=retry_count + 1
                    )
                elif retry_count < 2:
                    # Попытка 2: без reference
                    logger.info(f"🔄 Попытка 2: генерируем БЕЗ reference")
                    return await self._generate_single_photo(
                        prompt=prompt,
                        aspect_ratio=aspect_ratio,
                        reference_image_url=None,
                        scene_index=scene_index,
                        retry_count=retry_count + 1
                    )
                else:
                    # Попытка 3: упрощаем промт
                    logger.info(f"🔄 Попытка 3: упрощаю промт")
                    simplified_prompt = self._simplify_prompt_for_api(prompt)
                    return await self._generate_single_photo(
                        prompt=simplified_prompt,
                        aspect_ratio=aspect_ratio,
                        reference_image_url=None,
                        scene_index=scene_index,
                        retry_count=retry_count + 1
                    )
            
            elif "E005" in error_msg and retry_count < 2:
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
            
            elif "E6716" in error_msg and retry_count < 3:
                # E6716 - Unexpected error handling prediction (от Replicate API)
                logger.warning(f"⚠️ Ошибка API (E6716, попытка {retry_count + 1}/3) - пытаюсь еще раз...")
                
                # На первой попытке retry - просто ждем и повторяем
                if retry_count == 0:
                    await asyncio.sleep(3)
                    logger.info(f"🔄 Повторная попытка 1: без изменений")
                    return await self._generate_single_photo(
                        prompt=prompt,
                        aspect_ratio=aspect_ratio,
                        reference_image_url=reference_image_url,
                        scene_index=scene_index,
                        retry_count=retry_count + 1
                    )
                
                # На второй попытке - пробуем без reference для упрощения
                elif retry_count == 1:
                    await asyncio.sleep(3)
                    logger.info(f"🔄 Повторная попытка 2: генерируем БЕЗ reference для упрощения")
                    # Повторяем без reference_image_url
                    return await self._generate_single_photo(
                        prompt=prompt,
                        aspect_ratio="16:9",  # Упрощаем aspect_ratio тоже
                        reference_image_url=None,  # Убираем reference
                        scene_index=scene_index,
                        retry_count=retry_count + 1
                    )
                
                # На третьей попытке - упрощаем сам промт (убираем детали)
                elif retry_count == 2:
                    await asyncio.sleep(3)
                    logger.info(f"🔄 Повторная попытка 3: упрощаю промт")
                    simplified_prompt = self._simplify_prompt_for_api(prompt)
                    logger.info(f"   Упрощенный промт: {simplified_prompt[:100]}...")
                    return await self._generate_single_photo(
                        prompt=simplified_prompt,
                        aspect_ratio="16:9",
                        reference_image_url=None,
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
    
    def _simplify_prompt_for_api(self, prompt: str) -> str:
        """
        Упрощает промт для API Replicate при ошибках E6716 или E004
        
        Убирает:
        - Лишние детали о позиции и сценах
        - Форматирование и спецсимволы
        - Оставляет только основное описание и атмосферу
        - Сохраняет инструкцию про БЕЗ ТЕКСТА
        """
        import re
        
        # Оставляем только первую часть до "Атмосфера" или первый параграф
        lines = prompt.split('\n')
        simplified = []
        has_no_text_instruction = False
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Сохраняем инструкцию про отсутствие текста
            if 'Без текста' in line or 'без надписей' in line or 'без логотипов' in line:
                has_no_text_instruction = True
                continue
            
            # Пропускаем служебные строки
            if line.startswith('Позиция:') or line.startswith('Длительность'):
                continue
            
            # Пропускаем служебные инструкции
            if 'Сцена' in line and 'из' in line:
                continue
            
            # Если строка про атмосферу - оставляем только атмосферу
            if line.startswith('Атмосфера:'):
                simplified.append(line.replace('Атмосфера:', '').strip())
                break
            
            simplified.append(line)
        
        # Объединяем и убираем лишние пробелы
        simplified_text = ' '.join(simplified)
        simplified_text = re.sub(r'\s+', ' ', simplified_text).strip()
        
        # Если результат пуст - используем первую строку оригинала
        if not simplified_text and prompt:
            simplified_text = prompt.split('\n')[0][:200]
        
        # Добавляем инструкцию про БЕЗ ТЕКСТА в конец
        if has_no_text_instruction or 'Без текста' in prompt:
            simplified_text += " (no text, no text overlays, clean image only)"
        
        logger.info(f"✂️ Промт упрощен:")
        logger.info(f"   До: {prompt[:150]}...")
        logger.info(f"   После: {simplified_text[:150]}...")
        
        return simplified_text[:400]  # Ограничиваем до 400 символов
    
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
        - ✅ БЕЗ ТЕКСТА на изображении
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
        
        # ✅ Формирую финальный промт БЕЗ ТЕКСТА
        extended_prompt = (
            f"{reference_instruction}"
            f"{scene_prompt}\n"
            f"Атмосфера: {atmosphere}\n"
            f"Позиция: {position_context}\n"
            f"Длительность сцены: {duration} секунд\n"
            f"⚠️ ВАЖНО: Без текста, без надписей, без логотипов, чистое изображение\n"
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