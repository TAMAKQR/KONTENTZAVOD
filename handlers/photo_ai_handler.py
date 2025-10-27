"""Обработчик для потока Текст + Фото + AI → Видео"""
import asyncio
import json
import logging
from aiogram import Router, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import StateFilter
from video_generator import VideoGenerator
from photo_generator import PhotoGenerator
from video_stitcher import VideoStitcher

logger = logging.getLogger(__name__)
router = Router()


# ✅ ХЕЛПЕР: Сохранение результатов в JSON для ИИ
async def save_scenes_result_to_json(message: types.Message, scenes: list, enhanced_prompt: str, aspect_ratio: str = "16:9"):
    """Сохраняет результаты генерации фото в JSON формат для ИИ"""
    from datetime import datetime
    
    try:
        user_id = message.from_user.id if message.from_user else "unknown"
        
        json_result = {
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "enhanced_prompt": enhanced_prompt,
            "num_scenes": len(scenes),
            "aspect_ratio": aspect_ratio,
            "scenes": []
        }
        
        for i, scene in enumerate(scenes, 1):
            scene_data = {
                "scene_number": i,
                "prompt": scene.get("prompt", ""),
                "duration": scene.get("duration", 5),
                "atmosphere": scene.get("atmosphere", ""),
                "photo_path": scene.get("photo_path", ""),
                "photo_url": scene.get("photo_url", ""),
                "photo_error": scene.get("photo_error", None)
            }
            json_result["scenes"].append(scene_data)
        
        # Сохраняем JSON файл
        json_path = f"d:\\VIDEO\\temp_images\\scene_result_{user_id}_{int(datetime.now().timestamp())}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_result, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ JSON результат сохранен: {json_path}")
        return json_path
    except Exception as e:
        logger.error(f"❌ Ошибка при сохранении JSON: {e}")
        return None


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
        f"{'─' * 40}\n\n"
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
            # ✅ Получаем прямую ссылку на фото из Telegram (вместо загрузки на ImgBB)
            # Это проще и надежнее для использования с Replicate API
            file = await message.bot.get_file(message.photo[-1].file_id)
            reference_url = f"https://api.telegram.org/file/bot{message.bot.token}/{file.file_path}"
            
            logger.info(f"✅ Получена Telegram ссылка на фото: {reference_url[:80]}...")
            
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
    """Обработка промта и разбиение на сцены + СРАЗУ ГЕНЕРИРУЕМ ВСЕ ФОТО ПАРАЛЛЕЛЬНО (БЕЗ ПОДТВЕРЖДЕНИЯ СЦЕН)"""
    data = await state.get_data()
    reference_file_id = data.get("reference_file_id")
    
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
        f"🤖 Разбиваю на {num_scenes} сцены (5 сек каждая)...\n"
        f"📸 Затем генерирую фото (параллель)..."
    )
    
    try:
        generator = VideoGenerator()
        
        # ✅ GPT разбивает промт на сцены
        scenes_result = await generator.enhance_prompt_with_gpt(
            prompt=message.text,
            num_scenes=num_scenes,
            duration_per_scene=5
        )
        
        scenes = scenes_result["scenes"]
        enhanced_prompt = scenes_result.get("enhanced_prompt", "")
        
        # ✅ ТОЛЬКО ПОКАЗЫВАЕМ что идет обработка (БЕЗ дублирования информации)
        await processing_msg.edit_text(
            f"✅ GPT-4 ОБРАБОТКА ЗАВЕРШЕНА!\n"
            f"{'═' * 50}\n\n"
            f"📸 Генерирую фото для {len(scenes)} сцен...\n"
            f"⏳ Это займет 1-2 мин (каждое фото наследует от предыдущего)...\n\n"
            f"Результаты будут показаны ниже ↓"
        )
        
        # ✅ ШАГ 1: Генерируем ФОТО ПОСЛЕДОВАТЕЛЬНО С НАСЛЕДОВАНИЕМ
        photo_gen = PhotoGenerator()
        
        # Получаем URL референса из state, если был загружен
        reference_url = data.get("reference_url")
        logger.info(f"🔍 DEBUG photo_ai_handler: reference_url = {reference_url}")
        logger.info(f"🔍 DEBUG photo_ai_handler: все данные в state = {list(data.keys())}")
        if reference_url:
            logger.info(f"📸 Используем reference_url: {reference_url[:80]}...")
        else:
            logger.info(f"📸 Генерация БЕЗ reference (reference_url пуст/None)")
        
        photos_result = await photo_gen.generate_photos_for_scenes(
            scenes=scenes,
            aspect_ratio=data.get("aspect_ratio", "16:9"),
            reference_image_url=reference_url,  # ✅ Передаём реальный URL референса
            general_prompt=""
        )
        
        # ✅ ШАГ 2: Используем сцены с уже прикрепленными фото
        final_scenes_with_photos = photos_result.get("scenes_with_photos", [])
        successful_photos = photos_result.get("successful_photos", 0)
        total_scenes = photos_result.get("total_scenes", len(final_scenes_with_photos))
        
        # ⚠️ Если есть ошибки при генерации фото
        if successful_photos < total_scenes:
            failed_count = total_scenes - successful_photos
            error_msg = (
                f"⚠️ Удалось сгенерировать фото: {successful_photos}/{total_scenes}\n"
                f"❌ Не удалось: {failed_count} сцены\n\n"
                f"💡 Совет: Это часто происходит из-за фильтра безопасности API.\n"
                f"📝 Попробуйте изменить промт:\n"
                f"- Избегайте слов 'женщина', 'человек', 'портрет'\n"
                f"- Используйте 'персонаж', 'существо', 'изображение'\n"
                f"- Сделайте промт более абстрактным или фантастичным"
            )
            logger.warning(f"⚠️ {error_msg}")
        
        await state.update_data(
            scenes=final_scenes_with_photos,
            enhanced_prompt=enhanced_prompt,
            current_photo_index=0
        )
        
        # ✅ СОХРАНЯЕМ результаты в JSON для ИИ (используя хелпер)
        await save_scenes_result_to_json(
            message=message,
            scenes=final_scenes_with_photos,
            enhanced_prompt=enhanced_prompt,
            aspect_ratio=data.get("aspect_ratio", "16:9")
        )
        
        # ✅ ШАГ 3: Показываем ВСЕ СЦЕНЫ + ВСЕ ФОТО для подтверждения
        await processing_msg.delete()
        await state.set_state(PhotoAIStates.confirming_photos)
        await show_all_scenes_and_photos_for_confirmation(message, state)
        
    except Exception as e:
        logger.error(f"❌ Ошибка обработки: {e}")
        error_text = str(e)
        
        # ✅ Специальная обработка ошибки E005 (фильтр безопасности)
        if "E005" in error_text or "sensitive" in error_text.lower():
            help_text = (
                f"❌ Ошибка: Фильтр безопасности API\n\n"
                f"Причина: Промт содержит слова о реальных людях\n\n"
                f"💡 Совет для исправления:\n"
                f"✏️ Избегайте:\n"
                f"  - 'женщина', 'человек', 'люди', 'лицо'\n"
                f"  - 'портрет', 'реальное фото'\n\n"
                f"✅ Используйте:\n"
                f"  - 'персонаж', 'существо', 'изображение'\n"
                f"  - Более абстрактные описания\n"
                f"  - Фантастические или художественные стили\n\n"
                f"🔄 Введи новый промт с /start"
            )
        else:
            help_text = f"❌ Ошибка при обработке:\n{error_text[:200]}\n\nПопробуй еще раз с /start"
        
        await processing_msg.edit_text(help_text)
        await state.clear()


