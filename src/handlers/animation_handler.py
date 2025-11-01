"""Обработчик для анимирования картин"""
import logging
import asyncio
import json
import uuid
import time
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import google.generativeai as genai
from aiogram import Router, types
from aiogram.client.bot import Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from src.config import GEMINI_API_KEY
from generators.image_utils import ImageUploader
from integrations.airtable.airtable_logger import session_logger

logger = logging.getLogger(__name__)
router = Router()


async def enhance_animation_prompt(prompt: str) -> str:
    """Улучшает промт для анимирования видео через Google Gemini"""
    if not GEMINI_API_KEY:
        logger.warning("⚠️ GEMINI_API_KEY не найден, возвращаю оригинальный промт")
        return prompt
    
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        
        system_prompt = """Ты эксперт по созданию видео промтов для AI моделей видеогенерации (Kling, Sora, Veo).
Твоя задача - улучшить промт пользователя, добавив:
1. Больше деталей о движении камеры и динамике
2. Уточнение атмосферы и стиля (кинематография, освещение)
3. Детали персонажей/объектов
4. Временные параметры (день/ночь, погода)
5. Конкретные эффекты и переходы

Верни ТОЛЬКО улучшенный промт (на русском языке), без объяснений. Длина: 200-300 символов."""
        
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = await asyncio.to_thread(
            model.generate_content,
            f"{system_prompt}\n\nУлучши этот промт для видео:\n{prompt}"
        )
        
        enhanced = response.text.strip()
        logger.info(f"✅ Промт улучшен Gemini:\nОригинал: {prompt}\nУлучшенный: {enhanced}")
        return enhanced
        
    except Exception as e:
        logger.error(f"❌ Ошибка при улучшении промта Gemini: {e}")
        logger.warning(f"⚠️ Возвращаю оригинальный промт")
        return prompt


class AnimationStates(StatesGroup):
    """Состояния для анимирования картины - ОДНО видео, без разбиения на сцены"""
    choosing_model = State()              # Выбор модели AI
    choosing_aspect_ratio = State()       # Выбор соотношения сторон
    choosing_duration = State()           # Выбор длительности
    choosing_resolution = State()         # Выбор разрешения (только для Veo)
    choosing_audio = State()              # Выбор генерации звука (только для Veo)
    choosing_image_option = State()       # Загружать ли изображение?
    waiting_for_image = State()           # Если да - получить изображение
    waiting_for_prompt = State()          # Основной промт
    waiting_for_negative_prompt = State() # Отрицательный промт (опционально)
    choosing_enhance_option = State()     # Улучшать ли с ИИ?
    reviewing_enhanced_prompt = State()   # Просмотр и редактирование улучшенного промта
    editing_prompt = State()              # Редактирование промта
    generating = State()                  # Генерация видео


@router.callback_query(lambda c: c.data == "animation")
async def start_animation(callback: types.CallbackQuery, state: FSMContext):
    """Начало анимирования картины - выбор модели AI"""
    from src.workflow_tracker import WorkflowTracker
    
    await callback.answer()
    
    # 🔄 Создание workflow с самого начала
    user_id = callback.from_user.id
    session_id = f"animation_{uuid.uuid4().hex[:12]}"
    start_time = time.time()
    
    # Инициализация WorkflowTracker
    tracker = WorkflowTracker()
    
    # Определение ВСЕХ этапов workflow
    stages = [
        {"id": 1, "title": "⚙️ Настройка параметров", "description": "Выбор модели, длительности, разрешения"},
        {"id": 2, "title": "📸 Загрузка изображения", "description": "Загрузка картинки для анимирования"},
        {"id": 3, "title": "✍️ Написание промпта", "description": "Описание желаемой анимации"},
        {"id": 4, "title": "🤖 Улучшение промпта", "description": "Обработка через Gemini AI"},
        {"id": 5, "title": "🎬 Генерация видео", "description": "Создание видео через Replicate API"},
        {"id": 6, "title": "⏳ Ожидание результата", "description": "Replicate обрабатывает запрос"},
        {"id": 7, "title": "📥 Скачивание видео", "description": "Загрузка готового видео"},
        {"id": 8, "title": "📤 Отправка в Telegram", "description": "Доставка результата пользователю"}
    ]
    
    # Запуск workflow (метод сам создает и возвращает workflow_id)
    workflow_id = tracker.start_workflow(user_id, "🎨 Анимация картинки", stages)
    
    # 📊 Логирование в Airtable
    await session_logger.log_session_start(
        user_id=user_id,
        session_id=session_id,
        video_type="animation"
    )
    
    # Сохраняем workflow_id в state
    await state.update_data(workflow_id=workflow_id, session_id=session_id, start_time=start_time, video_type="animation")
    
    # Первый этап - выбор параметров
    tracker.update_stage(workflow_id, 1, "running", {"step": "Выбор модели AI"})
    
    await state.set_state(AnimationStates.choosing_model)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎬 Kling v2.5 Turbo Pro", callback_data="anim_model_kling")],
            [InlineKeyboardButton(text="🎥 Veo 3.1 Fast", callback_data="anim_model_veo")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]
        ]
    )
    
    await callback.message.answer(
        "🎨 Анимирование картины\n"
        "────────────────────────────────────\n\n"
        "Выбери AI модель для анимирования:\n\n"
        "🎬 <b>Kling v2.5 Turbo Pro</b>\n"
        "   💰 $0.07/сек (~$0.70 за 10 сек)\n"
        "   ⭐ Бюджетный вариант\n"
        "   ✅ Хорошее качество\n\n"
        "🎥 <b>Veo 3.1 Fast</b>\n"
        "   💰 $0.15/сек (~$1.20 за 8 сек)\n"
        "   ⭐ Лучшее качество\n"
        "   ✅ Звук и 1080p поддержка\n\n"
        "📊 <b>Следи за процессом:</b> http://localhost:3000/workflow",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data.startswith("anim_model_"))
