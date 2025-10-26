"""Обработчик для потока Текст + Фото + AI → Видео"""
import asyncio
import json
import logging
from aiogram import Router, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import StateFilter
from video_generator import VideoGenerator
from photo_generator import PhotoGenerator
from video_stitcher import VideoStitcher
from image_utils import ImageUploader

logger = logging.getLogger(__name__)
router = Router()


class PhotoAIStates(StatesGroup):
    """Состояния для создания видео Текст + Фото + AI"""
    choosing_model = State()  # Выбор модели (только kling)
    choosing_aspect_ratio = State()  # Выбор соотношения сторон
    asking_reference = State()  # Вопрос о референсе
    waiting_reference = State()  # Загрузка референса
    waiting_prompt = State()  # Ввод промта
    processing_prompt = State()  # GPT обработка промта
    confirming_scenes = State()  # Подтверждение сцен
    editing_scene = State()  # Редактирование сцены
    generating_photos = State()  # Генерация фото
    confirming_photos = State()  # Подтверждение фото
    generating_video = State()  # Финальная генерация видео


@router.callback_query(lambda c: c.data == "video_text_photo_ai")
async def start_text_photo_ai_video(callback: types.CallbackQuery, state: FSMContext):
    """Начало потока Текст + Фото + AI"""
    await callback.answer()
    await state.set_state(PhotoAIStates.choosing_model)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎬 Kling v2.5 Turbo Pro ⭐", callback_data="photo_ai_model_kling")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]
        ]
    )
    
    await callback.message.answer(
        "📝🖼️🤖 Режим: Текст + Фото + AI → Видео\n\n"
        "Система автоматически:\n"
        "1️⃣ Разбивает промт на сцены\n"
        "2️⃣ Генерирует фото для каждой сцены (google/nano-banana)\n"
        "3️⃣ Создает видео на основе фото (Kling v2.5)\n\n"
        "🎬 Выбери модель видео:",
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data.startswith("photo_ai_model_"))
async def choose_photo_ai_model(callback: types.CallbackQuery, state: FSMContext):
    """Выбор модели для потока Текст + Фото + AI"""
    await callback.answer()
    
    # Для этого потока используем только kling
    await state.update_data(
        model="kwaivgi/kling-v2.5-turbo-pro",
        model_key="kling"
    )
    await state.set_state(PhotoAIStates.choosing_aspect_ratio)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📺 16:9 (YouTube/Desktop)", callback_data="photo_ai_aspect_16_9")],
            [InlineKeyboardButton(text="📱 9:16 (TikTok/Shorts) ⭐", callback_data="photo_ai_aspect_9_16")],
            [InlineKeyboardButton(text="⬜ 1:1 (Instagram Feed)", callback_data="photo_ai_aspect_1_1")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]
        ]
    )
    
    await callback.message.answer(
        "✅ Модель: 🎬 Kling v2.5 Turbo Pro\n"
        "{'─' * 40}\n\n"
        "📐 Выбери соотношение сторон для фото и видео:",
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data.startswith("photo_ai_aspect_"))
async def choose_photo_ai_aspect_ratio(callback: types.CallbackQuery, state: FSMContext):
    """Выбор соотношения сторон"""
    await callback.answer()
    
    aspect_map = {
        "photo_ai_aspect_16_9": "16:9",
        "photo_ai_aspect_9_16": "9:16",
        "photo_ai_aspect_1_1": "1:1"
    }
    
    aspect_ratio = aspect_map.get(callback.data, "16:9")
    await state.update_data(aspect_ratio=aspect_ratio)
    await state.set_state(PhotoAIStates.asking_reference)
    
    aspect_names = {
        "16:9": "📺 16:9 (Горизонтальное)",
        "9:16": "📱 9:16 (Вертикальное)",
        "1:1": "⬜ 1:1 (Квадратное)"
    }
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ По референсу", callback_data="photo_ai_with_reference"),
                InlineKeyboardButton(text="❌ Без референса", callback_data="photo_ai_without_reference")
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]
        ]
    )
    
    await callback.message.answer(
        f"✅ Соотношение сторон: {aspect_names.get(aspect_ratio, aspect_ratio)}\n"
        f"{'─' * 40}\n\n"
        f"🎨 Использовать ли референс-изображение?\n\n"
        f"✅ По референсу - загружаешь изображение, AI генерирует фото в похожем стиле\n"
        f"❌ Без референса - AI сама генерирует фото по описанию",
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data == "photo_ai_with_reference")
async def ask_for_reference(callback: types.CallbackQuery, state: FSMContext):
    """Запрос на загрузку референса"""
    await callback.answer()
    await state.update_data(use_reference=True)
    await state.set_state(PhotoAIStates.waiting_reference)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Отмена", callback_data="back_to_menu")]]
    )
    
    await callback.message.answer(
        "📸 Загрузи референс-изображение\n\n"
        "Это может быть:\n"
        "• Картина или фото в желаемом стиле\n"
        "• Скриншот из фильма\n"
        "• Любое изображение, которое задает атмосферу\n\n"
        "Google/Nano-Banana будет генерировать фото в похожем стиле для каждой сцены.",
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data == "photo_ai_without_reference")
async def skip_reference(callback: types.CallbackQuery, state: FSMContext):
    """Пропуск референса"""
    await callback.answer()
    await state.update_data(use_reference=False, reference_url=None)
    await state.set_state(PhotoAIStates.waiting_prompt)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Отмена", callback_data="back_to_menu")]]
    )
    
    await callback.message.answer(
        "✅ Режим без референса\n\n"
        "📝 Теперь напиши описание видео, которое ты хочешь создать.\n\n"
        "Советы:\n"
        "• Опиши основную идею, сюжет или концепцию\n"
        "• Указывай сцены явно (например: '3 сцены') для большего контроля\n"
        "• Опиши атмосферу, стиль, цветовую палитру",
        reply_markup=keyboard
    )


