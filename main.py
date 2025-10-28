"""Основной файл Telegram бота"""
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext

from config import BOT_TOKEN
from handlers import video_handler, animation_handler, photo_handler, photo_ai_handler

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)

# Регистрируем хэндлеры из отдельных модулей
dp.include_router(video_handler.router)
dp.include_router(animation_handler.router)
dp.include_router(photo_handler.router)
dp.include_router(photo_ai_handler.router)


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📹 Создать видео", callback_data="video")],
            [InlineKeyboardButton(text="🎨 Анимировать картину", callback_data="animation")],
            [InlineKeyboardButton(text="🖼️ Редактировать фото", callback_data="photo")],
        ]
    )
    
    await message.answer(
        "👋 Привет! Выбери, что ты хочешь сделать:",
        reply_markup=keyboard
    )


@dp.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await callback.answer()
    await state.clear()
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📹 Создать видео", callback_data="video")],
            [InlineKeyboardButton(text="🎨 Анимировать картину", callback_data="animation")],
            [InlineKeyboardButton(text="🖼️ Редактировать фото", callback_data="photo")],
        ]
    )
    
    await callback.message.answer(
        "👋 Главное меню. Выбери, что ты хочешь сделать:",
        reply_markup=keyboard
    )


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Обработчик команды /help"""
    help_text = """
📹 **Создать видео** - Генерируй видео из текста через AI
🎨 **Анимировать картину** - Оживи картину с помощью AI
🖼️ **Редактировать фото** - Редактируй и обрабатывай фото

Используй /start для главного меню
    """
    await message.answer(help_text)


async def main():
    """Главная функция"""
    logger.info("🚀 Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())