async def choose_animation_model(callback: types.CallbackQuery, state: FSMContext):
    """Выбор модели для анимирования"""
    from src.workflow_tracker import WorkflowTracker
    
    await callback.answer()
    
    model_map = {
        "anim_model_kling": ("kwaivgi/kling-v2.5-turbo-pro", "🎬 Kling v2.5 Turbo Pro"),
        "anim_model_veo": ("google/veo-3.1-fast", "🎥 Veo 3.1 Fast")
    }
    
    model, model_name = model_map.get(callback.data, ("", ""))
    await state.update_data(model=model, model_name=model_name)
    
    # Обновление workflow
    data = await state.get_data()
    if "workflow_id" in data:
        tracker = WorkflowTracker()
        tracker.update_stage(data["workflow_id"], 1, "running", {"step": "Выбор соотношения сторон", "model": model_name})
    
    await state.set_state(AnimationStates.choosing_aspect_ratio)
    
    # Выбор соотношения сторон (зависит от модели)
    is_veo = "veo" in model.lower()
    
    if is_veo:
        # Veo поддерживает только 16:9 и 9:16
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="16:9 (Горизонтальное)", callback_data="anim_aspect_169")],
                [InlineKeyboardButton(text="9:16 (Вертикальное)", callback_data="anim_aspect_916")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]
            ]
        )
    else:
        # Kling поддерживает 16:9, 9:16 и 1:1
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="16:9 (Горизонтальное)", callback_data="anim_aspect_169")],
                [InlineKeyboardButton(text="9:16 (Вертикальное)", callback_data="anim_aspect_916")],
                [InlineKeyboardButton(text="1:1 (Квадрат)", callback_data="anim_aspect_11")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]
            ]
        )
    
    await callback.message.answer(
        f"✅ Модель выбрана: {model_name}\n"
        f"────────────────────────────────────\n\n"
        f"📐 Выбери соотношение сторон для видео:",
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data.startswith("anim_aspect_"))
async def choose_aspect_ratio(callback: types.CallbackQuery, state: FSMContext):
    """Выбор соотношения сторон"""
    await callback.answer()
    
    aspect_map = {
        "anim_aspect_169": ("16:9", "16:9 (Горизонтальное)"),
        "anim_aspect_916": ("9:16", "9:16 (Вертикальное)"),
        "anim_aspect_11": ("1:1", "1:1 (Квадрат)")
    }
    
    aspect, aspect_name = aspect_map.get(callback.data, ("16:9", ""))
    await state.update_data(aspect_ratio=aspect)
    await state.set_state(AnimationStates.choosing_duration)
    
    # Получаем модель чтобы показать правильные варианты длительности
    data = await state.get_data()
    model = data.get("model", "")
    is_veo = "veo" in model.lower()
    
    # Выбор длительности (зависит от модели)
    if is_veo:
        # Veo поддерживает только 4, 6, 8 секунд
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⏱️ 4 секунды", callback_data="anim_duration_4")],
                [InlineKeyboardButton(text="⏱️ 6 секунд", callback_data="anim_duration_6")],
                [InlineKeyboardButton(text="⏱️ 8 секунд (Рекомендуется)", callback_data="anim_duration_8")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]
            ]
        )
    else:
        # Kling поддерживает 5, 10 секунд
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⏱️ 5 секунд", callback_data="anim_duration_5")],
                [InlineKeyboardButton(text="⏱️ 10 секунд", callback_data="anim_duration_10")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]
            ]
        )
    
    await callback.message.answer(
        f"✅ Соотношение сторон: {aspect_name}\n"
        f"────────────────────────────────────\n\n"
        f"⏱️ Выбери длительность видео:",
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data.startswith("anim_duration_"))
async def choose_duration(callback: types.CallbackQuery, state: FSMContext):
    """Выбор длительности"""
    await callback.answer()
    
    duration_map = {
        "anim_duration_4": 4,
        "anim_duration_5": 5,
        "anim_duration_6": 6,
        "anim_duration_8": 8,
        "anim_duration_10": 10
    }
    
    duration = duration_map.get(callback.data, 5)
    await state.update_data(duration=duration)
    
    # Проверяем модель
    data = await state.get_data()
    model = data.get("model", "")
    is_veo = "veo" in model.lower()
    
    if is_veo:
        # Для Veo переходим к выбору разрешения
        await state.set_state(AnimationStates.choosing_resolution)
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📺 720p (HD)", callback_data="anim_resolution_720p")],
                [InlineKeyboardButton(text="📺 1080p (Full HD) ⭐", callback_data="anim_resolution_1080p")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]
            ]
        )
        
        await callback.message.answer(
            f"✅ Длительность: {duration} сек\n"
            f"────────────────────────────────────\n\n"
            f"📺 Выбери разрешение видео:",
            reply_markup=keyboard
        )
    else:
        # Для Kling сразу переходим к выбору изображения
        # Устанавливаем дефолтные значения для параметров, которые используются только в Veo
        await state.update_data(resolution="1080p", generate_audio=True)
        await state.set_state(AnimationStates.choosing_image_option)
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Загрузить картину", callback_data="anim_image_yes")],
                [InlineKeyboardButton(text="❌ Генерировать без картины", callback_data="anim_image_no")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]
            ]
        )
        
        await callback.message.answer(
            f"✅ Длительность: {duration} сек\n"
            f"────────────────────────────────────\n\n"
            f"🖼️ Хочешь загрузить исходное изображение для анимирования?\n"
            f"(Можно пропустить и генерировать видео только из промта)",
            reply_markup=keyboard
        )


