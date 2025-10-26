"""Обработчик для создания видео"""
import asyncio
import json
import logging
from aiogram import Router, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import StateFilter
from video_generator import VideoGenerator
from video_stitcher import VideoStitcher
from image_utils import ImageUploader

logger = logging.getLogger(__name__)
router = Router()


class VideoStates(StatesGroup):
    """Состояния для создания видео"""
    choosing_type = State()  # Выбор типа видео
    
    # Подпоток 1: Текст → Видео
    text_choosing_model = State()  # Выбор модели AI
    text_choosing_aspect_ratio = State()  # Выбор соотношения сторон
    text_waiting_prompt = State()  # Ввод промта
    text_processing_prompt = State()  # GPT обработка промта
    text_confirming_scenes = State()  # Подтверждение сцен
    text_editing_scene = State()  # Редактирование отдельной сцены
    text_generating = State()  # Генерация видео
    
    # Подпоток 2: Текст + Фото → Видео
    text_photo_choosing_model = State()  # Выбор модели AI
    text_photo_choosing_aspect_ratio = State()  # Выбор соотношения сторон
    text_photo_waiting_prompt = State()
    text_photo_waiting_photo = State()
    text_photo_confirming_scene_photo = State()  # Подтверждение фото для каждой сцены
    text_photo_generating = State()
    text_photo_editing_scene = State()  # Редактирование промта сцены
    text_photo_editing_scene_photo = State()  # Загрузка нового фото для сцены
    
    # Подпоток 3: Текст + Фото + AI → Видео
    text_photo_ai_choosing_model = State()  # Выбор модели (kling-v2.5-turbo-pro)
    text_photo_ai_choosing_aspect_ratio = State()  # Выбор соотношения сторон
    text_photo_ai_asking_reference = State()  # Вопрос о референсе
    text_photo_ai_waiting_reference = State()  # Загрузка референса
    text_photo_ai_waiting_prompt = State()  # Ввод промта
    text_photo_ai_processing_prompt = State()  # GPT разбивает на сцены
    text_photo_ai_generating_photos = State()  # Генерация фото через google/nano-banana
    text_photo_ai_confirming_scenes = State()  # Подтверждение сцен с фото
    text_photo_ai_editing_scene = State()  # Редактирование сцены
    text_photo_ai_generating = State()  # Генерация видео


@router.callback_query(lambda c: c.data == "video")
async def start_video_creation(callback: types.CallbackQuery, state: FSMContext):
    """Начало создания видео - выбор типа"""
    await callback.answer()
    await state.set_state(VideoStates.choosing_type)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Текст", callback_data="video_text")],
            [InlineKeyboardButton(text="📝 Текст + Фото", callback_data="video_text_photo")],
            [InlineKeyboardButton(text="📝 Текст + Фото + AI", callback_data="video_text_photo_ai")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]
        ]
    )
    
    await callback.message.answer(
        "📹 Создание видео\n\n"
        "Выбери режим генерации:",
        reply_markup=keyboard
    )


# ==================== ПОДПОТОК 1: ТЕКСТ → ВИДЕО ====================