@router.message(PhotoAIStates.waiting_reference)
async def process_reference_image(message: types.Message, state: FSMContext):
    """Обработка загруженного референса"""
    if message.photo:
        try:
            uploader = ImageUploader()
            reference_url = await uploader.process_telegram_photo(
                message.bot,
                message.photo[-1].file_id,
                photo_name="reference"
            )
            
            if reference_url:
                await state.update_data(reference_url=reference_url)
                await state.set_state(PhotoAIStates.waiting_prompt)
                
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="⬅️ Отмена", callback_data="back_to_menu")]]
                )
                
                await message.answer(
                    "✅ Референс загружен!\n\n"
                    "📝 Теперь напиши описание видео",
                    reply_markup=keyboard
                )
            else:
                await message.answer("❌ Ошибка при обработке изображения")
                
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            await message.answer(f"❌ Ошибка: {str(e)[:100]}")
    else:
        await message.answer("❌ Отправь фото!")


@router.message(PhotoAIStates.waiting_prompt)
async def process_prompt(message: types.Message, state: FSMContext):
    """Обработка промта и разбиение на сцены"""
    data = await state.get_data()
    
    await state.update_data(prompt=message.text)
    await state.set_state(PhotoAIStates.processing_prompt)
    
    input_text = message.text
    indented_input = "\n".join("    " + line for line in input_text.split("\n"))
    
    # Извлекаю количество сцен
    num_scenes = _extract_num_scenes_from_prompt(message.text)
    
    processing_msg = await message.answer(
        f"⏳ Обработка промта через GPT-4...\n"
        f"{'─' * 40}\n\n"
        f"📝 Ваш промт:\n\n{indented_input}\n\n"
        f"{'─' * 40}\n"
        f"🤖 Разбиваю на {num_scenes} сцены (5 сек каждая)..."
    )
    
    try:
        generator = VideoGenerator()
        
        # GPT разбивает промт на сцены
        scenes_result = await generator.enhance_prompt_with_gpt(
            prompt=message.text,
            num_scenes=num_scenes,
            duration_per_scene=5  # Каждая сцена 5 секунд
        )
        
        await state.update_data(
            scenes=scenes_result["scenes"],
            enhanced_prompt=scenes_result["enhanced_prompt"],
            current_scene_index=0
        )
        
        await state.set_state(PhotoAIStates.confirming_scenes)
        
        await show_scene_for_confirmation(message, state, 0)
        await processing_msg.delete()
        
    except Exception as e:
        logger.error(f"❌ Ошибка обработки: {e}")
        await processing_msg.edit_text(
            f"❌ Ошибка при обработке: {str(e)}\n\n"
            f"Попробуй еще раз с /start"
        )
        await state.clear()


