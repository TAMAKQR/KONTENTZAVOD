"""Обработчик для создания видео"""
import asyncio
import json
import logging
import uuid
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from aiogram import Router, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import StateFilter
from generators.video_generator import VideoGenerator
from generators.video_stitcher import VideoStitcher
from generators.image_utils import ImageUploader
from integrations.airtable.airtable_logger import session_logger
from integrations.airtable.airtable_video_update import update_video_parameters

logger = logging.getLogger(__name__)
router = Router()


class VideoStates(StatesGroup):
    """Состояния для создания видео"""
    choosing_type = State()  # Выбор типа видео
    
    # Подпоток 1: Текст → Видео
    text_choosing_model = State()  # Выбор модели AI
    text_choosing_aspect_ratio = State()  # Выбор соотношения сторон
    text_choosing_duration = State()  # Выбор длительности
    text_waiting_prompt = State()  # Ввод промта
    text_processing_prompt = State()  # Gemini обработка промта
    text_confirming_scenes = State()  # Подтверждение сцен
    text_editing_scene = State()  # Редактирование отдельной сцены
    text_generating = State()  # Генерация видео
    
    # Подпоток 2: Текст + Фото → Видео
    text_photo_choosing_model = State()  # Выбор модели AI
    text_photo_choosing_aspect_ratio = State()  # Выбор соотношения сторон
    text_photo_choosing_duration = State()  # Выбор длительности
    text_photo_waiting_prompt = State()
    text_photo_waiting_photo = State()
    text_photo_confirming_scene_photo = State()  # Подтверждение фото для каждой сцены
    text_photo_generating = State()
    text_photo_editing_scene = State()  # Редактирование промта сцены
    text_photo_editing_scene_photo = State()  # Загрузка нового фото для сцены
    
    # Подпоток 3: Текст + Фото + AI → Видео
    text_photo_ai_choosing_model = State()  # Выбор модели (kling-v2.5-turbo-pro)
    text_photo_ai_choosing_aspect_ratio = State()  # Выбор соотношения сторон
    text_photo_ai_choosing_duration = State()  # Выбор длительности
    text_photo_ai_asking_reference = State()  # Вопрос о референсе
    text_photo_ai_waiting_reference = State()  # Загрузка референса
    text_photo_ai_waiting_prompt = State()  # Ввод промта
    text_photo_ai_processing_prompt = State()  # Gemini разбивает на сцены
    text_photo_ai_generating_photos = State()  # Генерация фото через google/nano-banana
    text_photo_ai_confirming_scenes = State()  # Подтверждение сцен с фото
    text_photo_ai_editing_scene = State()  # Редактирование сцены
    text_photo_ai_generating = State()  # Генерация видео


def get_video_type_buttons():
    """Получить кнопки выбора типа видео"""
    return [
        {"id": 1, "text": "📝 Текст", "callback": "video_text"},
        {"id": 2, "text": "📝 Текст + Фото", "callback": "video_text_photo"},
        {"id": 3, "text": "📝 Текст + Фото + AI", "callback": "video_text_photo_ai"}
    ]


@router.callback_query(lambda c: c.data == "video")
async def start_video_creation(callback: types.CallbackQuery, state: FSMContext):
    """Начало создания видео - выбор типа"""
    await callback.answer()
    await state.set_state(VideoStates.choosing_type)
    
    # Загружаем кнопки из БД
    buttons = get_video_type_buttons()
    
    # Создаём клавиатуру
    inline_keyboard = []
    for btn in buttons:
        inline_keyboard.append([
            InlineKeyboardButton(text=btn["text"], callback_data=btn["callback"])
        ])
    
    # Добавляем кнопку "Назад"
    inline_keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
    
    await callback.message.answer(
        "📹 Создание видео\n\n"
        "Выбери режим генерации:",
        reply_markup=keyboard
    )


# ==================== ПОДПОТОК 1: ТЕКСТ → ВИДЕО ====================