@router.callback_query(lambda c: c.data == "video_text")
async def start_text_video(callback: types.CallbackQuery, state: FSMContext):
    """Режим 1: Только текст - выбор модели AI"""
    await callback.answer()
    await state.set_state(VideoStates.text_choosing_model)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎬 Kling v2.5 Turbo Pro", callback_data="model_kling_text")],
            [InlineKeyboardButton(text="🎞️ Sora 2", callback_data="model_sora_text")],
            [InlineKeyboardButton(text="🎥 Veo 3.1 Fast", callback_data="model_veo_text")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]
        ]
    )
    
    await callback.message.answer(
        "📝 Режим: Текст → Видео\n\n"
        "Выбери AI модель для генерации:",
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data.startswith("model_") and c.data.endswith("_text"))
async def choose_text_model(callback: types.CallbackQuery, state: FSMContext):
    """Выбор модели для режима Текст"""
    await callback.answer()
    
    model_map = {
        "model_kling_text": ("kling", "kwaivgi/kling-v2.5-turbo-pro"),
        "model_sora_text": ("sora", "openai/sora-2"),
        "model_veo_text": ("veo", "google/veo-3.1-fast")
    }
    
    model_key, model_full = model_map.get(callback.data, ("kling", "kwaivgi/kling-v2.5-turbo-pro"))
    await state.update_data(model_key=model_key, model=model_full)
    await state.set_state(VideoStates.text_choosing_aspect_ratio)
    
    model_names = {
        "kling": "🎬 Kling v2.5 Turbo Pro (5/10 сек)",
        "sora": "🎞️ Sora 2 (20 сек)",
        "veo": "🎥 Veo 3.1 Fast (5/10/15 сек)"
    }
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📺 16:9 (YouTube/Desktop)", callback_data="aspect_16_9_text")],
            [InlineKeyboardButton(text="📱 9:16 (TikTok/Shorts) ⭐", callback_data="aspect_9_16_text")],
            [InlineKeyboardButton(text="⬜ 1:1 (Instagram Feed)", callback_data="aspect_1_1_text")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]
        ]
    )
    
    await callback.message.answer(
        f"✅ Модель выбрана: {model_names.get(model_key, model_key)}\n"
        f"{'─' * 40}\n\n"
        f"📐 Выбери соотношение сторон:\n\n"
        f"  16:9 - Горизонтальное (YouTube, Desktop)\n"
        f"  9:16 - Вертикальное (TikTok, Instagram, YouTube Shorts)\n"
        f"  1:1  - Квадратное (Instagram Feed)\n",
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data.startswith("aspect_") and c.data.endswith("_text") and not c.data.endswith("_text_photo"))
async def choose_text_aspect_ratio(callback: types.CallbackQuery, state: FSMContext):
    """Выбор соотношения сторон для режима Текст"""
    await callback.answer()
    
    aspect_map = {
        "aspect_16_9_text": "16:9",
        "aspect_9_16_text": "9:16",
        "aspect_1_1_text": "1:1"
    }
    
    aspect_ratio = aspect_map.get(callback.data, "16:9")
    await state.update_data(aspect_ratio=aspect_ratio)
    await state.set_state(VideoStates.text_waiting_prompt)
    
    aspect_names = {
        "16:9": "📺 16:9 (Горизонтальное)",
        "9:16": "📱 9:16 (Вертикальное)",
        "1:1": "⬜ 1:1 (Квадратное)"
    }
    
    data = await state.get_data()
    model_key = data.get("model_key", "kling")
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]]
    )
    
    await callback.message.answer(
        f"✅ Параметры видео установлены:\n"
        f"{'═' * 40}\n\n"
        f"🎬 Модель: {model_key.upper()}\n"
        f"📐 Соотношение: {aspect_names.get(aspect_ratio, aspect_ratio)}\n\n"
        f"{'═' * 40}\n"
        f"📝 Теперь напиши описание видео:",
        reply_markup=keyboard
    )