async def show_all_scenes_and_photos_for_confirmation(message: types.Message, state: FSMContext):
    """✅ НОВОЕ: Показывает КАЖДУЮ СЦЕНУ + её ФОТО вместе для подтверждения"""
    data = await state.get_data()
    scenes = data.get("scenes", [])
    enhanced_prompt = data.get("enhanced_prompt", "")
    
    if not scenes:
        await message.answer("❌ Ошибка: нет сцен")
        return
    
    # Подсчитываем успешные фото
    successful_photos_count = sum(1 for s in scenes if s.get("photo_url") or s.get("photo_path"))
    failed_photos_count = len(scenes) - successful_photos_count
    
    # ✅ Показываем ИНФОРМАЦИЮ + ФОТО для каждой сцены
    for i, scene in enumerate(scenes, 1):
        # Формируем информацию сцены
        scene_text = f"🎬 СЦЕНА {i}/{len(scenes)}\n"
        scene_text += "─" * 40 + "\n"
        scene_text += f"📝 Промт: {scene.get('prompt', 'N/A')}\n"
        scene_text += f"⏱️ Длительность: {scene.get('duration', 5)} сек\n"
        scene_text += f"🎨 Атмосфера: {scene.get('atmosphere', 'N/A')}"
        
        # Добавляем информацию об ошибке, если есть
        if scene.get("photo_error"):
            scene_text += f"\n❌ Ошибка: {scene.get('photo_error')[:100]}"
        
        # Отправляем информацию сцены
        await message.answer(scene_text, parse_mode="Markdown")
        
        # Отправляем фотографию для этой сцены (если она есть)
        photo_path = scene.get("photo_path")
        photo_url = scene.get("photo_url")
        
        if photo_path or photo_url:
            try:
                if photo_path:
                    # ✅ Используем FSInputFile для локальных файлов
                    photo_input = FSInputFile(photo_path)
                    await message.answer_photo(
                        photo=photo_input,
                        caption=f"🖼️ Фото для сцены {i} ✅"
                    )
                elif photo_url:
                    await message.answer_photo(
                        photo=photo_url,
                        caption=f"🖼️ Фото для сцены {i} ✅"
                    )
            except Exception as e:
                logger.warning(f"⚠️ Не смог отправить фото сцены {i}: {e}")
                await message.answer(f"⚠️ Ошибка при отправке фото сцены {i}: {str(e)[:80]}")
        else:
            error_reason = scene.get('photo_error', 'Ошибка генерации')
            await message.answer(
                f"⚠️ Фото для сцены {i} не найдено\n\n"
                f"Причина: {error_reason}"
            )
    
    # В конце показываем финальное сообщение с кнопками подтверждения
    final_text = "=" * 50 + "\n"
    
    if failed_photos_count == 0:
        final_text += f"✅ ВСЕ {len(scenes)} СЦЕН И ИХ ФОТО ГОТОВЫ!\n"
    else:
        final_text += f"⚠️ СТАТУС: {successful_photos_count}/{len(scenes)} фото готовы\n"
        final_text += f"❌ Не удалось: {failed_photos_count} сцены\n"
    
    final_text += "=" * 50 + "\n\n"
    final_text += "Подтверждаешь ли все сцены и фото для генерации видео?"
    
    # Кнопки зависят от того, есть ли ошибки
    if failed_photos_count > 0:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ ПРИНЯТЬ (даже с ошибками)", callback_data="photo_ai_confirm_all_scenes"),
                    InlineKeyboardButton(text="🔄 Переделать ВСЕ", callback_data="photo_ai_regenerate_photos")
                ],
                [
                    InlineKeyboardButton(text="✏️ Изменить промт", callback_data="photo_ai_edit_all_scenes"),
                    InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")
                ]
            ]
        )
    else:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ ПРИНЯТЬ ВСЕ", callback_data="photo_ai_confirm_all_scenes"),
                    InlineKeyboardButton(text="✏️ Редактировать сцены", callback_data="photo_ai_edit_all_scenes")
                ],
                [
                    InlineKeyboardButton(text="🔄 Переделать фото", callback_data="photo_ai_regenerate_photos"),
                    InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")
                ]
            ]
        )
    
    await message.answer(final_text, parse_mode="Markdown", reply_markup=keyboard)


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


