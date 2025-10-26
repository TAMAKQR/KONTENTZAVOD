"""Объединение видео с плавными переходами"""
import asyncio
import logging
from typing import List, Optional
from pathlib import Path
import requests
from moviepy.editor import (
    VideoFileClip, concatenate_videoclips, CompositeVideoClip,
    vfx, CompositeAudioClip
)
from PIL import Image
import io

logger = logging.getLogger(__name__)


class VideoStitcher:
    """Класс для объединения видео с плавными переходами"""
    
    # Параметры плавного перехода
    TRANSITION_DURATION = 0.5  # 0.5 секунды
    TRANSITION_TYPE = "cross_fade"  # cross_fade или dissolve
    
    def __init__(self, temp_dir: str = "temp_videos", output_dir: str = "output_videos"):
        self.temp_dir = Path(temp_dir)
        self.output_dir = Path(output_dir)
        
        # Создаем директории если не существуют
        self.temp_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)

    async def download_video(self, url: str, filename: str) -> Optional[str]:
        """
        Скачивает видео по URL
        
        Args:
            url: URL видео
            filename: Имя файла
            
        Returns:
            Путь к скачанному файлу или None
        """
        try:
            filepath = self.temp_dir / filename
            
            logger.info(f"📥 Начинаю скачивание: {filename}")
            logger.info(f"   URL: {url[:80]}...")
            
            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()
            
            # Получаем размер файла
            total_size = int(response.headers.get('content-length', 0))
            logger.info(f"   Размер: {total_size / (1024*1024):.2f} MB")
            
            downloaded = 0
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size:
                            progress = (downloaded / total_size) * 100
                            if int(progress) % 20 == 0:  # Логируем каждые 20%
                                logger.info(f"   Прогресс: {progress:.1f}%")
            
            file_size = filepath.stat().st_size
            logger.info(f"✅ Видео скачано: {filename} ({file_size / (1024*1024):.2f} MB)")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"❌ Ошибка скачивания видео {filename}")
            logger.error(f"   Ошибка: {str(e)}")
            logger.error(f"   Тип: {type(e).__name__}")
            return None

    async def extract_last_frame(self, video_path: str) -> Optional[str]:
        """
        Извлекает последний фрейм из видео
        
        Args:
            video_path: Путь к видео
            
        Returns:
            Путь к фрейму или None
        """
        try:
            video = VideoFileClip(video_path)
            last_frame = video.get_frame(video.duration - 0.1)  # Почти последний кадр
            
            # Сохраняем фрейм
            frame_path = self.temp_dir / f"frame_{Path(video_path).stem}.jpg"
            Image.fromarray((last_frame * 255).astype('uint8')).save(frame_path)
            
            video.close()
            logger.info(f"✅ Фрейм извлечен: {frame_path.name}")
            return str(frame_path)
            
        except Exception as e:
            logger.error(f"❌ Ошибка извлечения фрейма: {e}")
            return None

    async def extract_first_frame(self, video_path: str) -> Optional[str]:
        """
        Извлекает первый фрейм из видео
        
        Args:
            video_path: Путь к видео
            
        Returns:
            Путь к фрейму или None
        """
        try:
            video = VideoFileClip(video_path)
            first_frame = video.get_frame(0.1)
            
            frame_path = self.temp_dir / f"first_frame_{Path(video_path).stem}.jpg"
            Image.fromarray((first_frame * 255).astype('uint8')).save(frame_path)
            
            video.close()
            logger.info(f"✅ Первый фрейм извлечен: {frame_path.name}")
            return str(frame_path)
            
        except Exception as e:
            logger.error(f"❌ Ошибка извлечения первого фрейма: {e}")
            return None

    async def create_cross_fade_transition(
        self,
        clip1: VideoFileClip,
        clip2: VideoFileClip,
        duration: float = 0.5
    ) -> CompositeVideoClip:
        """
        Создает переход между двумя видео (cross-fade)
        
        Args:
            clip1: Первое видео
            clip2: Второе видео
            duration: Длительность перехода в секундах
            
        Returns:
            Композитное видео с переходом
        """
        # Длительность перекрытия
        overlap_duration = duration
        
        # Первое видео播放 полностью, но последние 'overlap_duration' секунд будут с фейдом
        clip1_faded = clip1.set_opacity(1).fx(vfx.fadeout, overlap_duration)
        
        # Второе видео начинается раньше, чем заканчивается первое
        clip2_faded = clip2.set_opacity(0).fx(vfx.fadein, overlap_duration)
        clip2_delayed = clip2_faded.set_start(clip1.duration - overlap_duration)
        
        # Создаем композит
        final_clip = CompositeVideoClip(
            [clip1_faded, clip2_delayed],
            size=clip1.size
        )
        
        return final_clip

    async def stitch_videos(
        self,
        video_paths: List[str],
        output_filename: str = "final_video.mp4",
        use_transitions: bool = True,
        fps: int = 30
    ) -> Optional[str]:
        """
        Объединяет несколько видео с плавными переходами
        
        Args:
            video_paths: Список путей к видео
            output_filename: Имя выходного файла
            use_transitions: Использовать ли переходы
            fps: FPS выходного видео
            
        Returns:
            Путь к объединенному видео или None
        """
        try:
            if not video_paths:
                logger.error("❌ Список видео пуст!")
                return None
            
            logger.info(f"🎬 Начинаю объединение {len(video_paths)} видео...")
            for i, path in enumerate(video_paths, 1):
                logger.info(f"   {i}. {Path(path).name}")
            
            # Загружаем видео
            clips = []
            total_duration = 0
            
            for i, path in enumerate(video_paths):
                try:
                    logger.info(f"📽️ Загружаю видео {i+1}: {Path(path).name}...")
                    clip = VideoFileClip(path)
                    duration = clip.duration
                    total_duration += duration
                    clips.append(clip)
                    logger.info(f"   ✅ Загружено: {duration:.2f} сек")
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось загрузить {Path(path).name}: {e}")
                    continue
            
            if not clips:
                logger.error("❌ Не удалось загрузить ни одного видео!")
                return None
            
            logger.info(f"✅ Загружено {len(clips)} видео (всего: {total_duration:.2f} сек)")
            
            # Объединяем с переходами
            if use_transitions and len(clips) > 1:
                logger.info(f"🎨 Применяю cross-fade переходы (0.5 сек)...")
                final_clips = [clips[0]]
                
                for i in range(1, len(clips)):
                    logger.info(f"   Переход {i}: {clips[i-1].duration:.2f}s → {clips[i].duration:.2f}s")
                    # Создаем переход между видео
                    transition = await self.create_cross_fade_transition(
                        clips[i - 1],
                        clips[i],
                        self.TRANSITION_DURATION
                    )
                    
                    # Добавляем второе видео после перехода
                    final_clips.append(clips[i])
                
                # Объединяем с плавными переходами
                logger.info(f"🔗 Объединяю видео с переходами...")
                final_video = concatenate_videoclips(final_clips, method="compose")
            else:
                # Просто объединяем без переходов
                logger.info(f"🔗 Объединяю видео без переходов...")
                final_video = concatenate_videoclips(clips, method="chain")
            
            # Устанавливаем FPS
            final_video = final_video.set_fps(fps)
            final_duration = final_video.duration
            logger.info(f"✅ Итоговое видео: {final_duration:.2f} сек ({fps} FPS)")
            
            # Сохраняем
            output_path = self.output_dir / output_filename
            logger.info(f"💾 Кодирую видео в {output_path}...")
            logger.info(f"   Кодек: libx264, Аудио: aac")
            
            # Кодируем видео (может занять время)
            loop = asyncio.get_event_loop()
            try:
                await loop.run_in_executor(
                    None,
                    lambda: final_video.write_videofile(
                        str(output_path),
                        verbose=False,
                        logger=None,
                        fps=fps,
                        codec='libx264',
                        audio_codec='aac',
                        temp_audiofile='temp-audio.m4a',
                        remove_temp=True
                    )
                )
            except Exception as encode_error:
                logger.error(f"❌ Ошибка кодирования: {encode_error}")
                raise
            
            # Закрываем клипы
            for clip in clips:
                clip.close()
            final_video.close()
            
            file_size = output_path.stat().st_size if output_path.exists() else 0
            logger.info(f"✅ Видео готово: {output_path}")
            logger.info(f"   Размер: {file_size / (1024*1024):.2f} MB")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"❌ Ошибка объединения видео!")
            logger.error(f"   Ошибка: {str(e)}")
            logger.error(f"   Тип: {type(e).__name__}")
            import traceback
            logger.error(f"   Traceback: {traceback.format_exc()}")
            return None

    async def cleanup_temp_files(self):
        """Удаляет временные файлы"""
        try:
            for file in self.temp_dir.glob("*"):
                file.unlink()
            logger.info("✅ Временные файлы удалены")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при удалении временных файлов: {e}")