@router.callback_query(lambda c: c.data.startswith("anim_resolution_"))
async def choose_resolution(callback: types.CallbackQuery, state: FSMContext):
    """Выбор разрешения (только для Veo)"""
    await callback.answer()
    
    resolution_map = {
        "anim_resolution_720p": "720p",
        "anim_resolution_1080p": "1080p"
    }
    
    resolution = resolution_map.get(callback.data, "1080p")
    await state.update_data(resolution=resolution)
    await state.set_state(AnimationStates.choosing_audio)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔊 Со звуком ⭐", callback_data="anim_audio_yes")],
            [InlineKeyboardButton(text="🔇 Без звука", callback_data="anim_audio_no")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]
        ]
    )
    
    await callback.message.answer(
        f"✅ Разрешение: {resolution}\n"
        f"────────────────────────────────────\n\n"
        f"🔊 Генерировать звук для видео?",
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data.startswith("anim_audio_"))
async def choose_audio(callback: types.CallbackQuery, state: FSMContext):
    """Выбор генерации звука (только для Veo)"""
    await callback.answer()
    
    audio_map = {
        "anim_audio_yes": (True, "Со звуком"),
        "anim_audio_no": (False, "Без звука")
    }
    
    generate_audio, audio_text = audio_map.get(callback.data, (True, "Со звуком"))
    await state.update_data(generate_audio=generate_audio)
    await state.set_state(AnimationStates.choosing_image_option)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Загрузить картину", callback_data="anim_image_yes")],
            [InlineKeyboardButton(text="❌ Генерировать без картины", callback_data="anim_image_no")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]
        ]
    )
    
    await callback.message.answer(
        f"✅ Звук: {audio_text}\n"
        f"────────────────────────────────────\n\n"
        f"🖼️ Хочешь загрузить исходное изображение для анимирования?\n"
        f"(Можно пропустить и генерировать видео только из промта)",
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data == "anim_image_yes")
async def choose_image_yes(callback: types.CallbackQuery, state: FSMContext):
    """Пользователь хочет загрузить изображение"""
    await callback.answer()
    await state.set_state(AnimationStates.waiting_for_image)
    
    await callback.message.answer(
        "📤 Отправь картину, которую ты хочешь анимировать:\n"
        "(PNG, JPG или другой формат изображения)"
    )


@router.callback_query(lambda c: c.data == "anim_image_no")
async def choose_image_no(callback: types.CallbackQuery, state: FSMContext):
    """Пользователь хочет генерировать без изображения"""
    await callback.answer()
    await state.update_data(image_url=None)
    await state.set_state(AnimationStates.waiting_for_prompt)
    
    await callback.message.answer(
        "✅ OK, будем генерировать видео только из промта\n"
        "────────────────────────────────────\n\n"
        "📝 Напиши описание видео, которое ты хочешь создать:\n\n"
        "Пример: 'Красивый пейзаж горных вершин с облаками'"
    )