async def show_scene_for_confirmation(message: types.Message, state: FSMContext, scene_index: int):
    """Показывает сцену для подтверждения перед генерацией фото"""
    data = await state.get_data()
    scenes = data.get("scenes", [])
    
    if scene_index >= len(scenes):
        await start_photo_generation(message, state)
        return
    
    scene = scenes[scene_index]
    
    prompt_text = scene.get('prompt', '')
    indented_prompt = "\n".join("    " + line for line in prompt_text.split("\n"))
    
    scene_text = (
        f"🎬 Сцена {scene['id']} из {len(scenes)}\n"
        f"{'─' * 40}\n\n"
        f"📝 Промт для фото:\n{indented_prompt}\n\n"
        f"⏱️  Длительность: {scene.get('duration', 5)} сек\n"
        f"🎨 Атмосфера: {scene.get('atmosphere', 'N/A')}\n\n"
        f"{'─' * 40}\n"
        f"Подходит ли промт для генерации фото?"
    )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Далее", callback_data=f"photo_ai_scene_approve_{scene_index}"),
                InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"photo_ai_scene_edit_{scene_index}")
            ],
            [
                InlineKeyboardButton(text="🔄 Регенерировать все", callback_data="photo_ai_scenes_regenerate"),
                InlineKeyboardButton(text="⬅️ Отмена", callback_data="back_to_menu")
            ]
        ]
    )
    
    await message.answer(scene_text, parse_mode="Markdown", reply_markup=keyboard)


@router.callback_query(lambda c: c.data.startswith("photo_ai_scene_approve_"))
async def approve_scene(callback: types.CallbackQuery, state: FSMContext):
    """Подтверждение сцены"""
    await callback.answer()
    
    scene_index = int(callback.data.replace("photo_ai_scene_approve_", ""))
    data = await state.get_data()
    scenes = data.get("scenes", [])
    
    next_index = scene_index + 1
    await state.update_data(current_scene_index=next_index)
    
    if next_index < len(scenes):
        await show_scene_for_confirmation(callback.message, state, next_index)
    else:
        await start_photo_generation(callback.message, state)


@router.callback_query(lambda c: c.data.startswith("photo_ai_scene_edit_"))
async def edit_scene(callback: types.CallbackQuery, state: FSMContext):
    """Редактирование промта сцены"""
    await callback.answer()
    
    scene_index = int(callback.data.replace("photo_ai_scene_edit_", ""))
    await state.update_data(editing_scene_index=scene_index)
    await state.set_state(PhotoAIStates.editing_scene)
    
    data = await state.get_data()
    scenes = data.get("scenes", [])
    scene = scenes[scene_index]
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Готово", callback_data=f"photo_ai_edit_done_{scene_index}")],
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data="back_to_menu")]
        ]
    )
    
    await callback.message.answer(
        f"✏️ Редактирование сцены {scene_index + 1}\n\n"
        f"Текущий промт:\n{scene['prompt']}\n\n"
        f"Напиши новый промт или нажми Готово:",
        reply_markup=keyboard
    )


@router.message(PhotoAIStates.editing_scene)
async def process_scene_edit(message: types.Message, state: FSMContext):
    """Обработка отредактированного промта"""
    data = await state.get_data()
    scene_index = data.get("editing_scene_index", 0)
    scenes = data.get("scenes", [])
    
    if scene_index < len(scenes):
        scenes[scene_index]['prompt'] = message.text
        await state.update_data(scenes=scenes)
    
    await message.answer(f"✅ Сцена {scene_index + 1} обновлена!")
    await state.set_state(PhotoAIStates.confirming_scenes)
    await show_scene_for_confirmation(message, state, scene_index)


@router.callback_query(lambda c: c.data.startswith("photo_ai_edit_done_"))
async def edit_scene_done(callback: types.CallbackQuery, state: FSMContext):
    """Завершение редактирования"""
    await callback.answer()
    scene_index = int(callback.data.replace("photo_ai_edit_done_", ""))
    await state.set_state(PhotoAIStates.confirming_scenes)
    await show_scene_for_confirmation(callback.message, state, scene_index)


@router.callback_query(lambda c: c.data == "photo_ai_scenes_regenerate")
async def regenerate_scenes(callback: types.CallbackQuery, state: FSMContext):
    """Регенерирование всех сцен"""
    await callback.answer()
    
    data = await state.get_data()
    prompt = data.get("prompt", "")
    
    await state.set_state(PhotoAIStates.processing_prompt)
    
    processing_msg = await callback.message.answer(
        "⏳ Регенерирую сцены..."
    )
    
    try:
        generator = VideoGenerator()
        num_scenes = _extract_num_scenes_from_prompt(prompt)
        
        scenes_result = await generator.enhance_prompt_with_gpt(
            prompt=prompt,
            num_scenes=num_scenes,
            duration_per_scene=5
        )
        
        await state.update_data(
            scenes=scenes_result["scenes"],
            current_scene_index=0
        )
        
        await state.set_state(PhotoAIStates.confirming_scenes)
        await show_scene_for_confirmation(callback.message, state, 0)
        await processing_msg.delete()
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        await processing_msg.edit_text(f"❌ Ошибка: {str(e)[:100]}")


