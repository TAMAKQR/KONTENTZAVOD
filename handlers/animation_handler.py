"""Обработчик для анимирования картин"""
from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

router = Router()


class AnimationStates(StatesGroup):
    """Состояния для анимирования картины"""
    choosing_model = State()  # Выбор модели AI
    waiting_for_image = State()
    waiting_for_prompt = State()
    generating = State()


@router.callback_query(lambda c: c.data == "animation")
async def start_animation(callback: types.CallbackQuery, state: FSMContext):
    """Начало анимирования картины - выбор модели AI"""
    await callback.answer()
    await state.set_state(AnimationStates.choosing_model)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎬 Kling v2.5 Turbo Pro", callback_data="model_kling_anim")],
            [InlineKeyboardButton(text="🎞️ Sora 2", callback_data="model_sora_anim")],
            [InlineKeyboardButton(text="🎥 Veo 3.1 Fast", callback_data="model_veo_anim")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]
        ]
    )
    
    await callback.message.answer(
        "🎨 Анимирование картины\n\n"
        "Выбери AI модель для анимирования:",
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data.startswith("model_") and c.data.endswith("_anim"))
async def choose_animation_model(callback: types.CallbackQuery, state: FSMContext):
    """Выбор модели для анимирования"""
    await callback.answer()
    
    model_map = {
        "model_kling_anim": "kwaivgi/kling-v2.5-turbo-pro",
        "model_sora_anim": "openai/sora-2",
        "model_veo_anim": "google/veo-3.1-fast"
    }
    
    model = model_map.get(callback.data)
    await state.update_data(model=model)
    await state.set_state(AnimationStates.waiting_for_image)
    
    model_name = callback.data.replace("model_", "").replace("_anim", "").upper()
    
    await callback.message.answer(
        f"✅ Модель выбрана: {model_name}\n\n"
        f"📤 Теперь отправь картину, которую ты хочешь анимировать:"
    )


@router.message(AnimationStates.waiting_for_image)
async def process_animation_image(message: types.Message, state: FSMContext):
    """Обработка изображения"""
    if message.photo:
        await state.update_data(image_id=message.photo[-1].file_id)
        await state.set_state(AnimationStates.waiting_for_prompt)
        
        await message.answer(
            "✅ Картина получена!\n\n"
            "Теперь опиши, как ты хочешь её анимировать:\n"
            "(например: 'волнующееся море', 'летящие птицы')"
        )
    else:
        await message.answer("❌ Пожалуйста, отправь изображение")


@router.message(AnimationStates.waiting_for_prompt)
async def process_animation_prompt(message: types.Message, state: FSMContext):
    """Обработка описания анимации"""
    await state.set_state(AnimationStates.generating)
    
    data = await state.get_data()
    model = data.get("model", "google/veo-3.1-fast")
    
    await message.answer(
        f"⏳ Обработка запроса...\n\n"
        f"Модель: {model}\n"
        f"Описание: {message.text}\n\n"
        f"⏰ Видео генерируется... (это может занять несколько минут)"
    )
    
    # TODO: Добавить логику анимирования с использованием выбранной модели
    
    await message.answer("✅ Анимация готова!")
    await state.clear()