@router.message(AnimationStates.waiting_for_image)
async def process_animation_image(message: types.Message, state: FSMContext):
    """Обработка загруженного изображения"""
    if message.photo:
        try:
            # Показываем статус загрузки
            processing_msg = await message.answer("⏳ Загружаю картину на облако...")
            
            logger.info(f"📸 DEBUG: Начинаю загрузку фото через ImageUploader...")
            logger.info(f"   Telegram file_id: {message.photo[-1].file_id}")
            
            # Скачиваем фото с Telegram и загружаем на ImgBB
            uploader = ImageUploader()
            image_url = await uploader.process_telegram_photo(
                message.bot,
                message.photo[-1].file_id,
                photo_name="animation_frame"
            )
            
            logger.info(f"📸 DEBUG: process_telegram_photo() вернул: {image_url}")
            
            if image_url:
                # Сохраняем URL облака (не file_id!)
                await state.update_data(image_url=image_url)
                logger.info(f"✅ Получено изображение для анимации: {image_url}")
                logger.info(f"✅ image_url сохранено в FSM")
                
                # VERIFY - проверяем что сохранилось
                state_data = await state.get_data()
                saved_url = state_data.get("image_url")
                logger.info(f"🔍 VERIFY: Проверяю что было сохранено в FSM")
                logger.info(f"   saved_url = {saved_url}")
                logger.info(f"   saved_url == image_url? {saved_url == image_url}")
                logger.info(f"   saved_url type = {type(saved_url).__name__}")
                
                # Обновление workflow - этап 2 завершен
                from src.workflow_tracker import WorkflowTracker
                if "workflow_id" in state_data:
                    tracker = WorkflowTracker()
                    tracker.update_stage(state_data["workflow_id"], 1, "completed", {"step": "Параметры настроены"})
                    tracker.update_stage(state_data["workflow_id"], 2, "completed", {"image_url": image_url[:50] + "..."})
                    tracker.update_stage(state_data["workflow_id"], 3, "running", {"step": "Ожидание промпта"})
                
                await processing_msg.delete()
                await state.set_state(AnimationStates.waiting_for_prompt)
                await message.answer(
                    "✅ Картина получена и загружена!\n"
                    "────────────────────────────────────\n\n"
                    "📝 Теперь напиши описание анимации:\n\n"
                    "Пример: 'волнующееся море с закатом', 'летящие птицы'"
                )
            else:
                logger.error(f"❌ ImageUploader.process_telegram_photo() вернул None!")
                await processing_msg.edit_text("❌ Ошибка при загрузке фото. Попробуй еще раз.")
                return
                
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки фото: {e}")
            await message.answer(f"❌ Ошибка: {str(e)}\n\nПопробуй еще раз или напиши /отмена")
            return
    else:
        await message.answer("❌ Пожалуйста, отправь изображение в формате фото")


@router.message(AnimationStates.waiting_for_prompt)
async def process_animation_prompt(message: types.Message, state: FSMContext):
    """Обработка основного промта"""
    from src.workflow_tracker import WorkflowTracker
    
    prompt = message.text
    await state.update_data(prompt=prompt)
    
    # Обновление workflow - этап 3 завершен
    data = await state.get_data()
    if "workflow_id" in data:
        tracker = WorkflowTracker()
        tracker.update_stage(data["workflow_id"], 3, "completed", {"prompt": prompt[:50] + "..."})
    
    await state.set_state(AnimationStates.waiting_for_negative_prompt)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Добавить отрицательный промт", callback_data="anim_neg_yes")],
            [InlineKeyboardButton(text="❌ Пропустить", callback_data="anim_neg_no")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]
        ]
    )
    
    await message.answer(
        f"✅ Промт получен: '{prompt[:60]}...'\n"
        f"────────────────────────────────────\n\n"
        f"❌ Хочешь добавить отрицательный промт?\n"
        f"(Что НЕ должно быть в видео)",
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data == "anim_neg_yes")
async def add_negative_prompt(callback: types.CallbackQuery, state: FSMContext):
    """Пользователь хочет добавить отрицательный промт"""
    await callback.answer()
    await state.set_state(AnimationStates.waiting_for_negative_prompt)
    
    await callback.message.answer(
        "❌ Напиши что НЕ должно быть в видео:\n\n"
        "Пример: 'размытое, низкое качество, артефакты'"
    )


@router.callback_query(lambda c: c.data == "anim_neg_no")
async def skip_negative_prompt(callback: types.CallbackQuery, state: FSMContext):
    """Пропустить отрицательный промт"""
    await callback.answer()
    await state.update_data(negative_prompt="")
    await state.set_state(AnimationStates.choosing_enhance_option)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✨ Улучшить с помощью ИИ", callback_data="anim_enhance_yes")],
            [InlineKeyboardButton(text="❌ Использовать как есть", callback_data="anim_enhance_no")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]
        ]
    )
    
    await callback.message.answer(
        "✅ Отрицательный промт пропущен\n"
        "────────────────────────────────────\n\n"
        "✨ Хочешь улучшить промт с помощью ИИ?\n"
        "(ИИ добавит детали и улучшит качество описания)",
        reply_markup=keyboard
    )