async def start_photo_generation(message: types.Message, state: FSMContext):
    """Начало генерации фото через google/nano-banana"""
    data = await state.get_data()
    scenes = data.get("scenes", [])
    aspect_ratio = data.get("aspect_ratio", "16:9")
    reference_url = data.get("reference_url")
    general_prompt = data.get("enhanced_prompt", "")
    
    generating_msg = await message.answer(
        f"🎨 Начинаю генерацию фото для {len(scenes)} сцен...\n\n"
        f"🎬 google/nano-banana генерирует фото\n"
        f"({'с референсом' if reference_url else 'без референса'})\n\n"
        f"⏳ Это может занять несколько минут..."
    )
    
    await state.set_state(PhotoAIStates.generating_photos)
    
    try:
        photo_gen = PhotoGenerator()
        
        photos_result = await photo_gen.generate_photos_for_scenes(
            scenes=scenes,
            aspect_ratio=aspect_ratio,
            reference_image_url=reference_url,
            general_prompt=general_prompt
        )
        
        if photos_result["status"] == "success":
            scenes_with_photos = photos_result["scenes_with_photos"]
            successful = photos_result["successful_photos"]
            
            await state.update_data(scenes_with_photos=scenes_with_photos)
            await state.set_state(PhotoAIStates.confirming_photos)
            
            await generating_msg.edit_text(
                f"✅ Фото готовы!\n\n"
                f"📊 Статистика:\n"
                f"  Всего сцен: {photos_result['total_scenes']}\n"
                f"  Успешно: {successful}\n\n"
                f"Подтверждаешь эти фото для видео?"
            )
            
            # Показываю первое фото
            await show_photo_for_confirmation(message, state, 0)
            
        else:
            error = photos_result.get("error", "Unknown error")
            await generating_msg.edit_text(f"❌ Ошибка: {error}")
            await state.clear()
            
    except Exception as e:
        logger.error(f"❌ Ошибка генерации фото: {e}")
        await generating_msg.edit_text(f"❌ Ошибка: {str(e)[:100]}")
        await state.clear()


async def show_photo_for_confirmation(message: types.Message, state: FSMContext, scene_index: int):
    """Показывает фото для подтверждения"""
    data = await state.get_data()
    scenes_with_photos = data.get("scenes_with_photos", [])
    
    if scene_index >= len(scenes_with_photos):
        await start_video_generation_final(message, state)
        return
    
    scene = scenes_with_photos[scene_index]
    photo_url = scene.get("photo_url")
    
    if not photo_url:
        error_msg = scene.get("photo_error", "Ошибка генерации")
        text = f"⚠️ Сцена {scene_index + 1}: Ошибка\n{error_msg}\n\nПропускаю..."
        await message.answer(text)
        
        next_index = scene_index + 1
        await state.update_data(current_scene_index=next_index)
        await show_photo_for_confirmation(message, state, next_index)
        return
    
    scene_text = (
        f"🖼️ Сцена {scene_index + 1} из {len(scenes_with_photos)}\n"
        f"{'─' * 40}\n\n"
        f"📝 Промт: {scene.get('prompt', '')[:100]}...\n"
        f"🎨 Атмосфера: {scene.get('atmosphere', 'N/A')}\n\n"
        f"Подходит ли это фото?"
    )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Далее", callback_data=f"photo_ai_photo_approve_{scene_index}"),
                InlineKeyboardButton(text="🔄 Регенерировать", callback_data=f"photo_ai_photo_regen_{scene_index}")
            ],
            [
                InlineKeyboardButton(text="✅ Принять все", callback_data="photo_ai_photos_final"),
                InlineKeyboardButton(text="⬅️ Отмена", callback_data="back_to_menu")
            ]
        ]
    )
    
    try:
        if scene.get("photo_path"):
            await message.answer_photo(
                types.FSInputFile(scene["photo_path"]),
                caption=scene_text,
                reply_markup=keyboard
            )
        else:
            await message.answer(scene_text, reply_markup=keyboard)
    except Exception as e:
        logger.warning(f"⚠️ Ошибка отправки фото: {e}")
        await message.answer(scene_text, reply_markup=keyboard)


