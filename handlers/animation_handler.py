"""Обработчик для анимирования картин"""
import logging
from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)
router = Router()


class AnimationStates(StatesGroup):
    """Состояния для анимирования картины - ОДНО видео, без разбиения на сцены"""
    choosing_model = State()              # Выбор модели AI
    choosing_aspect_ratio = State()       # Выбор соотношения сторон
    choosing_duration = State()           # Выбор длительности
    choosing_image_option = State()       # Загружать ли изображение?
    waiting_for_image = State()           # Если да - получить изображение
    waiting_for_prompt = State()          # Основной промт
    waiting_for_negative_prompt = State() # Отрицательный промт (опционально)
    choosing_enhance_option = State()     # Улучшать ли с ИИ?
    generating = State()                  # Генерация видео


@router.callback_query(lambda c: c.data == "animation")
async def start_animation(callback: types.CallbackQuery, state: FSMContext):
    """Начало анимирования картины - выбор модели AI"""
    await callback.answer()
    await state.set_state(AnimationStates.choosing_model)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎬 Kling v2.5 Turbo Pro", callback_data="anim_model_kling")],
            [InlineKeyboardButton(text="🎞️ Sora 2", callback_data="anim_model_sora")],
            [InlineKeyboardButton(text="🎥 Veo 3.1 Fast", callback_data="anim_model_veo")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]
        ]
    )
    
    await callback.message.answer(
        "🎨 Анимирование картины\n"
        "────────────────────────────────────\n\n"
        "Выбери AI модель для анимирования:",
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data.startswith("anim_model_"))
async def choose_animation_model(callback: types.CallbackQuery, state: FSMContext):
    """Выбор модели для анимирования"""
    await callback.answer()
    
    model_map = {
        "anim_model_kling": ("kwaivgi/kling-v2.5-turbo-pro", "🎬 Kling v2.5 Turbo Pro"),
        "anim_model_sora": ("openai/sora-2", "🎞️ Sora 2"),
        "anim_model_veo": ("google/veo-3.1-fast", "🎥 Veo 3.1 Fast")
    }
    
    model, model_name = model_map.get(callback.data, ("", ""))
    await state.update_data(model=model, model_name=model_name)
    await state.set_state(AnimationStates.choosing_aspect_ratio)
    
    # Выбор соотношения сторон
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
    
    # Выбор длительности
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
        "anim_duration_5": 5,
        "anim_duration_10": 10
    }
    
    duration = duration_map.get(callback.data, 5)
    await state.update_data(duration=duration)
    await state.set_state(AnimationStates.choosing_image_option)
    
    # Спрашиваем нужна ли исходная картина
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
    await state.update_data(image_id=None)
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
        # Получаем самое большое изображение
        file_id = message.photo[-1].file_id
        await state.update_data(image_id=file_id)
        logger.info(f"✅ Получено изображение для анимации: {file_id}")
        
        await state.set_state(AnimationStates.waiting_for_prompt)
        await message.answer(
            "✅ Картина получена!\n"
            "────────────────────────────────────\n\n"
            "📝 Теперь напиши описание анимации:\n\n"
            "Пример: 'волнующееся море с закатом', 'летящие птицы'"
        )
    else:
        await message.answer("❌ Пожалуйста, отправь изображение в формате фото")


@router.message(AnimationStates.waiting_for_prompt)
async def process_animation_prompt(message: types.Message, state: FSMContext):
    """Обработка основного промта"""
    prompt = message.text
    await state.update_data(prompt=prompt)
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
    await state.set_state(AnimationStates.generating)
    
    data = await state.get_data()
    
    await callback.message.answer(
        f"✨ Улучшаю промт через ИИ...\n"
        f"⏳ Это займет несколько секунд..."
    )
    
    # TODO: Добавить улучшение промта через GPT/Gemini
    original_prompt = data.get("prompt", "")
    enhanced_prompt = original_prompt  # TODO: заменить на реальное улучшение
    
    await state.update_data(prompt=enhanced_prompt)
    await start_generation(callback, state)


@router.callback_query(lambda c: c.data == "anim_enhance_no")
async def enhance_prompt_no(callback: types.CallbackQuery, state: FSMContext):
    """Использовать промт как есть"""
    await callback.answer()
    await state.set_state(AnimationStates.generating)
    await start_generation(callback, state)


async def start_generation(callback: types.CallbackQuery, state: FSMContext):
    """Начинаем генерацию видео"""
    data = await state.get_data()
    
    model = data.get("model", "google/veo-3.1-fast")
    model_name = data.get("model_name", "Unknown")
    aspect_ratio = data.get("aspect_ratio", "16:9")
    duration = data.get("duration", 5)
    prompt = data.get("prompt", "")
    negative_prompt = data.get("negative_prompt", "")
    image_id = data.get("image_id")
    
    # Подготавливаем информацию о генерации
    summary = (
        f"🎬 ПАРАМЕТРЫ ВИДЕО\n"
        f"────────────────────────────────────\n"
        f"🎨 Модель: {model_name}\n"
        f"📐 Соотношение сторон: {aspect_ratio}\n"
        f"⏱️ Длительность: {duration} сек\n"
        f"📝 Промт: {prompt[:70]}{'...' if len(prompt) > 70 else ''}\n"
    )
    
    if negative_prompt:
        summary += f"❌ Отрицательный промт: {negative_prompt[:50]}{'...' if len(negative_prompt) > 50 else ''}\n"
    
    if image_id:
        summary += f"🖼️ Исходное изображение: ✅ Загружено\n"
    
    summary += (
        f"────────────────────────────────────\n\n"
        f"⏳ Генерирую видео...\n"
        f"⏰ Это может занять 2-5 минут"
    )
    
    await callback.message.answer(summary)
    logger.info(f"🎬 Начало генерации видео: {model}")
    logger.info(f"   📝 Промт: {prompt[:100]}")
    logger.info(f"   ❌ Отр. промт: {negative_prompt[:100] if negative_prompt else 'N/A'}")
    
    # TODO: Добавить логику генерации видео через Replicate API
    
    await callback.message.answer(
        "✅ Видео готово!\n\n"
        "🎉 Твоя анимация успешно создана"
    )
    
    await state.clear()