def extract_num_scenes_from_prompt(prompt: str) -> int:
    """Извлекает количество сцен из промта пользователя"""
    import re
    
    patterns = [
        r'(\d+)\s*сцен',
        r'(\d+)\s*scene',
        r'на\s*(\d+)\s*сцен',
        r'разбить на\s*(\d+)',
        r'(\d+)\s*частей',
        r'split.*?(\d+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, prompt, re.IGNORECASE)
        if match:
            num = int(match.group(1))
            if 1 <= num <= 10:
                return num
    
    return 3


@router.message(VideoStates.text_waiting_prompt)
async def process_text_video_prompt(message: types.Message, state: FSMContext):
    """Обработка текста для видео - отправка на обработку GPT"""
    data = await state.get_data()
    model_key = data.get("model_key", "kling")
    
    await state.update_data(prompt=message.text)
    await state.set_state(VideoStates.text_processing_prompt)
    
    input_text = message.text
    indented_input = "\n".join("    " + line for line in input_text.split("\n"))
    
    num_scenes = extract_num_scenes_from_prompt(message.text)
    
    processing_msg = await message.answer(
        f"⏳ Обработка промта через GPT-4...\n"
        f"{'─' * 40}\n\n"
        f"📝 Ваш промт:\n\n{indented_input}\n\n"
        f"{'─' * 40}\n"
        f"🤖 Разбиваю на {num_scenes} сцены..."
    )
    
    try:
        generator = VideoGenerator()
        
        scenes_result = await generator.enhance_prompt_with_gpt(
            prompt=message.text,
            num_scenes=num_scenes
        )
        
        await state.update_data(
            scenes=scenes_result["scenes"],
            enhanced_prompt=scenes_result["enhanced_prompt"],
            current_scene_index=0
        )
        
        await state.set_state(VideoStates.text_confirming_scenes)
        
        await show_scene_for_confirmation(message, state, 0)
        
    except Exception as e:
        logger.error(f"❌ Ошибка обработки: {e}")
        await processing_msg.edit_text(
            f"❌ Ошибка при обработке: {str(e)}\n\n"
            f"Попробуй еще раз с /start"
        )
        await state.clear()


async def show_scene_for_confirmation(message: types.Message, state: FSMContext, scene_index: int):
    """Показывает сцену для подтверждения"""
    data = await state.get_data()
    scenes = data.get("scenes", [])
    
    if scene_index >= len(scenes):
        await start_video_generation(message, state)
        return
    
    scene = scenes[scene_index]
    
    prompt_text = scene['prompt']
    indented_prompt = "\n".join("    " + line for line in prompt_text.split("\n"))
    
    aspect_ratio = scene.get('aspect_ratio', data.get('aspect_ratio', '16:9'))
    
    scene_text = (
        f"🎬 Сцена {scene['id']} из {len(scenes)}\n"
        f"{'─' * 40}\n\n"
        f"📝 Промт:\n{indented_prompt}\n\n"
        f"⏱️  Длительность: {scene.get('duration', 5)} сек\n"
        f"🎨 Атмосфера: {scene.get('atmosphere', 'N/A')}\n"
        f"📐 Соотношение: {aspect_ratio}\n\n"
        f"{'─' * 40}\n"
        f"Что ты думаешь? ✅ Подтвердить или отредактировать?"
    )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Далее", callback_data=f"scene_approve_{scene_index}"),
                InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"scene_edit_{scene_index}")
            ],
            [
                InlineKeyboardButton(text="🔄 Регенерировать все", callback_data="scenes_regenerate_all"),
                InlineKeyboardButton(text="⬅️ Отмена", callback_data="back_to_menu")
            ]
        ]
    )
    
    await message.answer(scene_text, parse_mode="Markdown", reply_markup=keyboard)


@router.callback_query(lambda c: c.data.startswith("scene_approve_"))
async def approve_scene(callback: types.CallbackQuery, state: FSMContext):
    """Подтверждение сцены"""
    await callback.answer()
    
    scene_index = int(callback.data.replace("scene_approve_", ""))
    data = await state.get_data()
    scenes = data.get("scenes", [])
    
    next_index = scene_index + 1
    await state.update_data(current_scene_index=next_index)
    
    if next_index < len(scenes):
        await show_scene_for_confirmation(callback.message, state, next_index)
    else:
        await start_video_generation(callback.message, state)


@router.callback_query(lambda c: c.data.startswith("scene_edit_"))
async def edit_scene(callback: types.CallbackQuery, state: FSMContext):
    """Редактирование отдельной сцены"""
    await callback.answer()
    
    scene_index = int(callback.data.replace("scene_edit_", ""))
    await state.update_data(editing_scene_index=scene_index)
    await state.set_state(VideoStates.text_editing_scene)
    
    data = await state.get_data()
    scenes = data.get("scenes", [])
    scene = scenes[scene_index]
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Готово", callback_data=f"edit_scene_done_{scene_index}")],
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data="back_to_menu")]
        ]
    )
    
    await callback.message.answer(
        f"✏️ Редактирование сцены {scene_index + 1}\n\n"
        f"Текущий промт:\n{scene['prompt']}\n\n"
        f"Напиши новый промт или нажми Готово:",
        reply_markup=keyboard
    )


@router.message(VideoStates.text_editing_scene)
async def process_scene_edit(message: types.Message, state: FSMContext):
    """Обработка отредактированного промта сцены"""
    data = await state.get_data()
    scene_index = data.get("editing_scene_index", 0)
    scenes = data.get("scenes", [])
    
    if scene_index < len(scenes):
        scenes[scene_index]['prompt'] = message.text
        await state.update_data(scenes=scenes)
    
    await message.answer(f"✅ Сцена {scene_index + 1} обновлена!")
    await state.set_state(VideoStates.text_confirming_scenes)
    await show_scene_for_confirmation(message, state, scene_index)


@router.callback_query(lambda c: c.data.startswith("edit_scene_done_"))
async def edit_scene_done(callback: types.CallbackQuery, state: FSMContext):
    """Завершение редактирования сцены"""
    await callback.answer()
    
    scene_index = int(callback.data.replace("edit_scene_done_", ""))
    await state.set_state(VideoStates.text_confirming_scenes)
    await show_scene_for_confirmation(callback.message, state, scene_index)