@router.callback_query(lambda c: c.data == "video_text")
async def start_text_video(callback: types.CallbackQuery, state: FSMContext):
    """Режим 1: Только текст - выбор модели AI"""
    from src.workflow_tracker import WorkflowTracker
    
    await callback.answer()
    
    # 🔄 Создание workflow для генерации видео
    user_id = callback.from_user.id
    session_id = f"video_{uuid.uuid4().hex[:12]}"
    start_time = time.time()
    
    tracker = WorkflowTracker()
    
    # Определение этапов workflow
    stages = [
        {"id": 1, "title": "⚙️ Выбор модели", "description": "Выбор AI модели для генерации"},
        {"id": 2, "title": "📐 Настройка параметров", "description": "Соотношение сторон, качество"},
        {"id": 3, "title": "✍️ Написание промпта", "description": "Описание желаемого видео"},
        {"id": 4, "title": "🤖 Обработка Gemini", "description": "Разбиение на сцены через AI"},
        {"id": 5, "title": "✅ Подтверждение сцен", "description": "Проверка и редактирование сцен"},
        {"id": 6, "title": "🎬 Генерация сцен", "description": "Создание видео через Replicate API"},
        {"id": 7, "title": "🎞️ Склеивание видео", "description": "Объединение всех сцен в одно видео"},
        {"id": 8, "title": "📤 Отправка результата", "description": "Доставка видео в Telegram"}
    ]
    
    # Запуск workflow
    workflow_id = tracker.start_workflow(user_id, "📹 Создание видео (Текст)", stages)
    
    # 📊 Логирование в Airtable
    await session_logger.log_session_start(
        user_id=user_id,
        session_id=session_id,
        video_type="text"
    )
    
    await state.update_data(workflow_id=workflow_id, session_id=session_id, start_time=start_time, video_type="text")
    
    # Первый этап - выбор модели
    tracker.update_stage(workflow_id, 1, "running", {"step": "Выбор AI модели"})
    
    await state.set_state(VideoStates.text_choosing_model)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎬 Kling v2.5 Turbo Pro", callback_data="model_kling_text")],
            [InlineKeyboardButton(text="🎥 Veo 3.1 Fast", callback_data="model_veo_text")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]
        ]
    )
    
    await callback.message.answer(
        "📝 Режим: Текст → Видео\n"
        "────────────────────────────────────\n\n"
        "Выбери AI модель для генерации:\n\n"
        "🎬 <b>Kling v2.5 Turbo Pro</b>\n"
        "   💰 $0.07/сек (~$0.70 за 10 сек)\n"
        "   ⭐ Бюджетный вариант\n\n"
        "🎥 <b>Veo 3.1 Fast</b>\n"
        "   💰 $0.15/сек (~$1.20 за 8 сек)\n"
        "   ⭐ Лучшее качество\n\n"
        "📊 <b>Следи за процессом:</b> http://localhost:3000/workflow",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data.startswith("model_") and c.data.endswith("_text"))