@router.message(AnimationStates.waiting_for_negative_prompt)
async def process_negative_prompt(message: types.Message, state: FSMContext):
    """Обработка отрицательного промта"""
    negative_prompt = message.text
    await state.update_data(negative_prompt=negative_prompt)
    await state.set_state(AnimationStates.choosing_enhance_option)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✨ Улучшить с помощью ИИ", callback_data="anim_enhance_yes")],
            [InlineKeyboardButton(text="❌ Использовать как есть", callback_data="anim_enhance_no")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]
        ]
    )
    
    await message.answer(
        f"✅ Отрицательный промт: '{negative_prompt[:50]}...'\n"
        f"────────────────────────────────────\n\n"
        f"✨ Хочешь улучшить основной промт с помощью ИИ?",
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data == "anim_enhance_yes")
async def enhance_prompt_yes(callback: types.CallbackQuery, state: FSMContext):
    """Улучшить промт через ИИ"""
    await callback.answer()
    await state.set_state(AnimationStates.reviewing_enhanced_prompt)
    
    data = await state.get_data()
    original_prompt = data.get("prompt", "")
    
    msg = await callback.message.answer(
        f"✨ Улучшаю промт через ИИ...\n"
        f"⏳ Это займет несколько секунд..."
    )
    
    # Улучшаем промт через Google Gemini
    enhanced_prompt = await enhance_animation_prompt(original_prompt)
    
    # Сохраняем улучшенный промт в состояние
    await state.update_data(
        original_prompt=original_prompt,
        enhanced_prompt=enhanced_prompt
    )
    
    # Показываем результат улучшения с кнопками для управления
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✨ Регенерировать", callback_data="anim_regen_prompt")],
            [InlineKeyboardButton(text="✏️ Редактировать", callback_data="anim_edit_prompt")],
            [InlineKeyboardButton(text="✅ Принять", callback_data="anim_accept_prompt")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="anim_reject_prompt")]
        ]
    )
    
    if enhanced_prompt != original_prompt:
        await callback.message.answer(
            f"✅ Промт улучшен!\n\n"
            f"📝 <b>Оригинал:</b>\n<code>{original_prompt}</code>\n\n"
            f"✨ <b>Улучшенный:</b>\n<code>{enhanced_prompt}</code>\n\n"
            f"────────────────────────────────────\n"
            f"Что дальше?",
            parse_mode="HTML",
            reply_markup=keyboard
        )
    else:
        await callback.message.answer(
            f"⚠️ Не удалось улучшить промт через ИИ\n\n"
            f"📝 <b>Используется оригинальный промт:</b>\n<code>{original_prompt}</code>\n\n"
            f"────────────────────────────────────\n"
            f"Что дальше?",
            parse_mode="HTML",
            reply_markup=keyboard
        )


@router.callback_query(lambda c: c.data == "anim_enhance_no")
async def enhance_prompt_no(callback: types.CallbackQuery, state: FSMContext):
    """Использовать промт как есть"""
    await callback.answer()
    await state.set_state(AnimationStates.generating)
    await start_generation(callback, state)


@router.callback_query(lambda c: c.data == "anim_regen_prompt")
async def regenerate_prompt(callback: types.CallbackQuery, state: FSMContext):
    """Регенерировать (переулучшить) промт еще раз"""
    await callback.answer()
    
    data = await state.get_data()
    current_prompt = data.get("enhanced_prompt", data.get("prompt", ""))
    
    # Удаляем старое сообщение с кнопками
    try:
        await callback.message.delete()
    except:
        pass
    
    msg = await callback.message.answer(
        f"✨ Переулучшаю промт через ИИ...\n"
        f"⏳ Это займет несколько секунд..."
    )
    
    # Еще раз улучшаем (на основе уже улучшенного)
    re_enhanced_prompt = await enhance_animation_prompt(current_prompt)
    
    # Обновляем состояние
    await state.update_data(enhanced_prompt=re_enhanced_prompt)
    
    # Показываем новый результат
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✨ Регенерировать еще", callback_data="anim_regen_prompt")],
            [InlineKeyboardButton(text="✏️ Редактировать", callback_data="anim_edit_prompt")],
            [InlineKeyboardButton(text="✅ Принять", callback_data="anim_accept_prompt")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="anim_reject_prompt")]
        ]
    )
    
    await callback.message.answer(
        f"✅ Промт переулучшен!\n\n"
        f"✨ <b>Новый вариант:</b>\n<code>{re_enhanced_prompt}</code>\n\n"
        f"────────────────────────────────────\n"
        f"Что дальше?",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data == "anim_edit_prompt")
async def edit_prompt(callback: types.CallbackQuery, state: FSMContext):
    """Перейти в режим редактирования промта"""
    await callback.answer()
    await state.set_state(AnimationStates.editing_prompt)
    
    data = await state.get_data()
    enhanced_prompt = data.get("enhanced_prompt", data.get("prompt", ""))
    
    await callback.message.answer(
        f"✏️ Редактирование промта\n"
        f"────────────────────────────────────\n\n"
        f"📝 Текущий промт:\n<code>{enhanced_prompt}</code>\n\n"
        f"Отправь новый текст промта, который ты хочешь использовать:",
        parse_mode="HTML"
    )


