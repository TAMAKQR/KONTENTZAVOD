"""Обработчик настроек и управления промтами"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from aiogram import Router, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from src.prompts_config import prompts_manager

logger = logging.getLogger(__name__)
router = Router()


class SettingsStates(StatesGroup):
    """Состояния для настроек"""
    viewing_prompts = State()
    choosing_prompt_to_edit = State()
    editing_prompt = State()


@router.callback_query(lambda c: c.data == "settings")
async def open_settings(callback: types.CallbackQuery, state: FSMContext):
    """Открыть меню настроек"""
    await callback.answer()
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Просмотреть промты", callback_data="view_prompts")],
            [InlineKeyboardButton(text="✏️ Редактировать промт", callback_data="edit_prompt_menu")],
            [InlineKeyboardButton(text="🔄 Восстановить дефолтные", callback_data="reset_prompts")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]
        ]
    )
    
    await callback.message.answer(
        "⚙️ <b>Настройки</b>\n\n"
        "Управление системными промтами для ИИ:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data == "view_prompts")
async def view_prompts(callback: types.CallbackQuery, state: FSMContext):
    """Просмотреть все промты"""
    await callback.answer()
    
    prompts = prompts_manager.get_all_prompts()
    
    text = "📋 <b>Текущие системные промты:</b>\n\n"
    
    for i, (key, value) in enumerate(prompts.items(), 1):
        preview = value[:100].replace('\n', ' ')
        if len(value) > 100:
            preview += "..."
        
        text += f"<b>{i}. {key}</b>\n"
        text += f"<code>{preview}</code>\n\n"
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Редактировать", callback_data="edit_prompt_menu")],
            [InlineKeyboardButton(text="⬅️ Назад к настройкам", callback_data="settings")]
        ]
    )
    
    await callback.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data == "edit_prompt_menu")
async def edit_prompt_menu(callback: types.CallbackQuery, state: FSMContext):
    """Выбрать промт для редактирования"""
    await callback.answer()
    
    prompts = prompts_manager.get_all_prompts()
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"✏️ {key[:30]}", 
                callback_data=f"edit_prompt:{key}"
            )] for key in prompts.keys()
        ] + [
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="settings")]
        ]
    )
    
    await callback.message.answer(
        "✏️ <b>Выбери промт для редактирования:</b>",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data.startswith("edit_prompt:"))
async def select_prompt_to_edit(callback: types.CallbackQuery, state: FSMContext):
    """Выбран промт для редактирования"""
    await callback.answer()
    
    prompt_key = callback.data.split(":", 1)[1]
    prompt_value = prompts_manager.get_prompt(prompt_key)
    
    await state.update_data(editing_prompt_key=prompt_key)
    await state.set_state(SettingsStates.editing_prompt)
    
    text = f"✏️ <b>Редактирование промта:</b> <code>{prompt_key}</code>\n\n"
    text += f"<b>Текущее значение:</b>\n<code>{prompt_value}</code>\n\n"
    text += "Отправь новое значение промта (или /cancel для отмены):"
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Восстановить дефолт", callback_data=f"reset_prompt:{prompt_key}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="edit_prompt_menu")]
        ]
    )
    
    await callback.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.message(SettingsStates.editing_prompt)
async def save_edited_prompt(message: types.Message, state: FSMContext):
    """Сохранить отредактированный промт"""
    data = await state.get_data()
    prompt_key = data.get("editing_prompt_key")
    
    new_value = message.text
    
    if prompts_manager.set_prompt(prompt_key, new_value):
        await message.answer(
            f"✅ <b>Промт обновлён!</b>\n\n"
            f"Ключ: <code>{prompt_key}</code>\n"
            f"Новое значение: <code>{new_value[:100]}...</code>",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"❌ Ошибка при сохранении промта",
            parse_mode="HTML"
        )
    
    await state.clear()


@router.callback_query(lambda c: c.data.startswith("reset_prompt:"))
async def reset_single_prompt(callback: types.CallbackQuery, state: FSMContext):
    """Восстановить один дефолтный промт"""
    await callback.answer()
    
    prompt_key = callback.data.split(":", 1)[1]
    
    if prompts_manager.reset_prompt(prompt_key):
        await callback.message.answer(
            f"✅ <b>Промт восстановлен!</b>\n\n"
            f"Ключ: <code>{prompt_key}</code>",
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(
            f"❌ Ошибка при восстановлении промта",
            parse_mode="HTML"
        )
    
    await state.clear()


@router.callback_query(lambda c: c.data == "reset_prompts")
async def reset_all_prompts(callback: types.CallbackQuery):
    """Восстановить все дефолтные промты"""
    await callback.answer()
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, восстановить", callback_data="confirm_reset")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="settings")]
        ]
    )
    
    await callback.message.answer(
        "⚠️ <b>Вы уверены?</b>\n\n"
        "Все промты будут восстановлены на значения по умолчанию.\n"
        "Это действие необратимо!",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data == "confirm_reset")
async def confirm_reset(callback: types.CallbackQuery):
    """Подтвердить восстановление всех промтов"""
    await callback.answer()
    
    if prompts_manager.reset_all():
        await callback.message.answer(
            "✅ <b>Все промты восстановлены на значения по умолчанию!</b>",
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(
            "❌ Ошибка при восстановлении промтов",
            parse_mode="HTML"
        )