async def choose_text_model(callback: types.CallbackQuery, state: FSMContext):
    """Выбор модели для режима Текст"""
    from src.workflow_tracker import WorkflowTracker
    
    await callback.answer()
    
    model_map = {
        "model_kling_text": ("kling", "kwaivgi/kling-v2.5-turbo-pro"),
        "model_veo_text": ("veo", "google/veo-3.1-fast")
    }
    
    model_key, model_full = model_map.get(callback.data, ("kling", "kwaivgi/kling-v2.5-turbo-pro"))
    await state.update_data(model_key=model_key, model=model_full)
    
    # Обновление workflow - завершение этапа 1, начало этапа 2
    data = await state.get_data()
    workflow_id = data.get("workflow_id")
    session_id = data.get("session_id")
    
    if workflow_id:
        tracker = WorkflowTracker()
        tracker.update_stage(workflow_id, 1, "completed", {"model": model_key})
        tracker.update_stage(workflow_id, 2, "running", {"step": "Выбор соотношения сторон"})
    
    if session_id:
        model_for_airtable = "Kling" if model_key == "kling" else "Veo"
        await update_video_parameters(session_id, model=model_for_airtable)
    
    await state.set_state(VideoStates.text_choosing_aspect_ratio)
    
    model_names = {
        "kling": "🎬 Kling v2.5 Turbo Pro (5/10 сек)",
        "veo": "🎥 Veo 3.1 Fast (4/6/8 сек)"
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
    from src.workflow_tracker import WorkflowTracker
    
    await callback.answer()
    
    aspect_map = {
        "aspect_16_9_text": "16:9",
        "aspect_9_16_text": "9:16",
        "aspect_1_1_text": "1:1"
    }
    
    aspect_ratio = aspect_map.get(callback.data, "16:9")
    await state.update_data(aspect_ratio=aspect_ratio)
    
    data = await state.get_data()
    model_key = data.get("model_key", "kling")
    
    # Автоматически устанавливаем минимальную длительность в зависимости от модели
    if model_key == "kling":
        duration = 5
    else:  # veo
        duration = 4
    
    await state.update_data(duration_per_scene=duration)
    
    # Обновление workflow - завершение этапа 2 и 3, начало этапа 4
    workflow_id = data.get("workflow_id")
    session_id = data.get("session_id")
    
    if workflow_id:
        tracker = WorkflowTracker()
        tracker.update_stage(workflow_id, 2, "completed", {"aspect_ratio": aspect_ratio})
        tracker.update_stage(workflow_id, 3, "completed", {"duration": duration})
        tracker.update_stage(workflow_id, 4, "running", {"step": "Ожидание промпта от пользователя"})
    
    if session_id:
        await update_video_parameters(session_id, aspect_ratio=aspect_ratio, duration=duration)
    
    await state.set_state(VideoStates.text_waiting_prompt)
    
    aspect_names = {
        "16:9": "📺 16:9 (Горизонтальное)",
        "9:16": "📱 9:16 (Вертикальное)",
        "1:1": "⬜ 1:1 (Квадратное)"
    }
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]]
    )
    
    await callback.message.answer(
        f"✅ Параметры видео:\n"
        f"{'═' * 40}\n\n"
        f"🎬 Модель: {model_key.upper()}\n"
        f"📐 Соотношение: {aspect_names.get(aspect_ratio, aspect_ratio)}\n"
        f"⏱️  Длительность: <b>{duration} сек</b>\n\n"
        f"{'═' * 40}\n"
        f"📝 Теперь напиши описание видео:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data.startswith("duration_") and c.data.endswith("_text"))
async def choose_text_duration(callback: types.CallbackQuery, state: FSMContext):
    """Выбор длительности для режима Текст"""
    from src.workflow_tracker import WorkflowTracker
    
    await callback.answer()
    
    duration_map = {
        "duration_4_text": 4,
        "duration_5_text": 5,
        "duration_6_text": 6,
        "duration_8_text": 8,
        "duration_10_text": 10,
    }
    
    duration = duration_map.get(callback.data, 5)
    await state.update_data(duration_per_scene=duration)
    
    # Обновление workflow
    data = await state.get_data()
    workflow_id = data.get("workflow_id")
    if workflow_id:
        tracker = WorkflowTracker()
        tracker.update_stage(workflow_id, 3, "completed", {"duration": duration})
        tracker.update_stage(workflow_id, 4, "running", {"step": "Ожидание промпта от пользователя"})
    
    await state.set_state(VideoStates.text_waiting_prompt)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]]
    )
    
    await callback.message.answer(
        f"✅ Длительность выбрана: <b>{duration} сек</b>\n"
        f"{'═' * 40}\n\n"
        f"📝 Теперь напиши описание видео:",
        parse_mode="HTML",
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
    """Обработка текста для видео - отправка на обработку Gemini"""
    from src.workflow_tracker import WorkflowTracker
    
    data = await state.get_data()
    model_key = data.get("model_key", "kling")
    workflow_id = data.get("workflow_id")
    session_id = data.get("session_id")
    
    await state.update_data(prompt=message.text)
    await state.set_state(VideoStates.text_processing_prompt)
    
    # Обновление workflow - завершение этапа 3, начало этапа 4
    if workflow_id:
        tracker = WorkflowTracker()
        tracker.update_stage(workflow_id, 3, "completed", {"prompt_length": len(message.text)})
        tracker.update_stage(workflow_id, 4, "running", {"step": "Обработка через Gemini AI"})
    
    if session_id:
        await update_video_parameters(session_id, prompt=message.text[:500])
    
    input_text = message.text
    indented_input = "\n".join("    " + line for line in input_text.split("\n"))
    
    num_scenes = extract_num_scenes_from_prompt(message.text)
    
    processing_msg = await message.answer(
        f"⏳ Обработка промта через Gemini AI...\n"
        f"{'─' * 40}\n\n"
        f"📝 Ваш промт:\n\n{indented_input}\n\n"
        f"{'─' * 40}\n"
        f"🤖 Разбиваю на {num_scenes} сцены..."
    )
    
    try:
        generator = VideoGenerator()
        
        scenes_result = await generator.enhance_prompt_with_gemini(
            prompt=message.text,
            num_scenes=num_scenes
        )
        
        await state.update_data(
            scenes=scenes_result["scenes"],
            enhanced_prompt=scenes_result["enhanced_prompt"],
            current_scene_index=0
        )
        
        # Обновление workflow - завершение этапа 4, начало этапа 5
        if workflow_id:
            tracker = WorkflowTracker()
            tracker.update_stage(workflow_id, 4, "completed", {
                "num_scenes": len(scenes_result["scenes"]),
                "enhanced_prompt": scenes_result["enhanced_prompt"][:100]
            })
            tracker.update_stage(workflow_id, 5, "running", {"step": "Подтверждение сцен"})
        
        await state.set_state(VideoStates.text_confirming_scenes)
        
        await show_scene_for_confirmation(message, state, 0)
        
    except Exception as e:
        logger.error(f"❌ Ошибка обработки: {e}")
        
        # Ошибка в workflow
        if workflow_id:
            tracker = WorkflowTracker()
            tracker.error_workflow(workflow_id, f"Ошибка Gemini: {str(e)}", 4)
        
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
        
        scenes_result = await generator.enhance_prompt_with_gemini(
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
    from src.workflow_tracker import WorkflowTracker
    
    await state.set_state(VideoStates.text_generating)
    
    data = await state.get_data()
    scenes = data.get("scenes", [])
    model_key = data.get("model_key", "kling")
    aspect_ratio = data.get("aspect_ratio", "16:9")
    workflow_id = data.get("workflow_id")
    session_id = data.get("session_id")
    prompt = data.get("prompt", "")
    duration = data.get("duration", 5)
    
    # 📊 Логирование параметров генерации в Airtable
    if session_id:
        data = await state.get_data()
        video_type = data.get("video_type")
        enhanced_prompt = data.get("enhanced_prompt", "")
        prompt_data = {"enhanced_prompt": enhanced_prompt, "scenes": scenes}
        scenes_json = json.dumps(prompt_data, ensure_ascii=False, indent=2)[:2000]
        
        await session_logger.log_session_update(
            session_id=session_id,
            update_fields={
                "Model": model_key.capitalize(),
                "Aspect Ratio": aspect_ratio,
                "Duration": int(duration),
                "PromptAI": scenes_json,
                "Status": "Generating"
            },
            video_type=video_type
        )
    
    # Обновление workflow - завершение этапа 5, начало этапа 6
    if workflow_id:
        tracker = WorkflowTracker()
        tracker.update_stage(workflow_id, 5, "completed", {"all_scenes_confirmed": True})
        tracker.update_stage(workflow_id, 6, "running", {
            "step": "Генерация сцен через Replicate API",
            "num_scenes": len(scenes)
        })
    
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
        
        if session_id:
            await session_logger.log_session_update(
                session_id=session_id,
                video_type=video_type,
                update_fields={"Status": "Processing"}
            )
        
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
        
        # 📊 Логирование URL видео сцен в Airtable
        scene_videos_list = []
        for i, result in enumerate(scene_results):
            if result.get("status") == "success":
                scene_videos_list.append({
                    "scene": i + 1,
                    "url": result.get("video_url", "")
                })
        
        if session_id and scene_videos_list:
            await session_logger.log_scene_artifacts(
                session_id=session_id,
                video_type=video_type,
                scene_videos=scene_videos_list
            )
        
        # Обновление workflow - завершение этапа 6, начало этапа 7
        if workflow_id:
            tracker = WorkflowTracker()
            tracker.update_stage(workflow_id, 6, "completed", {
                "scenes_generated": len(video_paths),
                "total_scenes": len(scene_results)
            })
            tracker.update_stage(workflow_id, 7, "running", {"step": "Склеивание видео"})
        
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
        
        # Обновление workflow - завершение этапа 7, начало этапа 8
        if workflow_id:
            tracker = WorkflowTracker()
            tracker.update_stage(workflow_id, 7, "completed", {"final_video": final_video_path})
            tracker.update_stage(workflow_id, 8, "running", {"step": "Отправка в Telegram"})
        
        await generating_msg.delete()
        await message.answer_video(
            types.FSInputFile(final_video_path),
            caption="✅ Видео готово!\n\n🎬 С плавными переходами 0.5 сек"
        )
        
        # Завершение workflow - успешно
        if workflow_id:
            tracker = WorkflowTracker()
            tracker.update_stage(workflow_id, 8, "completed", {"delivered": True})
            tracker.complete_workflow(workflow_id, final_video_path)
        
        # 📊 Логирование успешного завершения в Airtable
        data = await state.get_data()
        session_id = data.get("session_id")
        start_time = data.get("start_time")
        video_type = data.get("video_type")
        if session_id and start_time:
            processing_time = time.time() - start_time
            await session_logger.log_session_complete(
                session_id=session_id,
                video_type=video_type,
                status="Completed",
                output_url=final_video_path,
                processing_time=processing_time
            )
        
        await stitcher.cleanup_temp_files()
        logger.info("✅ Генерация завершена успешно")
        
    except Exception as e:
        logger.error(f"❌ Ошибка генерации: {e}")
        
        # Ошибка в workflow
        if workflow_id:
            tracker = WorkflowTracker()
            tracker.error_workflow(workflow_id, f"Ошибка генерации: {str(e)}", 6)
        
        # 📊 Логирование ошибки в Airtable
        data = await state.get_data()
        session_id = data.get("session_id")
        video_type = data.get("video_type")
        if session_id:
            await session_logger.log_session_update(
                session_id=session_id,
                video_type=video_type,
                update_fields={
                    "Status": "Failed",
                    "Error Message": str(e)[:500]
                }
            )
        
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
    from src.workflow_tracker import WorkflowTracker
    
    await callback.answer()
    
    # 🔄 Создание workflow для режима Текст + Фото
    user_id = callback.from_user.id
    session_id = f"video_{uuid.uuid4().hex[:12]}"
    start_time = time.time()
    
    tracker = WorkflowTracker()
    
    # Определение этапов workflow
    stages = [
        {"id": 1, "title": "⚙️ Выбор модели", "description": "Выбор AI модели для генерации"},
        {"id": 2, "title": "📐 Настройка параметров", "description": "Соотношение сторон, качество"},
        {"id": 3, "title": "✍️ Написание промпта", "description": "Описание желаемого видео"},
        {"id": 4, "title": "📸 Загрузка фото", "description": "Загрузка изображений для сцен"},
        {"id": 5, "title": "✅ Подтверждение сцен", "description": "Проверка и редактирование сцен"},
        {"id": 6, "title": "🎬 Генерация сцен", "description": "Создание видео через Replicate API"},
        {"id": 7, "title": "🎞️ Склеивание видео", "description": "Объединение всех сцен в одно видео"},
        {"id": 8, "title": "📤 Отправка результата", "description": "Доставка видео в Telegram"}
    ]
    
    # Запуск workflow
    workflow_id = tracker.start_workflow(user_id, "📹 Создание видео (Текст + Фото)", stages)
    
    # 📊 Логирование в Airtable
    await session_logger.log_session_start(
        user_id=user_id,
        session_id=session_id,
        video_type="text_photo"
    )
    
    await state.update_data(workflow_id=workflow_id, session_id=session_id, start_time=start_time, video_type="text_photo")
    
    # Первый этап - выбор модели
    tracker.update_stage(workflow_id, 1, "running", {"step": "Выбор AI модели"})
    
    await state.set_state(VideoStates.text_photo_choosing_model)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎬 Kling v2.5 Turbo Pro", callback_data="model_kling_text_photo")],
            [InlineKeyboardButton(text="🎥 Veo 3.1 Fast", callback_data="model_veo_text_photo")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]
        ]
    )
    
    await callback.message.answer(
        "📝🖼️ Режим: Текст + Фото → Видео\n"
        "────────────────────────────────────\n\n"
        "Выбери AI модель для генерации:\n\n"
        "🎬 <b>Kling v2.5 Turbo Pro</b>\n"
        "   💰 $0.07/сек (~$0.70 за 10 сек)\n"
        "   ⭐ Бюджетный вариант\n\n"
        "🎥 <b>Veo 3.1 Fast</b>\n"
        "   💰 $0.15/сек (~$1.20 за 8 сек)\n"
        "   ⭐ Лучшее качество\n\n"
        "📊 <b>Следи за процессом:</b> http://localhost:3000/workflow",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data.startswith("model_") and c.data.endswith("_text_photo"))