@router.callback_query(lambda c: c.data.startswith("photo_ai_photo_approve_"))
async def approve_photo(callback: types.CallbackQuery, state: FSMContext):
    """Подтверждение фото"""
    await callback.answer()
    scene_index = int(callback.data.replace("photo_ai_photo_approve_", ""))
    
    next_index = scene_index + 1
    await state.update_data(current_scene_index=next_index)
    
    data = await state.get_data()
    scenes_with_photos = data.get("scenes_with_photos", [])
    
    if next_index < len(scenes_with_photos):
        await show_photo_for_confirmation(callback.message, state, next_index)
    else:
        await start_video_generation_final(callback.message, state)


@router.callback_query(lambda c: c.data == "photo_ai_photos_final")
async def approve_all_photos(callback: types.CallbackQuery, state: FSMContext):
    """Принятие всех фото"""
    await callback.answer()
    await start_video_generation_final(callback.message, state)


async def start_video_generation_final(message: types.Message, state: FSMContext):
    """Финальная генерация видео на основе фото"""
    data = await state.get_data()
    scenes_with_photos = data.get("scenes_with_photos", [])
    aspect_ratio = data.get("aspect_ratio", "16:9")
    model = data.get("model", "kwaivgi/kling-v2.5-turbo-pro")
    
    generating_msg = await message.answer(
        f"🎬 Начинаю генерацию видео на основе фото!\n\n"
        f"📊 Статистика:\n"
        f"  Сцен: {len(scenes_with_photos)}\n"
        f"  Длительность: {len(scenes_with_photos) * 5} сек\n"
        f"  Модель: Kling v2.5 Turbo Pro\n\n"
        f"⏳ Генерирую видео для каждой сцены..."
    )
    
    await state.set_state(PhotoAIStates.generating_video)
    
    try:
        generator = VideoGenerator()
        stitcher = VideoStitcher()
        
        video_paths = []
        
        # Генерирую видео для каждой сцены с фото
        for idx, scene in enumerate(scenes_with_photos):
            scene_num = idx + 1
            logger.info(f"🎥 Генерирую видео для сцены {scene_num}/{len(scenes_with_photos)}...")
            
            await generating_msg.edit_text(
                f"🎬 Генерирую видео ({scene_num}/{len(scenes_with_photos)})...\n\n"
                f"Прогресс: {int(scene_num / len(scenes_with_photos) * 100)}%"
            )
            
            photo_url = scene.get("photo_url")
            if not photo_url:
                logger.warning(f"⚠️ Нет фото для сцены {scene_num}, пропускаю")
                continue
            
            result = await generator.generate_scene(
                prompt=scene.get("prompt", ""),
                duration=5,
                aspect_ratio=aspect_ratio,
                model="kling",
                start_image_url=photo_url  # Используем фото как начальный фрейм
            )
            
            if result.get("status") == "success":
                video_url = result.get("video_url")
                video_path = await stitcher.download_video(
                    video_url,
                    f"scene_{scene_num}.mp4"
                )
                
                if video_path:
                    video_paths.append(video_path)
                    logger.info(f"✅ Видео сцены {scene_num} готово")
            else:
                logger.error(f"❌ Ошибка генерации сцены {scene_num}")
        
        # Склеиваю видео
        if video_paths:
            await generating_msg.edit_text("🎞️ Склеиваю видео...")
            
            final_video = await stitcher.stitch_videos(video_paths)
            
            if final_video:
                await generating_msg.delete()
                
                await message.answer_video(
                    types.FSInputFile(final_video),
                    caption="✅ Видео готово! Создано с помощью:\n"
                            "• Google Nano-Banana (фото)\n"
                            "• Kling v2.5 Turbo Pro (видео)"
                )
                
                await stitcher.cleanup_temp_files()
                logger.info("✅ Видео успешно отправлено!")
            else:
                await generating_msg.edit_text("❌ Ошибка при склеивании видео")
        else:
            await generating_msg.edit_text("❌ Не удалось сгенерировать видео для сцен")
            
    except Exception as e:
        logger.error(f"❌ Ошибка генерации видео: {e}")
        await generating_msg.edit_text(f"❌ Ошибка: {str(e)[:100]}")
    
    finally:
        await state.clear()


def _extract_num_scenes_from_prompt(prompt: str) -> int:
    """Извлекает количество сцен из промта"""
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
            if 1 <= num <= 20:
                return num
    
    return 3  # По умолчанию 3 сцены