@router.callback_query(lambda c: c.data == "photo_ai_confirm_all_scenes")
async def confirm_all_scenes(callback: types.CallbackQuery, state: FSMContext):
    """✅ НОВОЕ: Подтверждение ВСЕ СЦЕНЫ + ФОТО → Генерация видео"""
    await callback.answer()
    
    data = await state.get_data()
    scenes = data.get("scenes", [])
    
    # Переименовываем для совместимости с start_video_generation_final()
    await state.update_data(scenes_with_photos=scenes)
    
    await callback.message.answer(
        f"⏳ Начинаю генерацию видео для {len(scenes)} сцен...\n"
        f"🎬 Это займет 2-5 минут в зависимости от количества сцен"
    )
    
    # Переходим к генерации видео
    await start_video_generation_final(callback.message, state)


@router.callback_query(lambda c: c.data == "photo_ai_regenerate_photos")
async def regenerate_all_photos(callback: types.CallbackQuery, state: FSMContext):
    """🔄 Переделать все фото - вернуться к шагу генерации фото"""
    await callback.answer()
    
    data = await state.get_data()
    scenes = data.get("scenes", [])
    aspect_ratio = data.get("aspect_ratio", "16:9")
    
    processing_msg = await callback.message.answer(
        f"🔄 Переделаю фото для всех {len(scenes)} сцен ПОСЛЕДОВАТЕЛЬНО...\n"
        f"⏳ Это займет 1-2 мин (с наследованием между сценами)..."
    )
    
    # Переходим обратно к генерации фото
    await state.set_state(PhotoAIStates.processing_prompt)
    
    try:
        photo_gen = PhotoGenerator()
        
        # ✅ Используем новый API с правильными параметрами
        photos_result = await photo_gen.generate_photos_for_scenes(
            scenes=scenes,
            aspect_ratio=aspect_ratio,
            reference_image_url=None,
            general_prompt=""
        )
        
        # ✅ Используем сцены с уже прикрепленными фото
        final_scenes_with_photos = photos_result.get("scenes_with_photos", [])
        successful_photos = photos_result.get("successful_photos", 0)
        total_scenes = photos_result.get("total_scenes", len(final_scenes_with_photos))
        
        # ⚠️ Если есть ошибки при генерации фото
        if successful_photos < total_scenes:
            failed_count = total_scenes - successful_photos
            logger.warning(
                f"⚠️ Переделка фото: {successful_photos}/{total_scenes} успешно, "
                f"{failed_count} ошибок"
            )
        
        await state.update_data(scenes=final_scenes_with_photos)
        
        # ✅ СОХРАНЯЕМ результаты переделки в JSON
        enhanced_prompt = data.get("enhanced_prompt", "")
        await save_scenes_result_to_json(
            message=callback.message,
            scenes=final_scenes_with_photos,
            enhanced_prompt=enhanced_prompt,
            aspect_ratio=aspect_ratio
        )
        
        await state.set_state(PhotoAIStates.confirming_photos)
        
        await processing_msg.delete()
        
        # Показываем ВСЕ СЦЕНЫ + ВСЕ ФОТО еще раз
        await show_all_scenes_and_photos_for_confirmation(callback.message, state)
        
    except Exception as e:
        logger.error(f"❌ Ошибка переделывания фото: {e}")
        error_text = str(e)
        
        # ✅ Специальная обработка ошибки E005
        if "E005" in error_text or "sensitive" in error_text.lower():
            help_text = (
                f"❌ Ошибка: Фильтр безопасности API при переделке фото\n\n"
                f"💡 Советы:\n"
                f"- Избегайте слов о реальных людях\n"
                f"- Используйте более абстрактные описания\n"
                f"- Попробуйте фантастический или художественный стиль"
            )
        else:
            help_text = f"❌ Ошибка при переделке фото:\n{error_text[:150]}"
        
        await processing_msg.edit_text(help_text)


