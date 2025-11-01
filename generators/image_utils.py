"""Утилиты для работы с изображениями"""
import asyncio
import logging
import sys
from pathlib import Path
import aiohttp
import requests
import replicate
from typing import Optional, Dict, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from aiogram import Bot
from PIL import Image
import io
from src.config import IMGBB_API_KEY, REPLICATE_API_TOKEN

logger = logging.getLogger(__name__)


class ImageUploader:
    """Класс для загрузки изображений на облако"""
    
    # Минимальные требования к фото
    MIN_WIDTH = 512
    MIN_HEIGHT = 512
    RECOMMENDED_WIDTH = 1280
    RECOMMENDED_HEIGHT = 720
    MAX_FILE_SIZE_MB = 10
    
    # Поддерживаемые соотношения сторон
    SUPPORTED_RATIOS = {
        "16:9": (16, 9),
        "9:16": (9, 16),
        "1:1": (1, 1)
    }
    
    def __init__(self, imgbb_api_key: str = IMGBB_API_KEY, replicate_token: str = REPLICATE_API_TOKEN):
        self.imgbb_api_key = imgbb_api_key
        self.imgbb_url = "https://api.imgbb.com/1/upload"
        self.replicate_token = replicate_token
        
        # Инициализируем Replicate клиент
        if self.replicate_token:
            replicate.api_token = self.replicate_token
    
    async def download_telegram_photo(self, bot: Bot, file_id: str) -> Optional[bytes]:
        """
        Скачивает фото с Telegram сервера
        
        Args:
            bot: Aiogram Bot instance
            file_id: Telegram file_id
            
        Returns:
            Bytes фото или None если ошибка
        """
        try:
            file = await bot.get_file(file_id)
            file_path = file.file_path
            
            # Скачиваем файл
            async with aiohttp.ClientSession() as session:
                url = f"https://api.telegram.org/file/bot{bot.token}/{file_path}"
                async with session.get(url) as response:
                    if response.status == 200:
                        photo_bytes = await response.read()
                        logger.info(f"✅ Фото скачано с Telegram ({len(photo_bytes)} bytes)")
                        return photo_bytes
                    else:
                        logger.error(f"❌ Ошибка скачивания фото: статус {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"❌ Ошибка при скачивании фото с Telegram: {e}")
            return None
    
    def validate_photo_quality(self, image_bytes: bytes) -> Dict[str, any]:
        """
        Проверяет качество фото перед загрузкой
        
        Args:
            image_bytes: Bytes изображения
            
        Returns:
            {
                "valid": bool,
                "width": int,
                "height": int,
                "file_size_mb": float,
                "aspect_ratio": str,
                "errors": list,
                "warnings": list
            }
        """
        errors = []
        warnings = []
        
        try:
            # Открываем изображение
            image = Image.open(io.BytesIO(image_bytes))
            width, height = image.size
            file_size_mb = len(image_bytes) / (1024 * 1024)
            
            logger.info(f"📊 Анализ фото: {width}x{height}px, {file_size_mb:.2f}MB")
            
            # ❌ КРИТИЧЕСКИЕ ОШИБКИ (отклонение)
            if width < self.MIN_WIDTH or height < self.MIN_HEIGHT:
                errors.append(
                    f"❌ Фото слишком маленькое ({width}x{height}px)\n"
                    f"   Минимум: {self.MIN_WIDTH}x{self.MIN_HEIGHT}px"
                )
            
            if file_size_mb > self.MAX_FILE_SIZE_MB:
                errors.append(
                    f"❌ Файл слишком большой ({file_size_mb:.1f}MB)\n"
                    f"   Максимум: {self.MAX_FILE_SIZE_MB}MB"
                )
            
            # ⚠️ ПРЕДУПРЕЖДЕНИЯ (принимаем, но предупреждаем)
            if width < self.RECOMMENDED_WIDTH or height < self.RECOMMENDED_HEIGHT:
                warnings.append(
                    f"⚠️ Фото меньше рекомендуемого ({width}x{height}px)\n"
                    f"   Рекомендуется: {self.RECOMMENDED_WIDTH}x{self.RECOMMENDED_HEIGHT}px или больше"
                )
            
            # Проверка соотношения сторон
            aspect_ratio = self._calculate_aspect_ratio(width, height)
            
            if aspect_ratio not in ["16:9", "9:16", "1:1"]:
                warnings.append(
                    f"⚠️ Нестандартное соотношение сторон: {aspect_ratio}\n"
                    f"   Рекомендуется: 16:9 (горизонтальное), 9:16 (вертикальное), 1:1 (квадрат)"
                )
            
            # Telegram сжатие
            if width == 1280 or height == 1280:
                warnings.append(
                    "💡 Фото сжато Telegram'ом до 1280px\n"
                    "   Для лучшего качества отправляй фото как ДОКУМЕНТ (без сжатия)"
                )
            
            return {
                "valid": len(errors) == 0,
                "width": width,
                "height": height,
                "file_size_mb": round(file_size_mb, 2),
                "aspect_ratio": aspect_ratio,
                "errors": errors,
                "warnings": warnings
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка валидации фото: {e}")
            return {
                "valid": False,
                "errors": [f"❌ Не удалось прочитать изображение: {str(e)}"],
                "warnings": []
            }
    
    def _calculate_aspect_ratio(self, width: int, height: int) -> str:
        """Вычисляет соотношение сторон изображения"""
        from math import gcd
        
        divisor = gcd(width, height)
        ratio_w = width // divisor
        ratio_h = height // divisor
        
        # Проверяем близость к стандартным соотношениям (с погрешностью 5%)
        for ratio_name, (std_w, std_h) in self.SUPPORTED_RATIOS.items():
            if abs(ratio_w / ratio_h - std_w / std_h) < 0.05:
                return ratio_name
        
        return f"{ratio_w}:{ratio_h}"
    
    async def upload_to_replicate(self, image_bytes: bytes) -> Optional[str]:
        """
        Загружает изображение через Replicate File API
        
        Args:
            image_bytes: Bytes изображения
            
        Returns:
            URL файла на Replicate или None если ошибка
        """
        if not self.replicate_token:
            logger.error("❌ REPLICATE_API_TOKEN не установлен")
            return None
        
        try:
            import io
            
            # Создаем file-like объект из bytes
            file_obj = io.BytesIO(image_bytes)
            file_obj.name = "image.jpg"
            
            # Загружаем через Replicate Files API
            loop = asyncio.get_event_loop()
            file_response = await loop.run_in_executor(
                None,
                lambda: replicate.files.create(file_obj)
            )
            
            # Получаем URL загруженного файла (правильный метод)
            file_url = file_response.urls.get("get")  # Метод get() требует ключ "get"
            logger.info(f"✅ Изображение загружено на Replicate: {file_url}")
            return file_url
            
        except Exception as e:
            logger.error(f"❌ Ошибка при загрузке на Replicate: {e}")
            return None
    
    async def upload_to_imgbb(self, image_bytes: bytes, image_name: str = "photo") -> Optional[str]:
        """
        Загружает изображение на ImgBB и возвращает URL
        
        Args:
            image_bytes: Bytes изображения
            image_name: Имя изображения
            
        Returns:
            URL изображения на ImgBB или None если ошибка
        """
        if not self.imgbb_api_key:
            logger.error("❌ IMGBB_API_KEY не установлен в .env")
            return None
        
        try:
            files = {
                'image': (f'{image_name}.jpg', image_bytes, 'image/jpeg')
            }
            data = {
                'key': self.imgbb_api_key,
                'name': image_name
            }
            
            # Синхронный запрос через loop.run_in_executor
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(self.imgbb_url, files=files, data=data, timeout=60)  # ⏱️ Увеличен timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    image_url = result["data"]["url"]
                    logger.info(f"✅ Изображение загружено на ImgBB: {image_url}")
                    return image_url
                else:
                    logger.error(f"❌ ImgBB ошибка: {result.get('error', {}).get('message', 'Unknown')}")
                    return None
            else:
                logger.error(f"❌ Ошибка загрузки на ImgBB: статус {response.status_code}")
                logger.error(f"   Ответ: {response.text[:200]}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка при загрузке на ImgBB: {e}")
            return None
    
    async def process_telegram_photo(self, bot: Bot, file_id: str, photo_name: str = "photo") -> Optional[str]:
        """
        Скачивает фото с Telegram и загружает на Replicate (или ImgBB как fallback)
        
        Args:
            bot: Aiogram Bot instance
            file_id: Telegram file_id
            photo_name: Имя фото для ImgBB (используется только при fallback)
            
        Returns:
            Public URL изображения или None если ошибка
        """
        try:
            logger.info(f"📥 Скачиваю фото с Telegram...")
            photo_bytes = await self.download_telegram_photo(bot, file_id)
            
            if not photo_bytes:
                logger.error("❌ Не удалось скачать фото с Telegram")
                return None
            
            # 🎯 ПРИОРИТЕТ 1: Replicate File API (надежнее и быстрее)
            logger.info(f"☁️ Загружаю фото на Replicate...")
            replicate_url = await self.upload_to_replicate(photo_bytes)
            
            if replicate_url:
                logger.info(f"✅ Фото загружено на Replicate: {replicate_url}")
                return replicate_url
            
            # 🔄 FALLBACK: ImgBB (если Replicate не сработал)
            logger.warning("⚠️ Replicate недоступен, пробую ImgBB как fallback...")
            logger.info(f"☁️ Загружаю фото на ImgBB...")
            imgbb_url = await self.upload_to_imgbb(photo_bytes, photo_name)
            
            if imgbb_url:
                logger.info(f"✅ Фото загружено на ImgBB: {imgbb_url}")
                return imgbb_url
            else:
                logger.error("❌ Не удалось загрузить фото ни на Replicate, ни на ImgBB")
                return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка при обработке фото: {e}")
            return None