@router.message(AnimationStates.editing_prompt)
async def process_edited_prompt(message: types.Message, state: FSMContext):
    """Обработка отредактированного промта"""
    edited_prompt = message.text
    
    # Сохраняем отредактированный промт
    await state.update_data(enhanced_prompt=edited_prompt)
    await state.set_state(AnimationStates.reviewing_enhanced_prompt)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✨ Регенерировать", callback_data="anim_regen_prompt")],
            [InlineKeyboardButton(text="✏️ Редактировать еще раз", callback_data="anim_edit_prompt")],
            [InlineKeyboardButton(text="✅ Принять", callback_data="anim_accept_prompt")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="anim_reject_prompt")]
        ]
    )
    
    await message.answer(
        f"✅ Промт обновлен!\n\n"
        f"📝 <b>Новый промт:</b>\n<code>{edited_prompt}</code>\n\n"
        f"────────────────────────────────────\n"
        f"Что дальше?",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data == "anim_accept_prompt")
async def accept_prompt(callback: types.CallbackQuery, state: FSMContext):
    """Принять улучшенный промт и начать генерацию"""
    await callback.answer()
    
    data = await state.get_data()
    final_prompt = data.get("enhanced_prompt", data.get("prompt", ""))
    
    # Обновляем основной промт на финальный
    await state.update_data(prompt=final_prompt)
    await state.set_state(AnimationStates.generating)
    
    await callback.message.answer("✅ Промт принят! Начинаю генерацию видео...")
    await start_generation(callback, state)


@router.callback_query(lambda c: c.data == "anim_reject_prompt")
async def reject_prompt(callback: types.CallbackQuery, state: FSMContext):
    """Отклонить улучшение и вернуться к оригиналу"""
    await callback.answer()
    
    data = await state.get_data()
    original_prompt = data.get("original_prompt", data.get("prompt", ""))
    
    # Возвращаемся к оригиналу
    await state.update_data(prompt=original_prompt, enhanced_prompt=None)
    await state.set_state(AnimationStates.choosing_enhance_option)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✨ Улучшить с помощью ИИ еще раз", callback_data="anim_enhance_yes")],
            [InlineKeyboardButton(text="❌ Использовать оригинал как есть", callback_data="anim_enhance_no")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]
        ]
    )
    
    await callback.message.answer(
        f"❌ Отменено. Вернулись к оригинальному промту.\n\n"
        f"📝 <b>Оригинал:</b>\n<code>{original_prompt}</code>\n\n"
        f"────────────────────────────────────\n"
        f"✨ Хочешь попробовать улучшить еще раз?",
        parse_mode="HTML",
        reply_markup=keyboard
    )


async def start_generation(callback: types.CallbackQuery, state: FSMContext):
    """Начинаем генерацию видео"""
    data = await state.get_data()
    
    model = data.get("model", "kling")  # kling, veo
    model_name = data.get("model_name", "Unknown")
    aspect_ratio = data.get("aspect_ratio", "16:9")
    duration = data.get("duration", 5)
    prompt = data.get("prompt", "")
    negative_prompt = data.get("negative_prompt", "")
    image_url = data.get("image_url")  # URL облака, не file_id!
    resolution = data.get("resolution", "1080p")  # Для Veo
    generate_audio = data.get("generate_audio", True)  # Для Veo
    workflow_id = data.get("workflow_id")  # 🔄 Получаем workflow_id
    
    logger.info(f"📊 DEBUG: image_url из FSM = {image_url}")  # 👈 ДЛЯ ОТЛАДКИ
    
    # Проверяем модель
    is_veo = "veo" in model.lower()
    
    # Рассчитываем стоимость
    price_per_second = 0.15 if is_veo else 0.07  # Veo: $0.15/сек, Kling: $0.07/сек
    total_cost = duration * price_per_second
    
    # Подготавливаем информацию о генерации
    summary = (
        f"🎬 ПАРАМЕТРЫ ВИДЕО\n"
        f"────────────────────────────────────\n"
        f"🎨 Модель: {model_name}\n"
        f"📐 Соотношение сторон: {aspect_ratio}\n"
        f"⏱️ Длительность: {duration} сек\n"
    )
    
    if is_veo:
        summary += f"📺 Разрешение: {resolution}\n"
        summary += f"🔊 Звук: {'Да' if generate_audio else 'Нет'}\n"
    
    summary += f"📝 Промт: {prompt[:70]}{'...' if len(prompt) > 70 else ''}\n"
    
    if negative_prompt:
        summary += f"❌ Отрицательный промт: {negative_prompt[:50]}{'...' if len(negative_prompt) > 50 else ''}\n"
    
    if image_url:
        summary += f"🖼️ Исходное изображение: ✅ Загружено\n"
    
    summary += (
        f"────────────────────────────────────\n"
        f"💰 СТОИМОСТЬ: ~${total_cost:.2f}\n"
        f"   ({duration} сек × ${price_per_second}/сек)\n"
        f"────────────────────────────────────\n\n"
        f"⏳ Генерирую видео...\n"
        f"⏰ Это может занять 2-5 минут"
    )
    
    await callback.message.answer(summary)
    logger.info(f"🎬 Начало генерации видео: {model}")
    logger.info(f"   📝 Промт: {prompt[:100]}")
    logger.info(f"   ❌ Отр. промт: {negative_prompt[:100] if negative_prompt else 'N/A'}")
    logger.info(f"   🖼️ Фото загружено: {image_url[:80] if image_url else 'Нет (text-to-video режим)'}...")
    logger.info(f"   📺 Resolution: {resolution}")
    logger.info(f"   🔊 Audio: {generate_audio}")
    
    # 🔴 ФИНАЛЬНАЯ ПРОВЕРКА перед отправкой в background task
    logger.info(f"🔍 ФИНАЛЬНАЯ ПРОВЕРКА ПРИ СОЗДАНИИ TASK:")
    logger.info(f"   ✓ user_id = {callback.from_user.id}")
    logger.info(f"   ✓ model = {model}")
    logger.info(f"   ✓ prompt = {prompt[:50]}...")
    logger.info(f"   ✓ duration = {duration}")
    logger.info(f"   ✓ aspect_ratio = {aspect_ratio}")
    logger.info(f"   ✓ resolution = {resolution}")
    logger.info(f"   ✓ generate_audio = {generate_audio}")
    logger.info(f"   ✓ negative_prompt = {negative_prompt[:50] if negative_prompt else 'N/A'}...")
    logger.info(f"   ✓ image_url = {image_url} (тип: {type(image_url).__name__}, длина: {len(image_url) if image_url else 'N/A'})")
    
    # ✅ Запускаем генерацию в фоновом режиме асинхронно (с фото или без)
    logger.info(f"✅ ОТПРАВЛЯЮ TASK с image_url: {image_url}")
    asyncio.create_task(generate_video_async(
        callback.from_user.id,
        callback.bot,
        model,
        prompt,
        duration,
        aspect_ratio,
        negative_prompt,
        image_url,
        resolution,
        generate_audio,
        workflow_id  # 🔄 Передаем workflow_id
    ))
    
    await state.clear()


