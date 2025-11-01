"""
Debug видео логирования
"""
import asyncio
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s - %(message)s')

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from integrations.airtable.airtable_video_integration import log_video_start, log_video_complete

async def main():
    print("🎥 Debug видео логирования...\n")
    
    user_id = 123456
    session_id = "debug_vid_001"
    
    print("1️⃣ Логирование начала видео...")
    success = await log_video_start(
        user_id=user_id,
        session_id=session_id,
        model="Kling",
        aspect_ratio="16:9",
        duration=5,
        prompt="Тестовое видео"
    )
    
    if success:
        print(f"✅ Начало залогировано\n")
    
    await asyncio.sleep(1)
    
    print("2️⃣ Логирование завершения видео...")
    success = await log_video_complete(
        session_id=session_id,
        status="Completed",
        output_url="https://example.com/video.mp4",
        processing_time=45.5
    )
    
    if success:
        print(f"✅ Завершение залогировано")
    else:
        print(f"❌ Ошибка при логировании завершения")

if __name__ == "__main__":
    asyncio.run(main())