@router.callback_query(lambda c: c.data == "photo_ai_edit_all_scenes")
async def edit_all_scenes(callback: types.CallbackQuery, state: FSMContext):
    """✏️ Редактировать все сцены"""
    await callback.answer()
    
    await callback.message.answer(
        "✏️ Редактирование сцен:\n\n"
        "Отправь новый промт для всех сцен,\n"
        "и система переделает фото с новыми промтами."
    )
    
    await state.set_state(PhotoAIStates.waiting_prompt)


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


async def start_photo_generation_immediate(message: types.Message, state: FSMContext, status_msg=None):
    """НОВЫЙ процесс: Генерация фото СРАЗУ после GPT разбиения - ПАРАЛЛЕЛЬНО для всех сцен
    
    Показывает фото вместе с информацией о сцене (промт, атмосфера, длительность)
    как с референсом, так и без него
    """
    data = await state.get_data()
    scenes = data.get("scenes", [])
    aspect_ratio = data.get("aspect_ratio", "16:9")
    reference_url = data.get("reference_url")
    general_prompt = data.get("enhanced_prompt", "")
    
    await state.set_state(PhotoAIStates.generating_photos)
    
    try:
        photo_gen = PhotoGenerator()
        
        # ПОСЛЕДОВАТЕЛЬНАЯ генерация фото для всех сцен с наследованием
        logger.info(f"📸 Генерирую фото для {len(scenes)} сцен ПОСЛЕДОВАТЕЛЬНО...")
        logger.info(f"   Соотношение: {aspect_ratio}")
        logger.info(f"   Референс: {'ДА 📸' if reference_url else 'НЕТ'}")
        logger.info(f"   Каждое фото будет использовано как референс для следующего")
        
        # ✅ generate_photos_for_scenes уже async, поэтому просто await
        photos_result = await photo_gen.generate_photos_for_scenes(
            scenes=scenes,
            aspect_ratio=aspect_ratio,
            reference_image_url=reference_url,
            general_prompt=general_prompt
        )
        
        if photos_result["status"] == "success":
            scenes_with_photos = photos_result["scenes_with_photos"]
            successful = photos_result["successful_photos"]
            total = photos_result["total_scenes"]
            
            await state.update_data(
                scenes_with_photos=scenes_with_photos,
                current_scene_index=0
            )
            
            # ✅ СОХРАНЯЕМ результаты в JSON
            enhanced_prompt = general_prompt or data.get("enhanced_prompt", "")
            await save_scenes_result_to_json(
                message=message,
                scenes=scenes_with_photos,
                enhanced_prompt=enhanced_prompt,
                aspect_ratio=aspect_ratio
            )
            
            await state.set_state(PhotoAIStates.confirming_photos)
            
            # Удаляю статус сообщение если есть
            if status_msg:
                try:
                    await status_msg.delete()
                except:
                    pass
            
            logger.info(f"✅ Фото готовы! Успешно: {successful}/{total}")
            
            # ✅ Показываем первое фото с полной информацией
            await show_photo_for_confirmation(message, state, 0)
            
        else:
            error = photos_result.get("error", "Unknown error")
            logger.error(f"❌ Ошибка генерации: {error}")
            if status_msg:
                await status_msg.edit_text(f"❌ Ошибка: {error}")
            await state.clear()
            
    except Exception as e:
        logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА генерации фото: {e}", exc_info=True)
        if status_msg:
            await status_msg.edit_text(f"❌ Ошибка: {str(e)[:150]}")
        await state.clear()