@router.callback_query(lambda c: c.data == "scenes_regenerate_all")
async def regenerate_all_scenes(callback: types.CallbackQuery, state: FSMContext):
    """Регенерирование всех сцен"""
    await callback.answer()
    
    data = await state.get_data()
    prompt = data.get("prompt", "")
    
    await state.set_state(VideoStates.text_processing_prompt)
    
    processing_msg = await callback.message.answer("⏳ Регенерирую все сцены...")
    
    try:
        generator = VideoGenerator()
        num_scenes = extract_num_scenes_from_prompt(prompt)
        
        scenes_result = await generator.enhance_prompt_with_gpt(
            prompt=prompt,
            num_scenes=num_scenes
        )
        
        await state.update_data(
            scenes=scenes_result["scenes"],
            enhanced_prompt=scenes_result["enhanced_prompt"],
            current_scene_index=0
        )
        
        await state.set_state(VideoStates.text_confirming_scenes)
        await processing_msg.delete()
        await show_scene_for_confirmation(callback.message, state, 0)
        
    except Exception as e:
        logger.error(f"❌ Ошибка регенерации: {e}")
        await processing_msg.edit_text(f"❌ Ошибка: {str(e)}")


async def start_video_generation(message: types.Message, state: FSMContext):
    """Начинает генерацию видео всех сцен"""
    await state.set_state(VideoStates.text_generating)
    
    data = await state.get_data()
    scenes = data.get("scenes", [])
    model_key = data.get("model_key", "kling")
    aspect_ratio = data.get("aspect_ratio", "16:9")
    
    for scene in scenes:
        scene["aspect_ratio"] = aspect_ratio
    
    time_estimate = 6
    
    scenes_list = "\n".join([f"  {i+1}. {s['prompt'][:50].strip()}..." for i, s in enumerate(scenes)])
    
    generating_msg = await message.answer(
        f"🎬 Начинаю генерацию видео!\n"
        f"{'═' * 40}\n\n"
        f"📊 Сцен: {len(scenes)}\n"
        f"🤖 Модель: {model_key.upper()}\n"
        f"📐 Соотношение: {aspect_ratio}\n"
        f"⏳ Время: примерно {time_estimate}-{time_estimate + 2} минут\n\n"
        f"{'─' * 40}\n"
        f"🎯 Сцены для генерации:\n\n{scenes_list}\n\n"
        f"{'─' * 40}\n"
        f"⚡ Генерирую сцены ПАРАЛЛЕЛЬНО (очень быстро!)..."
    )
    
    try:
        generator = VideoGenerator()
        stitcher = VideoStitcher()
        
        logger.info(f"🎬 Генерирую {len(scenes)} сцен ПАРАЛЛЕЛЬНО через {model_key}...")
        await generating_msg.edit_text(
            f"🎬 Генерирую видео ПАРАЛЛЕЛЬНО\n"
            f"{'═' * 40}\n\n"
            f"📊 Сцен: {len(scenes)}\n"
            f"🤖 Модель: {model_key.upper()}\n"
            f"📐 Соотношение: {aspect_ratio}\n\n"
            f"{'─' * 40}\n"
            f"⏳ Отправляю {len(scenes)} запросов на Replicate API...\n"
            f"⚡ Все сцены генерируются одновременно!\n"
            f"Это займет примерно 5-7 минут..."
        )
        
        scene_results = await generator.generate_multiple_scenes(
            scenes=scenes,
            model=model_key,
            start_image_url=None
        )
        
        logger.info(f"✅ Параллельная генерация завершена: {len(scene_results)} результатов")
        
        failed_scenes = [r for r in scene_results if r.get("status") == "error"]
        success_scenes = [r for r in scene_results if r.get("status") == "success"]
        
        logger.info(f"📊 Результаты: {len(success_scenes)} успешно, {len(failed_scenes)} ошибок")
        
        if failed_scenes:
            error_msgs = [f"Сцена {r.get('scene_number', '?')}: {r.get('error', 'Unknown')}" for r in failed_scenes]
            raise Exception(f"Не удалось сгенерировать {len(failed_scenes)} сцен:\n" + "\n".join(error_msgs))
        
        await generating_msg.edit_text(
            "📥 Скачиваю видео сцен...\n\n"
            "⏳ Это займет 1-2 минуты..."
        )
        
        video_paths = []
        download_tasks = []
        
        for i, result in enumerate(scene_results):
            if result.get("status") == "success":
                video_url = result.get("video_url")
                if not video_url:
                    logger.warning(f"⚠️ Сцена {i+1}: URL пуст")
                    continue
                
                logger.info(f"📥 Сцена {i+1}: Начинаю скачивание с {video_url[:60]}...")
                
                task = stitcher.download_video(
                    video_url,
                    f"scene_{i + 1}.mp4"
                )
                download_tasks.append((i + 1, task))
        
        if download_tasks:
            logger.info(f"⚡ Скачиваю {len(download_tasks)} видео параллельно...")
            results = await asyncio.gather(
                *[task for _, task in download_tasks],
                return_exceptions=True
            )
            
            for (scene_num, _), result in zip(download_tasks, results):
                if isinstance(result, Exception):
                    logger.error(f"❌ Сцена {scene_num}: Ошибка скачивания: {result}")
                elif result:
                    video_paths.append(result)
                    logger.info(f"✅ Сцена {scene_num}: Видео скачано в {result}")
                else:
                    logger.warning(f"⚠️ Сцена {scene_num}: Скачивание вернуло None")
        
        logger.info(f"📊 Скачано видео: {len(video_paths)}/{len(scene_results)}")
        
        if not video_paths:
            raise Exception(f"Не удалось скачать ни одного видео из {len(scene_results)} сцен")
        
        await generating_msg.edit_text(
            "🎬 Объединяю видео с плавными переходами...\n\n"
            "⏳ Это займет пару минут..."
        )
        
        final_video_path = await stitcher.stitch_videos(
            video_paths,
            output_filename="final_video.mp4",
            use_transitions=True
        )
        
        if not final_video_path:
            raise Exception("Не удалось объединить видео")
        
        await generating_msg.delete()
        await message.answer_video(
            types.FSInputFile(final_video_path),
            caption="✅ Видео готово!\n\n🎬 С плавными переходами 0.5 сек"
        )
        
        await stitcher.cleanup_temp_files()
        logger.info("✅ Генерация завершена успешно")
        
    except Exception as e:
        logger.error(f"❌ Ошибка генерации: {e}")
        await generating_msg.edit_text(
            f"❌ Ошибка при генерации видео:\n\n`{str(e)}`\n\n"
            f"Попробуй еще раз с /start",
            parse_mode="Markdown"
        )
    
    finally:
        await state.clear()


