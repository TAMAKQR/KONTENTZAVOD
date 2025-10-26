"""Утилиты для работы с изображениями"""
import asyncio
import logging
import aiohttp
import requests
from typing import Optional
from aiogram import Bot
from config import IMGBB_API_KEY

logger = logging.getLogger(__name__)


class ImageUploader:
    """Класс для загрузки изображений на облако"""
    
    def __init__(self, imgbb_api_key: str = IMGBB_API_KEY):
        self.imgbb_api_key = imgbb_api_key
        self.imgbb_url = "https://api.imgbb.com/1/upload"
    
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
                lambda: requests.post(self.imgbb_url, files=files, data=data, timeout=30)
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
        Скачивает фото с Telegram и загружает на ImgBB
        
        Args:
            bot: Aiogram Bot instance
            file_id: Telegram file_id
            photo_name: Имя фото для ImgBB
            
        Returns:
            Public URL изображения или None если ошибка
        """
        try:
            logger.info(f"📥 Скачиваю фото с Telegram...")
            photo_bytes = await self.download_telegram_photo(bot, file_id)
            
            if not photo_bytes:
                logger.error("❌ Не удалось скачать фото с Telegram")
                return None
            
            logger.info(f"☁️ Загружаю фото на ImgBB...")
            image_url = await self.upload_to_imgbb(photo_bytes, photo_name)
            
            if image_url:
                logger.info(f"✅ Фото готово: {image_url}")
                return image_url
            else:
                logger.error("❌ Не удалось загрузить фото на ImgBB")
                return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка при обработке фото: {e}")
            return None