async def start_photo_generation(message: types.Message, state: FSMContext):
    """Генерация фото (старый процесс с подтверждением сцен)"""
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
            
            # ✅ СОХРАНЯЕМ результаты в JSON
            await save_scenes_result_to_json(
                message=message,
                scenes=scenes_with_photos,
                enhanced_prompt=general_prompt,
                aspect_ratio=aspect_ratio
            )
            
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
    """Показывает фото для подтверждения с информацией о сцене, атмосфере и генерации
    
    Отображает:
    - Номер сцены и фото
    - Полный промт
    - Атмосферу и длительность
    - Информацию о использовании референса
    - Фото как изображение
    """
    data = await state.get_data()
    scenes_with_photos = data.get("scenes_with_photos", [])
    reference_url = data.get("reference_url")
    aspect_ratio = data.get("aspect_ratio", "16:9")
    
    if scene_index >= len(scenes_with_photos):
        await start_video_generation_final(message, state)
        return
    
    scene = scenes_with_photos[scene_index]
    photo_url = scene.get("photo_url")
    
    if not photo_url:
        error_msg = scene.get("photo_error", "Ошибка генерации")
        text = (
            f"⚠️ Сцена {scene_index + 1}: Ошибка\n"
            f"{'─' * 50}\n"
            f"{error_msg}\n\n"
            f"Пропускаю эту сцену..."
        )
        await message.answer(text)
        
        next_index = scene_index + 1
        await state.update_data(current_scene_index=next_index)
        await show_photo_for_confirmation(message, state, next_index)
        return
    
    prompt_full = scene.get('prompt', '')
    atmosphere = scene.get('atmosphere', 'N/A')
    
    # Информация о генерации с учетом референса
    reference_info = "📸 С референсом" if reference_url else "🎨 Без референса"
    
    scene_text = (
        f"🖼️ Фото {scene_index + 1} из {len(scenes_with_photos)}\n"
        f"{'═' * 50}\n\n"
        f"📝 **Промт для фото:**\n"
        f"{prompt_full}\n\n"
        f"{'─' * 50}\n"
        f"⏱️  **Длительность:** 5 сек\n"
        f"🎨 **Атмосфера:** {atmosphere}\n"
        f"📐 **Соотношение:** {aspect_ratio}\n"
        f"🎬 **Генератор:** google/nano-banana {reference_info}\n"
        f"{'═' * 50}\n\n"
        f"Подходит ли это фото?"
    )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Далее", callback_data=f"photo_ai_photo_approve_{scene_index}"),
                InlineKeyboardButton(text="🔄 Переделать", callback_data=f"photo_ai_photo_regen_{scene_index}")
            ],
            [
                InlineKeyboardButton(text="✏️ Изменить промт", callback_data=f"photo_ai_photo_edit_{scene_index}")
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
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        else:
            await message.answer(scene_text, reply_markup=keyboard, parse_mode="Markdown")
    except Exception as e:
        logger.warning(f"⚠️ Ошибка отправки фото: {e}")
        await message.answer(scene_text, reply_markup=keyboard, parse_mode="Markdown")


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


@router.callback_query(lambda c: c.data.startswith("photo_ai_photo_regen_"))
async def regenerate_photo(callback: types.CallbackQuery, state: FSMContext):
    """Регенерирование фото для конкретной сцены"""
    await callback.answer()
    scene_index = int(callback.data.replace("photo_ai_photo_regen_", ""))
    
    data = await state.get_data()
    scenes_with_photos = data.get("scenes_with_photos", [])
    aspect_ratio = data.get("aspect_ratio", "16:9")
    reference_url = data.get("reference_url")
    general_prompt = data.get("enhanced_prompt", "")
    
    if scene_index >= len(scenes_with_photos):
        await callback.message.answer("❌ Сцена не найдена")
        return
    
    scene = scenes_with_photos[scene_index]
    
    regenerating_msg = await callback.message.answer(
        f"🎨 Регенерирую фото для сцены {scene_index + 1}...\n"
        f"⏳ Это может занять минуту..."
    )
    
    try:
        photo_gen = PhotoGenerator()
        
        # Генерирую одно фото
        prompt = scene.get('prompt', general_prompt)
        result = await photo_gen._generate_single_photo(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            reference_image_url=reference_url,
            scene_index=scene_index
        )
        
        if result.get("status") == "success":
            # Обновляю сцену с новым фото
            scene["photo_url"] = result.get("photo_url")
            scene["photo_path"] = result.get("photo_path")
            
            scenes_with_photos[scene_index] = scene
            await state.update_data(scenes_with_photos=scenes_with_photos)
            
            await regenerating_msg.delete()
            
            # Показываю обновленное фото
            await state.set_state(PhotoAIStates.confirming_photos)
            await show_photo_for_confirmation(callback.message, state, scene_index)
        else:
            error = result.get("error", "Unknown error")
            await regenerating_msg.edit_text(f"❌ Ошибка: {error}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка регенерации фото: {e}")
        await regenerating_msg.edit_text(f"❌ Ошибка: {str(e)[:100]}")


@router.callback_query(lambda c: c.data.startswith("photo_ai_photo_edit_"))
async def edit_photo_prompt(callback: types.CallbackQuery, state: FSMContext):
    """Редактирование промта для фото"""
    await callback.answer()
    scene_index = int(callback.data.replace("photo_ai_photo_edit_", ""))
    
    await state.update_data(editing_photo_index=scene_index)
    await state.set_state(PhotoAIStates.editing_scene)
    
    data = await state.get_data()
    scenes_with_photos = data.get("scenes_with_photos", [])
    
    if scene_index >= len(scenes_with_photos):
        await callback.message.answer("❌ Сцена не найдена")
        return
    
    scene = scenes_with_photos[scene_index]
    current_prompt = scene.get('prompt', '')
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Готово", callback_data=f"photo_ai_photo_edit_done_{scene_index}")],
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data="back_to_menu")]
        ]
    )
    
    await callback.message.answer(
        f"✏️ Редактирование промта для сцены {scene_index + 1}\n\n"
        f"Текущий промт:\n{current_prompt}\n\n"
        f"Напиши новый промт или нажми Готово:",
        reply_markup=keyboard
    )