# ==================== ПОДПОТОК 2: ТЕКСТ + ФОТО → ВИДЕО ====================

@router.callback_query(lambda c: c.data == "video_text_photo")
async def start_text_photo_video(callback: types.CallbackQuery, state: FSMContext):
    """Режим 2: Текст + Фото - выбор модели AI"""
    await callback.answer()
    await state.set_state(VideoStates.text_photo_choosing_model)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎬 Kling v2.5 Turbo Pro", callback_data="model_kling_text_photo")],
            [InlineKeyboardButton(text="🎞️ Sora 2", callback_data="model_sora_text_photo")],
            [InlineKeyboardButton(text="🎥 Veo 3.1 Fast", callback_data="model_veo_text_photo")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]
        ]
    )
    
    await callback.message.answer(
        "📝🖼️ Режим: Текст + Фото → Видео\n\n"
        "Выбери AI модель для генерации:",
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data.startswith("model_") and c.data.endswith("_text_photo"))
async def choose_text_photo_model(callback: types.CallbackQuery, state: FSMContext):
    """Выбор модели для режима Текст+Фото"""
    await callback.answer()
    
    model_map = {
        "model_kling_text_photo": ("kling", "kwaivgi/kling-v2.5-turbo-pro"),
        "model_sora_text_photo": ("sora", "openai/sora-2"),
        "model_veo_text_photo": ("veo", "google/veo-3.1-fast")
    }
    
    model_key, model_full = model_map.get(callback.data, ("kling", "kwaivgi/kling-v2.5-turbo-pro"))
    await state.update_data(model_key=model_key, model=model_full)
    await state.set_state(VideoStates.text_photo_choosing_aspect_ratio)
    
    model_names = {
        "kling": "🎬 Kling v2.5 Turbo Pro (5/10 сек)",
        "sora": "🎞️ Sora 2 (20 сек)",
        "veo": "🎥 Veo 3.1 Fast (5/10/15 сек)"
    }
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📺 16:9 (YouTube/Desktop)", callback_data="aspect_16_9_text_photo")],
            [InlineKeyboardButton(text="📱 9:16 (TikTok/Shorts) ⭐", callback_data="aspect_9_16_text_photo")],
            [InlineKeyboardButton(text="⬜ 1:1 (Instagram Feed)", callback_data="aspect_1_1_text_photo")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]
        ]
    )
    
    await callback.message.answer(
        f"✅ Модель выбрана: {model_names.get(model_key, model_key)}\n"
        f"{'─' * 40}\n\n"
        f"📐 Выбери соотношение сторон:\n\n"
        f"  16:9 - Горизонтальное (YouTube, Desktop)\n"
        f"  9:16 - Вертикальное (TikTok, Instagram, YouTube Shorts)\n"
        f"  1:1  - Квадратное (Instagram Feed)\n",
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data.startswith("aspect_") and c.data.endswith("_text_photo"))
async def choose_text_photo_aspect_ratio(callback: types.CallbackQuery, state: FSMContext):
    """Выбор соотношения сторон для режима Текст+Фото"""
    await callback.answer()
    
    aspect_map = {
        "aspect_16_9_text_photo": "16:9",
        "aspect_9_16_text_photo": "9:16",
        "aspect_1_1_text_photo": "1:1"
    }
    
    aspect_ratio = aspect_map.get(callback.data, "16:9")
    await state.update_data(aspect_ratio=aspect_ratio)
    await state.set_state(VideoStates.text_photo_waiting_prompt)
    
    aspect_names = {
        "16:9": "📺 16:9 (Горизонтальное)",
        "9:16": "📱 9:16 (Вертикальное)",
        "1:1": "⬜ 1:1 (Квадратное)"
    }
    
    data = await state.get_data()
    model_key = data.get("model_key", "kling")
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]]
    )
    
    await callback.message.answer(
        f"✅ Параметры видео установлены:\n"
        f"{'═' * 40}\n\n"
        f"🎬 Модель: {model_key.upper()}\n"
        f"📐 Соотношение: {aspect_names.get(aspect_ratio, aspect_ratio)}\n\n"
        f"{'═' * 40}\n"
        f"📝 Теперь напиши описание видео:",
        reply_markup=keyboard
    )


