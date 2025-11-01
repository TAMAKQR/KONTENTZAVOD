"""
Пример использования Airtable логирования
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from integrations.airtable.airtable_logger import session_logger
from integrations.airtable.airtable_video_integration import log_video_start, log_video_complete
from integrations.airtable.airtable_animation_integration import log_animation_start, log_animation_complete
from integrations.airtable.airtable_photo_integration import log_photo_start, log_photo_complete
from integrations.airtable.airtable_photo_ai_integration import log_photo_ai_start, log_photo_ai_complete

async def example_video_logging():
    """Пример логирования видео"""
    print("🎥 Пример логирования видео...")
    
    # Начало сессии
    user_id = 123456
    session_id = "vid_001"
    
    success = await log_video_start(
        user_id=user_id,
        session_id=session_id,
        model="Kling",
        aspect_ratio="16:9",
        duration=5,
        prompt="Красивое небо с облаками на закате"
    )
    
    if success:
        print(f"✅ Сессия {session_id} начата")
    
    # Имитация работы
    await asyncio.sleep(2)
    
    # Завершение сессии
    success = await log_video_complete(
        session_id=session_id,
        status="Completed",
        output_url="https://example.com/video.mp4",
        processing_time=45.5
    )
    
    if success:
        print(f"✅ Сессия {session_id} завершена")

async def example_animation_logging():
    """Пример логирования анимации"""
    print("\n🎨 Пример логирования анимации...")
    
    user_id = 123456
    session_id = "anim_001"
    
    success = await log_animation_start(
        user_id=user_id,
        session_id=session_id,
        model="replicate",
        prompt="Оживи эту картину"
    )
    
    if success:
        print(f"✅ Анимация {session_id} начата")
    
    await asyncio.sleep(2)
    
    success = await log_animation_complete(
        session_id=session_id,
        status="Completed",
        output_url="https://example.com/animation.mp4",
        processing_time=30.0
    )
    
    if success:
        print(f"✅ Анимация {session_id} завершена")

async def example_photo_logging():
    """Пример логирования редактирования фото"""
    print("\n🖼️ Пример логирования редактирования фото...")
    
    user_id = 123456
    session_id = "photo_001"
    
    success = await log_photo_start(
        user_id=user_id,
        session_id=session_id,
        prompt="Размытие фона"
    )
    
    if success:
        print(f"✅ Редактирование фото {session_id} начато")
    
    await asyncio.sleep(2)
    
    success = await log_photo_complete(
        session_id=session_id,
        status="Completed",
        output_url="https://example.com/photo.jpg",
        processing_time=15.0
    )
    
    if success:
        print(f"✅ Редактирование фото {session_id} завершено")

async def example_photo_ai_logging():
    """Пример логирования AI фото"""
    print("\n✨ Пример логирования AI фото...")
    
    user_id = 123456
    session_id = "ai_photo_001"
    
    success = await log_photo_ai_start(
        user_id=user_id,
        session_id=session_id,
        model="gemini",
        prompt="Сделай фото более ярким"
    )
    
    if success:
        print(f"✅ AI обработка фото {session_id} начата")
    
    await asyncio.sleep(2)
    
    success = await log_photo_ai_complete(
        session_id=session_id,
        status="Completed",
        output_url="https://example.com/ai_photo.jpg",
        processing_time=20.0
    )
    
    if success:
        print(f"✅ AI обработка фото {session_id} завершена")

async def main():
    """Запуск примеров"""
    print("=" * 50)
    print("Примеры логирования Airtable")
    print("=" * 50)
    
    await example_video_logging()
    await example_animation_logging()
    await example_photo_logging()
    await example_photo_ai_logging()
    
    print("\n✨ Все примеры выполнены!")

if __name__ == "__main__":
    asyncio.run(main())