async def generate_video_async(
    user_id: int,
    bot: Bot,
    model: str,
    prompt: str,
    duration: int,
    aspect_ratio: str,
    negative_prompt: str,
    image_url: Optional[str] = None,
    resolution: str = "1080p",
    generate_audio: bool = True,
    workflow_id: Optional[str] = None  # 🔄 Добавляем параметр workflow_id
):
    """Асинхронная генерация видео в фоновом режиме"""
    try:
        from video_generator import VideoGenerator
        from video_stitcher import VideoStitcher
        from pathlib import Path
        from src.workflow_tracker import WorkflowTracker
        
        logger.info(f"🎬 [ФОНОВАЯ ГЕНЕРАЦИЯ] Начало для пользователя {user_id}")
        logger.info(f"📊 image_url получен в generate_video_async: {image_url}")
        logger.info(f"📊 Тип image_url: {type(image_url)}")
        logger.info(f"📊 Является ли пустым: {not image_url}")
        logger.info(f"📺 Resolution: {resolution}")
        logger.info(f"🔊 Generate audio: {generate_audio}")
        
        generator = VideoGenerator()
        stitcher = VideoStitcher()
        
        # 🔄 Инициализация WorkflowTracker
        tracker = WorkflowTracker()
        
        # Если workflow_id не передан - создаем новый (обратная совместимость)
        if not workflow_id:
            stages = [
                {"id": 1, "title": "📝 Получение параметров", "description": f"Модель: {model}, Duration: {duration}s"},
                {"id": 2, "title": "🎬 Генерация через Replicate API", "description": f"Prompt: {prompt[:50]}..."},
                {"id": 3, "title": "⏳ Ожидание результата", "description": "Replicate обрабатывает запрос"},
                {"id": 4, "title": "📥 Скачивание видео", "description": "Загрузка с сервера Replicate"},
                {"id": 5, "title": "📤 Отправка в Telegram", "description": "Доставка пользователю"}
            ]
            workflow_id = tracker.start_workflow(user_id=user_id, title=f"🎞️ Анимация картинки ({model})", stages=stages)
            tracker.update_stage(workflow_id, 1, "completed")
        
        # Workflow уже создан в start_animation, продолжаем с этапа 4 (Gemini улучшение промпта)
        # Этап 4: Улучшение промпта (пропускаем если не нужно)
        # Этап 5: Генерация через Replicate API
        tracker.update_stage(workflow_id, 4, "completed", {"step": "Промпт готов"})
        tracker.update_stage(workflow_id, 5, "running", {"progress": 0})
        logger.info(f"🎬 Отправляю запрос на генерацию видео...")
        logger.info(f"📊 DEBUG: image_url перед generate_scene = {image_url}")  # 👈 ДЛЯ ОТЛАДКИ
        
        result = await generator.generate_scene(
            prompt=prompt,
            model=model,
            duration=duration,
            aspect_ratio=aspect_ratio,
            start_image_url=image_url,  # Передаем URL облака с загруженным изображением (опционально)
            scene_number=1,
            require_image=False,  # ✅ Фото опционально - работает и text-to-video
            resolution=resolution,  # Для Veo
            generate_audio=generate_audio,  # Для Veo
            negative_prompt=negative_prompt  # Для Veo и Kling
        )
        
        tracker.update_stage(2, "completed")
        
        # 🧪 ТЕСТОВЫЙ РЕЖИМ - показываем JSON и останавливаемся
        if result.get("status") == "test_mode":
            json_payload = result.get("json_payload", {})
            model_id = result.get("model_id", "")
            
            message = (
                f"🧪 <b>ТЕСТОВЫЙ РЕЖИМ</b>\n"
                f"={'=' * 40}\n\n"
                f"📋 <b>Model ID:</b>\n<code>{model_id}</code>\n\n"
                f"📋 <b>JSON payload для Replicate API:</b>\n"
                f"<pre>{json.dumps(json_payload, ensure_ascii=False, indent=2)}</pre>\n\n"
                f"{'=' * 40}\n"
                f"✅ Запрос НЕ был отправлен на API\n"
                f"📝 Проверь логи консоли для полной информации"
            )
            
            await bot.send_message(user_id, message, parse_mode="HTML")
            logger.info(f"✅ JSON отправлен пользователю в Telegram")
            tracker.complete_workflow(workflow_id)
            return
        
        if result.get("status") == "error":
            error_msg = result.get("error", "Неизвестная ошибка")
            logger.error(f"❌ Ошибка генерации: {error_msg}")
            tracker.error_workflow(workflow_id, error_msg, stage_id=5)
            await bot.send_message(
                user_id,
                f"❌ Ошибка при генерации видео:\n{error_msg}"
            )
            return
        
        # Получаем URL видео
        video_url = result.get("video_url")
        if not video_url:
            logger.error(f"❌ URL видео не получен")
            tracker.error_workflow(workflow_id, "URL видео не получен", stage_id=6)
            await bot.send_message(
                user_id,
                "❌ Видео сгенерировано, но URL не получен"
            )
            return
        
        # Этап 6: Ожидание результата (завершено)
        tracker.update_stage(workflow_id, 5, "completed", {"progress": 100})
        tracker.update_stage(workflow_id, 6, "completed", {"video_url": video_url[:50] + "..."})
        logger.info(f"✅ Видео сгенерировано: {video_url[:80]}...")
        
        # Этап 7: Скачивание видео
        tracker.update_stage(workflow_id, 7, "running", {"progress": 0})
        logger.info(f"📥 Скачиваю видео...")
        await bot.send_message(user_id, "📥 Скачиваю видео с сервера...")
        
        video_path = await stitcher.download_video(
            video_url,
            f"animation_{user_id}_final.mp4"
        )
        
        tracker.update_stage(workflow_id, 7, "completed", {"progress": 100})
        
        if not video_path:
            logger.error(f"❌ Не удалось скачать видео")
            tracker.error_workflow(workflow_id, "Не удалось скачать видео", stage_id=7)
            await bot.send_message(
                user_id,
                "❌ Не удалось скачать видео с сервера"
            )
            return
        
        logger.info(f"✅ Видео скачано: {video_path}")
        
        # Этап 8: Отправка в Telegram
        tracker.update_stage(workflow_id, 8, "running", {"progress": 0})
        logger.info(f"📤 Отправляю видео в Telegram...")
        await bot.send_message(user_id, "📤 Отправляю видео...")
        
        video_file = types.FSInputFile(video_path)
        await bot.send_video(
            user_id,
            video=video_file,
            caption="✅ Твоя анимация готова! 🎬\n\n🎉 Наслаждайся результатом!"
        )
        
        tracker.update_stage(workflow_id, 8, "completed", {"progress": 100})
        logger.info(f"✅ Видео отправлено пользователю {user_id}")
        
        # 📊 Логирование успешного завершения в Airtable
        data = await state.get_data()
        session_id = data.get("session_id")
        start_time = data.get("start_time")
        video_type = data.get("video_type")
        if session_id and start_time:
            processing_time = time.time() - start_time
            await session_logger.log_session_complete(
                session_id=session_id,
                output_file=video_path,
                processing_time_seconds=processing_time,
                video_type=video_type
            )
        
        # Завершение workflow
        tracker.complete_workflow(workflow_id, output_file=video_path)
        
        # Очищаем временные файлы
        try:
            Path(video_path).unlink(missing_ok=True)
            logger.info(f"🧹 Временные файлы удалены")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось удалить временный файл: {e}")
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в фоновой генерации: {e}")
        logger.error(f"   Traceback: {asyncio.get_event_loop().is_closed()}")
        import traceback
        logger.error(traceback.format_exc())
        
        # 📊 Логирование ошибки в Airtable
        try:
            data = await state.get_data()
            session_id = data.get("session_id")
            video_type = data.get("video_type")
            if session_id:
                await session_logger.log_session_error(
                    session_id=session_id,
                    error_message=str(e),
                    video_type=video_type
                )
        except:
            pass
        
        # Сообщить об ошибке в workflow tracker
        try:
            from src.workflow_tracker import WorkflowTracker
            tracker = WorkflowTracker()
            if workflow_id:
                tracker.error_workflow(workflow_id, str(e))
        except:
            pass
        
        try:
            await bot.send_message(
                user_id,
                f"❌ Критическая ошибка при генерации видео:\n{str(e)}"
            )
        except:
            logger.error(f"   Не удалось отправить сообщение об ошибке")