@router.message(VideoStates.text_photo_waiting_prompt)
async def process_text_photo_prompt(message: types.Message, state: FSMContext):
    """Обработка текста для видео (Текст+Фото режим)"""
    data = await state.get_data()
    model_key = data.get("model_key", "kling")
    
    await state.update_data(prompt=message.text)
    await state.set_state(VideoStates.text_processing_prompt)
    
    input_text = message.text
    indented_input = "\n".join("    " + line for line in input_text.split("\n"))
    
    num_scenes = extract_num_scenes_from_prompt(message.text)
    
    processing_msg = await message.answer(
        f"⏳ Обработка промта через GPT-4...\n"
        f"{'─' * 40}\n\n"
        f"📝 Ваш промт:\n\n{indented_input}\n\n"
        f"{'─' * 40}\n"
        f"🤖 Разбиваю на {num_scenes} сцены..."
    )
    
    try:
        generator = VideoGenerator()
        
        scenes_result = await generator.enhance_prompt_with_gpt(
            prompt=message.text,
            num_scenes=num_scenes
        )
        
        await state.update_data(
            scenes=scenes_result["scenes"],
            enhanced_prompt=scenes_result["enhanced_prompt"],
            current_scene_index=0,
            scene_photos={}
        )
        
        await state.set_state(VideoStates.text_photo_confirming_scene_photo)
        await show_text_photo_scene_for_photo(message, state, 0)
        
    except Exception as e:
        logger.error(f"❌ Ошибка обработки: {e}")
        await processing_msg.edit_text(
            f"❌ Ошибка при обработке: {str(e)}\n\n"
            f"Попробуй еще раз с /start"
        )
        await state.clear()


