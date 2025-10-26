"""Обработчик для редактирования фото"""
from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

router = Router()


class PhotoStates(StatesGroup):
    """Состояния для редактирования фото"""
    choosing_model = State()  # Выбор модели AI - ПЕРВЫЙ ВЫБОР
    waiting_for_image = State()
    waiting_for_editing_type = State()
    waiting_for_prompt = State()
    processing = State()


@router.callback_query(lambda c: c.data == "photo")
async def start_photo_editing(callback: types.CallbackQuery, state: FSMContext):
    """Начало редактирования фото - выбор модели"""
    await callback.answer()
    await state.set_state(PhotoStates.choosing_model)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎨 Google Nano Banana", callback_data="model_nano_photo")],
            [InlineKeyboardButton(text="🖼️ Google Imagen 4", callback_data="model_imagen_photo")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")],
        ]
    )
    
    await callback.message.answer(
        "🖼️ Редактирование фото\n\n"
        "Выбери AI модель:",
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data.startswith("model_") and c.data.endswith("_photo"), PhotoStates.choosing_model)
async def choose_photo_model(callback: types.CallbackQuery, state: FSMContext):
    """Выбор модели для редактирования фото"""
    await callback.answer()
    
    model_map = {
        "model_nano_photo": "google/nano-banana",
        "model_imagen_photo": "google/imagen-4"
    }
    
    model = model_map.get(callback.data)
    await state.update_data(model=model)
    await state.set_state(PhotoStates.waiting_for_image)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]]
    )
    
    model_name = callback.data.replace("model_", "").replace("_photo", "").upper()
    
    await callback.message.answer(
        f"📦 Выбрана модель: {model_name}\n\n"
        f"Отправь фото, которое ты хочешь отредактировать:",
        reply_markup=keyboard
    )


@router.message(PhotoStates.waiting_for_image)
async def process_photo_image(message: types.Message, state: FSMContext):
    """Обработка изображения"""
    if message.photo:
        await state.update_data(image_id=message.photo[-1].file_id)
        await state.set_state(PhotoStates.waiting_for_editing_type)
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✨ Улучшить", callback_data="enhance_photo")],
                [InlineKeyboardButton(text="🎨 Изменить стиль", callback_data="style_photo")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")],
            ]
        )
        
        await message.answer(
            "✅ Фото получено!\n\n"
            "Выбери тип редактирования:",
            reply_markup=keyboard
        )
    else:
        await message.answer("❌ Пожалуйста, отправь изображение")


@router.callback_query(lambda c: c.data in ["enhance_photo", "style_photo"], PhotoStates.waiting_for_editing_type)
async def process_editing_type(callback: types.CallbackQuery, state: FSMContext):
    """Обработка типа редактирования"""
    await callback.answer()
    
    edit_action = "enhance" if callback.data == "enhance_photo" else "style"
    await state.update_data(edit_action=edit_action)
    await state.set_state(PhotoStates.waiting_for_prompt)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]]
    )
    
    data = await state.get_data()
    model = data.get("model", "google/nano-banana")
    model_name = model.replace("google/", "").upper()
    
    if edit_action == "enhance":
        prompt_text = (
            f"✨ Улучшение фото (модель: {model_name})\n\n"
            f"Опиши, как улучшить фото:\n"
            f"(например: 'сделать ярче', 'убрать шум', 'повысить резкость')"
        )
    else:
        prompt_text = (
            f"🎨 Изменение стиля (модель: {model_name})\n\n"
            f"Опиши желаемый стиль:\n"
            f"(например: 'масло на холсте', 'аниме', 'киберпанк')"
        )
    
    await callback.message.answer(
        prompt_text,
        reply_markup=keyboard
    )


@router.message(PhotoStates.waiting_for_prompt)
async def process_editing_prompt(message: types.Message, state: FSMContext):
    """Обработка описания редактирования"""
    await state.set_state(PhotoStates.processing)
    
    data = await state.get_data()
    model = data.get("model", "google/nano-banana")
    editing_type = data.get("editing_type", "")
    
    await message.answer(
        f"⏳ Обработка запроса...\n\n"
        f"Модель: {model}\n"
        f"Тип: {editing_type}\n"
        f"Описание: {message.text}\n\n"
        f"⏰ Фото обрабатывается..."
    )
    
    # TODO: Добавить логику редактирования фото с использованием выбранной модели
    
    await message.answer("✅ Фото готово!")
    await state.clear()