@router.message(PhotoAIStates.editing_scene)
async def process_photo_prompt_edit(message: types.Message, state: FSMContext):
    """Обработка отредактированного промта для фото"""
    data = await state.get_data()
    scene_index = data.get("editing_photo_index")
    
    if scene_index is not None:
        scenes_with_photos = data.get("scenes_with_photos", [])
        
        if scene_index < len(scenes_with_photos):
            scenes_with_photos[scene_index]['prompt'] = message.text
            await state.update_data(scenes_with_photos=scenes_with_photos)
            await message.answer(f"✅ Промт сцены {scene_index + 1} обновлен!")
    
    await state.set_state(PhotoAIStates.confirming_photos)


@router.callback_query(lambda c: c.data.startswith("photo_ai_photo_edit_done_"))
async def photo_edit_done(callback: types.CallbackQuery, state: FSMContext):
    """Завершение редактирования промта и регенерация фото"""
    await callback.answer()
    scene_index = int(callback.data.replace("photo_ai_photo_edit_done_", ""))
    
    data = await state.get_data()
    scenes_with_photos = data.get("scenes_with_photos", [])
    aspect_ratio = data.get("aspect_ratio", "16:9")
    reference_url = data.get("reference_url")
    general_prompt = data.get("enhanced_prompt", "")
    
    if scene_index >= len(scenes_with_photos):
        await callback.message.answer("❌ Сцена не найдена")
        return
    
    scene = scenes_with_photos[scene_index]
    
    regenerating_msg = await callback.message.answer(
        f"🎨 Генерирую новое фото с обновленным промтом...\n"
        f"⏳ Это может занять минуту..."
    )
    
    try:
        photo_gen = PhotoGenerator()
        
        # Генерирую одно фото с новым промтом
        prompt = scene.get('prompt', general_prompt)
        result = await photo_gen._generate_single_photo(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            reference_image_url=reference_url,
            scene_index=scene_index
        )
        
        if result.get("status") == "success":
            # Обновляю сцену с новым фото
            scene["photo_url"] = result.get("photo_url")
            scene["photo_path"] = result.get("photo_path")
            
            scenes_with_photos[scene_index] = scene
            await state.update_data(scenes_with_photos=scenes_with_photos)
            
            await regenerating_msg.delete()
            
            # Показываю обновленное фото
            await state.set_state(PhotoAIStates.confirming_photos)
            await show_photo_for_confirmation(callback.message, state, scene_index)
        else:
            error = result.get("error", "Unknown error")
            await regenerating_msg.edit_text(f"❌ Ошибка: {error}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        await regenerating_msg.edit_text(f"❌ Ошибка: {str(e)[:100]}")


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
    """Извлекает количество сцен из промта - ищет МАКСИМАЛЬНОЕ число!
    
    Обработает:
    - Цифры: "1 сцене", "2 сцены", "на 3 сцены"
    - Порядковые числительные: "во второй сцене", "в третьей сцене"
    """
    import re
    
    # ✅ Ищу ВСЕ числа связанные со сценами
    patterns = [
        r'(\d+)\s*сцен',          # "1 сцене", "2 сцены"
        r'(\d+)\s*scene',         # "1 scene", "2 scenes"
        r'на\s*(\d+)\s*сцен',     # "на 2 сцены"
        r'разбить на\s*(\d+)',    # "разбить на 3"
        r'(\d+)\s*частей',        # "3 части"
        r'split.*?(\d+)',         # "split 4"
        r'сцена\s*(\d+)',         # "сцена 2"
        r'scene\s*(\d+)',         # "scene 3"
    ]
    
    # Словарь для преобразования порядковых числительных в цифры
    ordinal_map = {
        'перв': 1, 'первая': 1, 'первой': 1, 'первую': 1,
        'втор': 2, 'вторая': 2, 'второй': 2, 'вторую': 2,
        'трет': 3, 'третья': 3, 'третьей': 3, 'третью': 3,
        'четвёрт': 4, 'четвертая': 4, 'четвёртой': 4,
        'пят': 5, 'пятая': 5, 'пятой': 5,
        'шест': 6, 'шестая': 6, 'шестой': 6,
        'сед': 7, 'седьмая': 7, 'седьмой': 7,
        'восьм': 8, 'восьмая': 8, 'восьмой': 8,
        'девят': 9, 'девятая': 9, 'девятой': 9,
        'десят': 10, 'десятая': 10, 'десятой': 10,
    }
    
    found_numbers = []
    
    # Ищу цифры в стандартных паттернах
    for pattern in patterns:
        matches = re.findall(pattern, prompt, re.IGNORECASE)
        for match in matches:
            num = int(match)
            if 1 <= num <= 20:
                found_numbers.append(num)
    
    # Ищу порядковые числительные (например "во второй сцене", "в третьей")
    ordinal_pattern = r'(первой|первую|вторая|второй|вторую|третья|третьей|третью|четвёртая|четвёртой|четвертая|четвертой|пятая|пятой|шестая|шестой|седьмая|седьмой|восьмая|восьмой|девятая|девятой|десятая|десятой)\s*сцен'
    matches = re.findall(ordinal_pattern, prompt, re.IGNORECASE)
    for match in matches:
        match_lower = match.lower()
        # Ищу совпадение в словаре
        for key, num in ordinal_map.items():
            if key in match_lower:
                found_numbers.append(num)
                break
    
    # ✅ Если нашли числа - берём максимальное (для "1 сцене ... 2 сцене" или "в первой ... во второй")
    if found_numbers:
        return max(found_numbers)
    
    return 3  # По умолчанию 3 сцены