async def choose_text_photo_model(callback: types.CallbackQuery, state: FSMContext):
    """Выбор модели для режима Текст+Фото"""
    await callback.answer()
    
    model_map = {
        "model_kling_text_photo": ("kling", "kwaivgi/kling-v2.5-turbo-pro"),
        "model_veo_text_photo": ("veo", "google/veo-3.1-fast")
    }
    
    model_key, model_full = model_map.get(callback.data, ("kling", "kwaivgi/kling-v2.5-turbo-pro"))
    await state.update_data(model_key=model_key, model=model_full)
    
    data = await state.get_data()
    session_id = data.get("session_id")
    
    if session_id:
        model_for_airtable = "Kling" if model_key == "kling" else "Veo"
        await update_video_parameters(session_id, model=model_for_airtable)
    
    await state.set_state(VideoStates.text_photo_choosing_aspect_ratio)
    
    model_names = {
        "kling": "🎬 Kling v2.5 Turbo Pro (5/10 сек)",
        "veo": "🎥 Veo 3.1 Fast (4/6/8 сек)"
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
    
    data = await state.get_data()
    model_key = data.get("model_key", "kling")
    session_id = data.get("session_id")
    
    # Автоматически устанавливаем минимальную длительность в зависимости от модели
    if model_key == "kling":
        duration = 5
    else:  # veo
        duration = 4
    
    await state.update_data(duration_per_scene=duration)
    
    if session_id:
        await update_video_parameters(session_id, aspect_ratio=aspect_ratio, duration=duration)
    
    await state.set_state(VideoStates.text_photo_waiting_prompt)
    
    aspect_names = {
        "16:9": "📺 16:9 (Горизонтальное)",
        "9:16": "📱 9:16 (Вертикальное)",
        "1:1": "⬜ 1:1 (Квадратное)"
    }
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]]
    )
    
    await callback.message.answer(
        f"✅ Параметры видео:\n"
        f"{'═' * 40}\n\n"
        f"🎬 Модель: {model_key.upper()}\n"
        f"📐 Соотношение: {aspect_names.get(aspect_ratio, aspect_ratio)}\n"
        f"⏱️  Длительность: <b>{duration} сек</b>\n\n"
        f"{'═' * 40}\n"
        f"📝 Теперь напиши описание видео:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data.startswith("duration_") and c.data.endswith("_text_photo"))
async def choose_text_photo_duration(callback: types.CallbackQuery, state: FSMContext):
    """Выбор длительности для режима Текст+Фото"""
    await callback.answer()
    
    duration_map = {
        "duration_4_text_photo": 4,
        "duration_5_text_photo": 5,
        "duration_6_text_photo": 6,
        "duration_8_text_photo": 8,
        "duration_10_text_photo": 10,
    }
    
    duration = duration_map.get(callback.data, 5)
    await state.update_data(duration_per_scene=duration)
    await state.set_state(VideoStates.text_photo_waiting_prompt)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]]
    )
    
    await callback.message.answer(
        f"✅ Длительность выбрана: <b>{duration} сек</b>\n"
        f"{'═' * 40}\n\n"
        f"📝 Теперь напиши описание видео:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.message(VideoStates.text_photo_waiting_prompt)
async def process_text_photo_prompt(message: types.Message, state: FSMContext):
    """Обработка текста для видео (Текст+Фото режим)"""
    from integrations.airtable.airtable_video_update import update_video_parameters
    
    data = await state.get_data()
    model_key = data.get("model_key", "kling")
    session_id = data.get("session_id")
    aspect_ratio = data.get("aspect_ratio", "16:9")
    duration = data.get("duration_per_scene", 5)
    
    await state.update_data(prompt=message.text)
    await state.set_state(VideoStates.text_processing_prompt)
    
    if session_id:
        model_for_airtable = "Kling" if model_key == "kling" else "Veo"
        await update_video_parameters(
            session_id, 
            model=model_for_airtable,
            aspect_ratio=aspect_ratio,
            duration=int(duration),
            prompt=message.text[:500]
        )
    
    input_text = message.text
    indented_input = "\n".join("    " + line for line in input_text.split("\n"))
    
    num_scenes = extract_num_scenes_from_prompt(message.text)
    
    processing_msg = await message.answer(
        f"⏳ Обработка промта через Gemini AI...\n"
        f"{'─' * 40}\n\n"
        f"📝 Ваш промт:\n\n{indented_input}\n\n"
        f"{'─' * 40}\n"
        f"🤖 Разбиваю на {num_scenes} сцены..."
    )
    
    try:
        generator = VideoGenerator()
        
        scenes_result = await generator.enhance_prompt_with_gemini(
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
        
        # 📊 Логирование параметров генерации в Airtable
        session_id = data.get("session_id")
        video_type = data.get("video_type")
        prompt = data.get("prompt", "")
        duration = data.get("duration_per_scene", 5)
        
        if session_id:
            enhanced_prompt = data.get("enhanced_prompt", "")
            prompt_data = {"enhanced_prompt": enhanced_prompt, "scenes": scenes}
            scenes_json = json.dumps(prompt_data, ensure_ascii=False, indent=2)[:2000]
            await session_logger.log_session_update(
                session_id=session_id,
                video_type=video_type,
                update_fields={
                    "Model": model_key.capitalize(),
                    "Aspect Ratio": aspect_ratio,
                    "Duration": int(duration),
                    "PromptAI": scenes_json,
                    "Status": "Generating"
                }
            )
        
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
        
        # 📊 Логирование URL видео сцен в Airtable
        scene_videos_list = []
        for i, result in enumerate(scene_results):
            if result.get("status") == "success":
                scene_videos_list.append({
                    "scene": i + 1,
                    "url": result.get("video_url", "")
                })
        
        if session_id and scene_videos_list:
            await session_logger.log_scene_artifacts(
                session_id=session_id,
                video_type=video_type,
                scene_videos=scene_videos_list
            )
        
        if session_id and scene_photos:
            scene_photos_list = []
            for i, url in scene_photos.items():
                scene_photos_list.append({
                    "scene": i + 1,
                    "url": url
                })
            await session_logger.log_scene_artifacts(
                session_id=session_id,
                video_type=video_type,
                scene_photos=scene_photos_list
            )
        
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