async def show_text_photo_scene_for_photo(message: types.Message, state: FSMContext, scene_index: int):
    """Показывает сцену и просит загрузить для неё фото"""
    data = await state.get_data()
    scenes = data.get("scenes", [])
    
    if scene_index >= len(scenes):
        await start_text_photo_video_generation(message, state)
        return
    
    scene = scenes[scene_index]
    
    prompt_text = scene['prompt']
    indented_prompt = "\n".join("    " + line for line in prompt_text.split("\n"))
    
    aspect_ratio = scene.get('aspect_ratio', data.get('aspect_ratio', '16:9'))
    
    scene_text = (
        f"📸 Сцена {scene['id']} из {len(scenes)}\n"
        f"{'─' * 40}\n\n"
        f"📝 Промт:\n{indented_prompt}\n\n"
        f"⏱️  Длительность: {scene.get('duration', 5)} сек\n"
        f"🎨 Атмосфера: {scene.get('atmosphere', 'N/A')}\n"
        f"📐 Соотношение: {aspect_ratio}\n\n"
        f"{'─' * 40}\n"
        f"📸 Загрузи фото для этой сцены (JPG/PNG):"
    )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data="back_to_menu")]
        ]
    )
    
    await message.answer(scene_text, parse_mode="Markdown", reply_markup=keyboard)
    
    await state.update_data(current_scene_index=scene_index)
    await state.set_state(VideoStates.text_photo_confirming_scene_photo)


@router.message(VideoStates.text_photo_confirming_scene_photo)
async def process_text_photo_scene_photo(message: types.Message, state: FSMContext):
    """Обработка загруженного фото для сцены"""
    if message.photo:
        data = await state.get_data()
        scene_index = data.get("current_scene_index", 0)
        scenes = data.get("scenes", [])
        
        try:
            uploader = ImageUploader()
            image_url = await uploader.process_telegram_photo(
                message.bot,
                message.photo[-1].file_id,
                photo_name=f"scene_{scene_index + 1}"
            )
            
            if image_url:
                scene_photos = data.get("scene_photos", {})
                scene_photos[scene_index] = image_url
                
                await state.update_data(scene_photos=scene_photos)
                
                logger.info(f"✅ Фото сцены {scene_index + 1} загружено: {image_url}")
                
                await message.answer(f"✅ Фото для сцены {scene_index + 1} загружено!")
                await show_text_photo_scene_for_photo(message, state, scene_index + 1)
                return
            else:
                await message.answer("❌ Ошибка при загрузке фото. Попробуй еще раз.")
                return
                
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки фото: {e}")
            await message.answer(f"❌ Ошибка: {str(e)}\n\nПопробуй еще раз или напиши /отмена")
            return
    
    if message.text and message.text.lower() in ["/отмена", "отмена"]:
        await message.answer("❌ Отменено")
        await state.clear()
        return
    
    await message.answer("❌ Отправь фото для этой сцены или напиши /отмена")


async def start_text_photo_video_generation(message: types.Message, state: FSMContext):
    """Начинает генерацию видео для режима Текст+Фото"""
    await state.set_state(VideoStates.text_photo_generating)
    
    data = await state.get_data()
    scenes = data.get("scenes", [])
    model_key = data.get("model_key", "kling")
    aspect_ratio = data.get("aspect_ratio", "16:9")
    scene_photos = data.get("scene_photos", {})
    
    for scene in scenes:
        scene["aspect_ratio"] = aspect_ratio
    
    time_estimate = 6
    
    scenes_list = "\n".join([f"  {i+1}. {s['prompt'][:50].strip()}..." for i, s in enumerate(scenes)])
    
    generating_msg = await message.answer(
        f"🎬 Начинаю генерацию видео с фото!\n"
        f"{'═' * 40}\n\n"
        f"📊 Сцен: {len(scenes)}\n"
        f"📸 Фото: {len(scene_photos)}\n"
        f"🤖 Модель: {model_key.upper()}\n"
        f"📐 Соотношение: {aspect_ratio}\n"
        f"⏳ Время: примерно {time_estimate}-{time_estimate + 2} минут\n\n"
        f"{'─' * 40}\n"
        f"🎯 Сцены для генерации:\n\n{scenes_list}\n\n"
        f"{'─' * 40}\n"
        f"⚡ Генерирую видео для каждой сцены с её фото..."
    )
    
    try:
        generator = VideoGenerator()
        stitcher = VideoStitcher()
        
        logger.info(f"🎬 Генерирую {len(scenes)} сцен ПАРАЛЛЕЛЬНО через {model_key}...")
        await generating_msg.edit_text(
            f"🎬 Генерирую видео ПАРАЛЛЕЛЬНО\n"
            f"{'═' * 40}\n\n"
            f"📊 Сцен: {len(scenes)}\n"
            f"📸 Фото: {len(scene_photos)}\n"
            f"🤖 Модель: {model_key.upper()}\n"
            f"📐 Соотношение: {aspect_ratio}\n\n"
            f"{'─' * 40}\n"
            f"⏳ Отправляю {len(scenes)} запросов на Replicate API...\n"
            f"⚡ Все сцены генерируются одновременно!\n"
            f"Это займет примерно 5-7 минут..."
        )
        
        # Генерируем видео с фото для каждой сцены ПАРАЛЛЕЛЬНО
        # Преобразуем словарь scene_photos в список в правильном порядке
        scene_image_urls = []
        for i in range(len(scenes)):
            if i in scene_photos:
                scene_image_urls.append(scene_photos[i])
        
        scene_results = await generator.generate_multiple_scenes(
            scenes=scenes,
            model=model_key,
            scene_image_urls=scene_image_urls if scene_image_urls else None
        )
        
        logger.info(f"✅ Параллельная генерация завершена: {len(scene_results)} результатов")
        
        failed_scenes = [r for r in scene_results if r.get("status") == "error"]
        success_scenes = [r for r in scene_results if r.get("status") == "success"]
        
        logger.info(f"📊 Результаты: {len(success_scenes)} успешно, {len(failed_scenes)} ошибок")
        
        if failed_scenes:
            error_msgs = [f"Сцена {r.get('scene_number', '?')}: {r.get('error', 'Unknown')}" for r in failed_scenes]
            raise Exception(f"Не удалось сгенерировать {len(failed_scenes)} сцен:\n" + "\n".join(error_msgs))
        
        await generating_msg.edit_text(
            "📥 Скачиваю видео сцен...\n\n"
            "⏳ Это займет 1-2 минуты..."
        )
        
        video_paths = []
        download_tasks = []
        
        for i, result in enumerate(scene_results):
            if result.get("status") == "success":
                video_url = result.get("video_url")
                if not video_url:
                    logger.warning(f"⚠️ Сцена {i+1}: URL пуст")
                    continue
                
                logger.info(f"📥 Сцена {i+1}: Начинаю скачивание с {video_url[:60]}...")
                
                task = stitcher.download_video(
                    video_url,
                    f"scene_{i + 1}.mp4"
                )
                download_tasks.append((i + 1, task))
        
        if download_tasks:
            logger.info(f"⚡ Скачиваю {len(download_tasks)} видео параллельно...")
            results = await asyncio.gather(
                *[task for _, task in download_tasks],
                return_exceptions=True
            )
            
            for (scene_num, _), result in zip(download_tasks, results):
                if isinstance(result, Exception):
                    logger.error(f"❌ Сцена {scene_num}: Ошибка скачивания: {result}")
                elif result:
                    video_paths.append(result)
                    logger.info(f"✅ Сцена {scene_num}: Видео скачано в {result}")
                else:
                    logger.warning(f"⚠️ Сцена {scene_num}: Скачивание вернуло None")
        
        logger.info(f"📊 Скачано видео: {len(video_paths)}/{len(scene_results)}")
        
        if not video_paths:
            raise Exception(f"Не удалось скачать ни одного видео из {len(scene_results)} сцен")
        
        await generating_msg.edit_text(
            "🎬 Объединяю видео с плавными переходами...\n\n"
            "⏳ Это займет пару минут..."
        )
        
        final_video_path = await stitcher.stitch_videos(
            video_paths,
            output_filename="final_video.mp4",
            use_transitions=True
        )
        
        if not final_video_path:
            raise Exception("Не удалось объединить видео")
        
        await generating_msg.delete()
        await message.answer_video(
            types.FSInputFile(final_video_path),
            caption="✅ Видео готово!\n\n🎬 С плавными переходами 0.5 сек"
        )
        
        await stitcher.cleanup_temp_files()
        logger.info("✅ Генерация завершена успешно")
        
    except Exception as e:
        logger.error(f"❌ Ошибка генерации: {e}")
        await generating_msg.edit_text(
            f"❌ Ошибка при генерации видео:\n\n`{str(e)}`\n\n"
            f"Попробуй еще раз с /start",
            parse_mode="Markdown"
        )
    
    finally:
        await state.clear()

# ==================== ПОДПОТОК 3: ТЕКСТ + ФОТО + AI → ВИДЕО ====================
# Обработчики находятся в photo_ai_handler.py
