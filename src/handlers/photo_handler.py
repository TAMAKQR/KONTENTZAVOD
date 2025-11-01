"""Обработчик для редактирования фото и генерации с нуля"""
import asyncio
import logging
import re
import uuid
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from aiogram import Router, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from generators.photo_generator import PhotoGenerator
from generators.image_utils import ImageUploader
import google.generativeai as genai
from src.config import GEMINI_API_KEY
from integrations.airtable.airtable_logger import session_logger

router = Router()
logger = logging.getLogger(__name__)

# Конфигурация Gemini для перевода
genai.configure(api_key=GEMINI_API_KEY)


def has_cyrillic(text: str) -> bool:
    """Проверяет наличие кириллицы в тексте"""
    return bool(re.search('[а-яА-ЯёЁ]', text))


async def translate_to_english(text: str) -> str:
    """Переводит русский текст на английский через Gemini"""
    if not text or not has_cyrillic(text):
        return text
    
    try:
        logger.info(f"🔄 Обнаружен русский текст, перевожу: {text[:50]}...")
        
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        prompt = f"""Translate this text from Russian to English. 
Return ONLY the English translation, nothing else.

Text: {text}

Translation:"""
        
        response = model.generate_content(prompt)
        translated = response.text.strip()
        
        logger.info(f"✅ Перевод: {translated}")
        return translated
        
    except Exception as e:
        logger.warning(f"⚠️ Ошибка перевода, использую оригинал: {e}")
        return text


class PhotoStates(StatesGroup):
    """Состояния для работы с фото"""
    choosing_mode = State()  # Генерация с нуля или редактирование
    choosing_model = State()  # Выбор модели AI
    
    # Для генерации с нуля
    generation_waiting_prompt = State()
    generation_waiting_aspect_ratio = State()
    generation_processing = State()
    
    # Для редактирования
    editing_waiting_image = State()
    editing_choosing_category = State()
    editing_choosing_function = State()
    editing_waiting_prompt = State()
    editing_processing = State()


@router.callback_query(lambda c: c.data == "photo")
async def start_photo_mode(callback: types.CallbackQuery, state: FSMContext):
    """Начало работы с фото - выбор режима"""
    await callback.answer()
    await state.set_state(PhotoStates.choosing_mode)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✨ Генерация с нуля", callback_data="photo_generate")],
            [InlineKeyboardButton(text="🖼️ Редактирование фото", callback_data="photo_edit")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")],
        ]
    )
    
    await callback.message.answer(
        "🎨 **Работа с изображениями**\n\n"
        "Выбери режим работы:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


# ==================== ГЕНЕРАЦИЯ С НУЛЯ ====================

@router.callback_query(lambda c: c.data == "photo_generate", PhotoStates.choosing_mode)
async def start_generation(callback: types.CallbackQuery, state: FSMContext):
    """Начало генерации с нуля - выбор модели"""
    await callback.answer()
    
    user_id = callback.from_user.id
    session_id = f"photo_{uuid.uuid4().hex[:12]}"
    start_time = time.time()
    
    # 📊 Логирование в Airtable
    await session_logger.log_session_start(
        user_id=user_id,
        session_id=session_id,
        video_type="photo"
    )
    
    await state.update_data(mode="generation", session_id=session_id, start_time=start_time, video_type="photo")
    await state.set_state(PhotoStates.choosing_model)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🍌 Google Nano Banana", callback_data="model_nano_gen")],
            [InlineKeyboardButton(text="🖼️ Google Imagen 4", callback_data="model_imagen_gen")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_photo_menu")],
        ]
    )
    
    await callback.message.answer(
        "✨ **Генерация изображения с нуля**\n\n"
        "Выбери AI модель:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


@router.callback_query(lambda c: c.data.startswith("model_") and c.data.endswith("_gen"), PhotoStates.choosing_model)
async def choose_generation_model(callback: types.CallbackQuery, state: FSMContext):
    """Выбор модели для генерации"""
    await callback.answer()
    
    model_map = {
        "model_nano_gen": "google/nano-banana",
        "model_imagen_gen": "google/imagen-4"
    }
    
    model = model_map.get(callback.data)
    await state.update_data(model=model)
    await state.set_state(PhotoStates.generation_waiting_prompt)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_photo_menu")]]
    )
    
    model_name = "Nano Banana 🍌" if "nano" in callback.data else "Imagen 4 🖼️"
    
    await callback.message.answer(
        f"📦 **Модель**: {model_name}\n\n"
        f"📝 Напиши описание изображения, которое хочешь создать:\n\n"
        f"_Примеры:_\n"
        f"• Футуристический город на закате\n"
        f"• Кот в костюме космонавта\n"
        f"• Абстрактное искусство в стиле кубизма\n\n"
        f"💡 Можешь писать на русском - система автоматически переведёт!",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


@router.message(PhotoStates.generation_waiting_prompt)
async def process_generation_prompt(message: types.Message, state: FSMContext):
    """Обработка промта для генерации"""
    # Автоматический перевод если есть кириллица
    prompt = await translate_to_english(message.text)
    await state.update_data(prompt=prompt)
    await state.set_state(PhotoStates.generation_waiting_aspect_ratio)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📱 9:16 (вертикальное)", callback_data="aspect_9:16")],
            [InlineKeyboardButton(text="🖥️ 16:9 (горизонтальное)", callback_data="aspect_16:9")],
            [InlineKeyboardButton(text="⬛ 1:1 (квадрат)", callback_data="aspect_1:1")],
            [InlineKeyboardButton(text="📐 3:4", callback_data="aspect_3:4")],
            [InlineKeyboardButton(text="📐 4:3", callback_data="aspect_4:3")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_photo_menu")],
        ]
    )
    
    await message.answer(
        "📐 **Выбери соотношение сторон:**",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


@router.callback_query(lambda c: c.data.startswith("aspect_"), PhotoStates.generation_waiting_aspect_ratio)
async def process_aspect_ratio(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора соотношения сторон и запуск генерации"""
    await callback.answer()
    
    aspect_ratio = callback.data.replace("aspect_", "")
    await state.update_data(aspect_ratio=aspect_ratio)
    await state.set_state(PhotoStates.generation_processing)
    
    data = await state.get_data()
    prompt = data.get("prompt", "")
    model = data.get("model", "google/nano-banana")
    
    status_msg = await callback.message.answer(
        f"⏳ Генерирую изображение...\n\n"
        f"📝 Промт: {prompt[:100]}...\n"
        f"📐 Формат: {aspect_ratio}\n"
        f"🤖 Модель: {model}\n\n"
        f"⏰ Это займет 30-60 секунд..."
    )
    
    # Запускаем генерацию
    try:
        generator = PhotoGenerator()
        
        result = await generator._generate_single_photo(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            reference_image_url=None,
            scene_index=0
        )
        
        if result["status"] == "success":
            photo_url = result["photo_url"]
            
            await status_msg.edit_text(
                f"✅ Изображение готово!\n\n"
                f"🔗 URL: {photo_url}"
            )
            
            # Отправляем фото
            await callback.message.answer_photo(
                photo=photo_url,
                caption=f"🎨 Сгенерировано: {prompt[:100]}..."
            )
            
            # 📊 Логирование успеха в Airtable
            data = await state.get_data()
            session_id = data.get("session_id")
            start_time = data.get("start_time")
            video_type = data.get("video_type")
            if session_id and start_time:
                processing_time = time.time() - start_time
                await session_logger.log_session_complete(
                    session_id=session_id,
                    output_file=photo_url,
                    processing_time_seconds=processing_time,
                    video_type=video_type
                )
            
            await callback.message.answer(
                "✨ Хочешь создать ещё одно изображение?",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="🔄 Ещё раз", callback_data="photo_generate")],
                        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")],
                    ]
                )
            )
        else:
            error = result.get("error", "Неизвестная ошибка")
            await status_msg.edit_text(
                f"❌ Ошибка генерации:\n\n{error}"
            )
            
            # 📊 Логирование ошибки в Airtable
            data = await state.get_data()
            session_id = data.get("session_id")
            video_type = data.get("video_type")
            if session_id:
                await session_logger.log_session_error(
                    session_id=session_id,
                    error_message=error,
                    video_type=video_type
                )
    
    except Exception as e:
        logger.error(f"❌ Ошибка генерации: {e}")
        await status_msg.edit_text(
            f"❌ Ошибка: {str(e)}"
        )
        
        # 📊 Логирование ошибки в Airtable
        data = await state.get_data()
        session_id = data.get("session_id")
        video_type = data.get("video_type")
        if session_id:
            await session_logger.log_session_error(
                session_id=session_id,
                error_message=str(e),
                video_type=video_type
            )
    
    await state.clear()


# ==================== РЕДАКТИРОВАНИЕ ФОТО ====================

@router.callback_query(lambda c: c.data == "photo_edit", PhotoStates.choosing_mode)
async def start_editing(callback: types.CallbackQuery, state: FSMContext):
    """Начало редактирования - выбор модели"""
    await callback.answer()
    
    user_id = callback.from_user.id
    session_id = f"photo_edit_{uuid.uuid4().hex[:12]}"
    start_time = time.time()
    
    # 📊 Логирование в Airtable
    await session_logger.log_session_start(
        user_id=user_id,
        session_id=session_id,
        video_type="photo_edit"
    )
    
    await state.update_data(mode="editing", session_id=session_id, start_time=start_time, video_type="photo_edit")
    await state.set_state(PhotoStates.choosing_model)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🍌 Google Nano Banana", callback_data="model_nano_edit")],
            [InlineKeyboardButton(text="🖼️ Google Imagen 4", callback_data="model_imagen_edit")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_photo_menu")],
        ]
    )
    
    await callback.message.answer(
        "🖼️ **Редактирование фото**\n\n"
        "Выбери AI модель:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


@router.callback_query(lambda c: c.data.startswith("model_") and c.data.endswith("_edit"), PhotoStates.choosing_model)
async def choose_editing_model(callback: types.CallbackQuery, state: FSMContext):
    """Выбор модели для редактирования"""
    await callback.answer()
    
    model_map = {
        "model_nano_edit": "google/nano-banana",
        "model_imagen_edit": "google/imagen-4"
    }
    
    model = model_map.get(callback.data)
    await state.update_data(model=model)
    await state.set_state(PhotoStates.editing_waiting_image)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_photo_menu")]]
    )
    
    model_name = "Nano Banana 🍌" if "nano" in callback.data else "Imagen 4 🖼️"
    
    await callback.message.answer(
        f"📦 **Модель**: {model_name}\n\n"
        f"📤 Отправь фото, которое хочешь отредактировать:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


@router.message(PhotoStates.editing_waiting_image)
async def process_editing_image(message: types.Message, state: FSMContext, bot: Bot):
    """Обработка загруженного фото"""
    if not message.photo:
        await message.answer("❌ Пожалуйста, отправь изображение")
        return
    
    status_msg = await message.answer("⏳ Проверяю качество фото...")
    
    try:
        uploader = ImageUploader()
        file_id = message.photo[-1].file_id
        
        # ✅ ШАГ 1: Скачиваем фото для валидации
        photo_bytes = await uploader.download_telegram_photo(bot, file_id)
        
        if not photo_bytes:
            await status_msg.edit_text("❌ Не удалось скачать фото")
            return
        
        # ✅ ШАГ 2: Валидация качества
        validation = uploader.validate_photo_quality(photo_bytes)
        
        # ❌ Критические ошибки - отклоняем фото
        if not validation["valid"]:
            error_text = "❌ **Фото не прошло проверку:**\n\n"
            error_text += "\n\n".join(validation["errors"])
            error_text += "\n\n💡 **Рекомендации:**\n"
            error_text += "• Используй фото минимум 512x512px\n"
            error_text += "• Отправляй фото как ДОКУМЕНТ для лучшего качества\n"
            error_text += "• Максимальный размер файла: 10MB"
            
            await status_msg.edit_text(error_text, parse_mode="Markdown")
            return
        
        # ⚠️ Предупреждения - принимаем, но информируем
        warning_text = ""
        if validation["warnings"]:
            warning_text = "\n\n⚠️ **Предупреждения:**\n"
            warning_text += "\n".join(validation["warnings"])
        
        # ✅ ШАГ 3: Загружаем на сервер
        await status_msg.edit_text("⏳ Загружаю фото на сервер...")
        image_url = await uploader.upload_to_replicate(photo_bytes)
        
        if not image_url:
            await status_msg.edit_text("❌ Не удалось загрузить фото")
            return
        
        await state.update_data(image_url=image_url)
        await state.set_state(PhotoStates.editing_choosing_category)
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✨ Улучшение", callback_data="cat_enhance")],
                [InlineKeyboardButton(text="🎨 Стилизация", callback_data="cat_style")],
                [InlineKeyboardButton(text="🌈 Цвета и атмосфера", callback_data="cat_color")],
                [InlineKeyboardButton(text="🔄 Трансформации", callback_data="cat_transform")],
                [InlineKeyboardButton(text="📐 Технические", callback_data="cat_technical")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_photo_menu")],
            ]
        )
        
        success_text = (
            f"✅ **Фото загружено!**\n\n"
            f"📊 **Параметры:**\n"
            f"• Размер: {validation['width']}x{validation['height']}px\n"
            f"• Соотношение: {validation['aspect_ratio']}\n"
            f"• Файл: {validation['file_size_mb']}MB"
            f"{warning_text}\n\n"
            f"Выбери категорию редактирования:"
        )
        
        await status_msg.edit_text(
            success_text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки фото: {e}")
        await status_msg.edit_text(f"❌ Ошибка: {str(e)}")


# ==================== КАТЕГОРИИ РЕДАКТИРОВАНИЯ ====================

@router.callback_query(lambda c: c.data.startswith("cat_"), PhotoStates.editing_choosing_category)
async def choose_editing_category(callback: types.CallbackQuery, state: FSMContext):
    """Выбор категории редактирования"""
    await callback.answer()
    
    category = callback.data.replace("cat_", "")
    await state.update_data(category=category)
    await state.set_state(PhotoStates.editing_choosing_function)
    
    # Определяем функции для каждой категории
    functions = {
        "enhance": {
            "title": "✨ Улучшение",
            "options": [
                ("Повысить качество (4K)", "func_upscale"),
                ("Убрать шум", "func_denoise"),
                ("Повысить резкость", "func_sharpen"),
                ("Общее улучшение", "func_enhance_general"),
            ]
        },
        "style": {
            "title": "🎨 Стилизация",
            "options": [
                ("🖌️ Масло на холсте", "func_oil_painting"),
                ("💧 Акварель", "func_watercolor"),
                ("🎭 Аниме стиль", "func_anime"),
                ("🌃 Киберпанк", "func_cyberpunk"),
                ("🎬 Киношный стиль", "func_cinematic"),
                ("🔮 Фэнтези", "func_fantasy"),
                ("📱 Pixel Art", "func_pixel_art"),
                ("🎮 3D Render", "func_3d_render"),
                ("🖼️ Граффити", "func_graffiti"),
            ]
        },
        "color": {
            "title": "🌈 Цвета и атмосфера",
            "options": [
                ("🌅 Теплые тона", "func_warm"),
                ("❄️ Холодные тона", "func_cold"),
                ("⚫ Черно-белое", "func_bw"),
                ("📺 Винтаж/ретро", "func_vintage"),
                ("🌙 День → Ночь", "func_to_night"),
                ("☀️ Ночь → День", "func_to_day"),
                ("❄️ Лето → Зима", "func_to_winter"),
                ("🌸 Зима → Весна", "func_to_spring"),
            ]
        },
        "transform": {
            "title": "🔄 Трансформации",
            "options": [
                ("🏞️ Сменить фон", "func_change_bg"),
                ("🌟 Добавить элементы", "func_add_elements"),
                ("🗺️ Изменить локацию", "func_change_location"),
                ("👗 Изменить одежду", "func_change_clothes"),
                ("🦸 Косплей/костюм", "func_cosplay"),
                ("🎭 Изменить персонажа", "func_change_character"),
            ]
        },
        "technical": {
            "title": "📐 Технические",
            "options": [
                ("📐 Изменить формат на 16:9", "func_format_16_9"),
                ("📱 Изменить формат на 9:16", "func_format_9_16"),
                ("⬛ Изменить формат на 1:1", "func_format_1_1"),
                ("📏 Расширить границы", "func_outpaint"),
                ("🎯 Размыть фон (Bokeh)", "func_bokeh"),
                ("🗑️ Удалить объект", "func_remove_object"),
            ]
        }
    }
    
    category_data = functions.get(category, {})
    title = category_data.get("title", "Функции")
    options = category_data.get("options", [])
    
    # Создаем клавиатуру с функциями
    keyboard_buttons = [[InlineKeyboardButton(text=name, callback_data=code)] for name, code in options]
    keyboard_buttons.append([InlineKeyboardButton(text="⬅️ Назад к категориям", callback_data="back_to_categories")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.answer(
        f"{title}\n\nВыбери функцию:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


@router.callback_query(lambda c: c.data.startswith("func_"), PhotoStates.editing_choosing_function)
async def choose_editing_function(callback: types.CallbackQuery, state: FSMContext):
    """Выбор конкретной функции редактирования"""
    await callback.answer()
    
    function = callback.data.replace("func_", "")
    await state.update_data(function=function)
    
    # Определяем, нужен ли дополнительный промт
    no_prompt_functions = [
        "upscale", "denoise", "sharpen", "enhance_general",
        "bw", "warm", "cold", "to_night", "to_day", "to_winter", "to_spring",
        "bokeh", "format_16_9", "format_9_16", "format_1_1"
    ]
    
    if function in no_prompt_functions:
        # Сразу запускаем обработку без промта
        await state.set_state(PhotoStates.editing_processing)
        await process_editing_without_prompt(callback, state)
    else:
        # Запрашиваем дополнительный промт
        await state.set_state(PhotoStates.editing_waiting_prompt)
        
        prompt_hints = {
            "change_bg": "Опиши новый фон (например: 'пляж на закате', 'космос с планетами')",
            "add_elements": "Опиши что добавить (например: 'бабочки вокруг', 'магические искры')",
            "change_location": "Опиши новую локацию (например: 'Париж, Эйфелева башня', 'тропический лес')",
            "change_clothes": "Опиши новую одежду (например: 'вечернее платье', 'спортивный костюм')",
            "cosplay": "Опиши костюм (например: 'супергерой Marvel', 'средневековый рыцарь')",
            "change_character": "Опиши нового персонажа (например: 'эльф', 'киборг')",
            "outpaint": "Опиши что должно быть за границами (например: 'продолжение пейзажа', 'космос')",
            "remove_object": "Опиши что убрать (например: 'человек слева', 'машина на фоне')",
            # Стили
            "oil_painting": "Дополнительное описание (или отправь '-' чтобы пропустить)",
            "watercolor": "Дополнительное описание (или отправь '-' чтобы пропустить)",
            "anime": "Дополнительное описание (или отправь '-' чтобы пропустить)",
            "cyberpunk": "Дополнительное описание (или отправь '-' чтобы пропустить)",
            "cinematic": "Дополнительное описание (или отправь '-' чтобы пропустить)",
            "fantasy": "Дополнительное описание (или отправь '-' чтобы пропустить)",
            "pixel_art": "Дополнительное описание (или отправь '-' чтобы пропустить)",
            "3d_render": "Дополнительное описание (или отправь '-' чтобы пропустить)",
            "graffiti": "Дополнительное описание (или отправь '-' чтобы пропустить)",
            "vintage": "Дополнительное описание (или отправь '-' чтобы пропустить)",
        }
        
        hint = prompt_hints.get(function, "Опиши желаемый результат")
        
        # Определяем, можно ли пропустить промт (для стилей)
        optional_prompt_functions = [
            "oil_painting", "watercolor", "anime", "cyberpunk", "cinematic",
            "fantasy", "pixel_art", "3d_render", "graffiti", "vintage"
        ]
        
        buttons = []
        if function in optional_prompt_functions:
            buttons.append([InlineKeyboardButton(text="⏭️ Пропустить", callback_data="skip_prompt")])
        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_categories")])
        
        await callback.message.answer(
            f"📝 {hint}\n\n"
            f"💡 **Подсказка:**\n"
            f"• Можешь писать на **русском** - система автоматически переведёт\n"
            f"• Для стилей можно нажать \"Пропустить\" - базовый эффект уже встроен",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )


@router.callback_query(lambda c: c.data == "skip_prompt")
async def skip_prompt_handler(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик кнопки Пропустить"""
    await callback.answer("✅ Промт пропущен")
    await state.update_data(user_prompt="")
    await state.set_state(PhotoStates.editing_processing)
    
    # Создаем фейковый объект message из callback
    class FakeMessage:
        def __init__(self, callback):
            self.chat = callback.message.chat
            self.message_id = callback.message.message_id
            self._callback = callback
            
        async def answer(self, text, **kwargs):
            return await self._callback.message.answer(text, **kwargs)
        
        async def answer_photo(self, photo, **kwargs):
            return await self._callback.message.answer_photo(photo, **kwargs)
    
    fake_message = FakeMessage(callback)
    await execute_editing(fake_message, state)


@router.message(PhotoStates.editing_waiting_prompt)
async def process_editing_with_prompt(message: types.Message, state: FSMContext):
    """Обработка дополнительного промта для редактирования"""
    # Обрабатываем пропуск промта: -, _, пустая строка
    text = message.text.strip() if message.text else ""
    
    if text in ["-", "_", ""]:
        user_prompt = ""
    else:
        # Автоматический перевод если есть кириллица
        user_prompt = await translate_to_english(text)
    
    await state.update_data(user_prompt=user_prompt)
    await state.set_state(PhotoStates.editing_processing)
    
    # Запускаем обработку
    await execute_editing(message, state)


async def process_editing_without_prompt(callback: types.CallbackQuery, state: FSMContext):
    """Обработка редактирования без дополнительного промта"""
    await state.update_data(user_prompt="")
    
    # Создаем фейковый объект message из callback
    class FakeMessage:
        def __init__(self, callback):
            self.chat = callback.message.chat
            self.message_id = callback.message.message_id
            self._callback = callback
            
        async def answer(self, text, **kwargs):
            return await self._callback.message.answer(text, **kwargs)
        
        async def answer_photo(self, photo, **kwargs):
            return await self._callback.message.answer_photo(photo, **kwargs)
    
    fake_message = FakeMessage(callback)
    await execute_editing(fake_message, state)


async def execute_editing(message, state: FSMContext):
    """Выполнение редактирования фото"""
    data = await state.get_data()
    function = data.get("function", "")
    user_prompt = data.get("user_prompt", "")
    image_url = data.get("image_url", "")
    model = data.get("model", "google/nano-banana")
    
    # Создаем промт на основе функции
    prompt = create_editing_prompt(function, user_prompt)
    
    status_msg = await message.answer(
        f"⏳ Обрабатываю фото...\n\n"
        f"🔧 Функция: {get_function_name(function)}\n"
        f"🤖 Модель: {model}\n\n"
        f"⏰ Это займет 30-60 секунд..."
    )
    
    try:
        generator = PhotoGenerator()
        
        # Определяем aspect_ratio для технических функций
        aspect_ratio_map = {
            "format_16_9": "16:9",
            "format_9_16": "9:16",
            "format_1_1": "1:1"
        }
        aspect_ratio = aspect_ratio_map.get(function, "match_input_image")
        
        result = await generator._generate_single_photo(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            reference_image_url=image_url,
            scene_index=0
        )
        
        if result["status"] == "success":
            photo_url = result["photo_url"]
            
            await status_msg.edit_text(
                f"✅ Фото готово!\n\n"
                f"🔗 URL: {photo_url}"
            )
            
            # Отправляем результат
            await message.answer_photo(
                photo=photo_url,
                caption=f"🎨 {get_function_name(function)}"
            )
            
            await message.answer(
                "✨ Хочешь отредактировать ещё?",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="🔄 Ещё раз", callback_data="photo_edit")],
                        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")],
                    ]
                )
            )
        else:
            error = result.get("error", "Неизвестная ошибка")
            await status_msg.edit_text(
                f"❌ Ошибка:\n\n{error}"
            )
    
    except Exception as e:
        logger.error(f"❌ Ошибка редактирования: {e}")
        await status_msg.edit_text(
            f"❌ Ошибка: {str(e)}"
        )
    
    await state.clear()


def create_editing_prompt(function: str, user_prompt: str = "") -> str:
    """Создает промт для редактирования на основе функции"""
    
    prompts = {
        # Улучшение
        "upscale": "Improve image quality, enhance details, 4K resolution, sharp, high quality",
        "denoise": "Remove noise, clean image, smooth, professional quality",
        "sharpen": "Sharpen image, enhance edges, increase clarity, detailed",
        "enhance_general": "Enhance overall quality, improve colors, better lighting, professional look",
        
        # Стили
        "oil_painting": f"Transform into oil painting style, artistic, painterly texture, brush strokes. {user_prompt}",
        "watercolor": f"Transform into watercolor painting, soft edges, artistic, flowing colors. {user_prompt}",
        "anime": f"Transform into anime art style, manga style, cel shaded, vibrant colors. {user_prompt}",
        "cyberpunk": f"Transform into cyberpunk style, neon lights, futuristic, dark atmosphere, tech noir. {user_prompt}",
        "cinematic": f"Transform into cinematic look, film grain, color grading, dramatic lighting, movie style. {user_prompt}",
        "fantasy": f"Transform into fantasy art, magical atmosphere, ethereal, mystical, enchanted. {user_prompt}",
        "pixel_art": f"Transform into pixel art style, 8-bit, retro game graphics, pixelated. {user_prompt}",
        "3d_render": f"Transform into 3D render, CGI style, smooth surfaces, professional 3D graphics. {user_prompt}",
        "graffiti": f"Transform into graffiti street art style, urban, spray paint effect, bold colors. {user_prompt}",
        
        # Цвета
        "warm": "Add warm color tones, golden hour lighting, warm atmosphere, cozy feeling",
        "cold": "Add cold color tones, blue atmosphere, cool temperature, winter feeling",
        "bw": "Transform to black and white, monochrome, high contrast, artistic",
        "vintage": f"Add vintage effect, retro look, film grain, aged photo, nostalgic atmosphere. {user_prompt}",
        "to_night": "Transform to night time, dark atmosphere, moonlight, stars, night scene",
        "to_day": "Transform to day time, bright sunlight, clear sky, daytime atmosphere",
        "to_winter": "Transform to winter season, snow, cold atmosphere, winter landscape",
        "to_spring": "Transform to spring season, flowers blooming, fresh greenery, spring atmosphere",
        
        # Трансформации
        "change_bg": f"Replace background with: {user_prompt}. Keep main subject, new background",
        "add_elements": f"Add to the image: {user_prompt}. Seamlessly integrate new elements",
        "change_location": f"Place subject in new location: {user_prompt}. Change environment, keep subject",
        "change_clothes": f"Change clothing to: {user_prompt}. New outfit, same person",
        "cosplay": f"Transform into cosplay: {user_prompt}. Costume, character transformation",
        "change_character": f"Transform character into: {user_prompt}. New character design",
        
        # Технические
        "format_16_9": "Extend to 16:9 aspect ratio, seamless expansion, natural continuation",
        "format_9_16": "Extend to 9:16 aspect ratio, vertical format, seamless expansion",
        "format_1_1": "Reframe to 1:1 square aspect ratio, balanced composition",
        "outpaint": f"Extend image borders, continue scene naturally: {user_prompt}",
        "bokeh": "Add bokeh effect, blur background, focus on subject, shallow depth of field, professional photography",
        "remove_object": f"Remove from image: {user_prompt}. Clean removal, seamless inpainting",
    }
    
    return prompts.get(function, f"Transform image: {user_prompt}")


def get_function_name(function: str) -> str:
    """Возвращает читаемое имя функции"""
    
    names = {
        "upscale": "Повышение качества",
        "denoise": "Убрать шум",
        "sharpen": "Повышение резкости",
        "enhance_general": "Общее улучшение",
        "oil_painting": "Масло на холсте",
        "watercolor": "Акварель",
        "anime": "Аниме стиль",
        "cyberpunk": "Киберпанк",
        "cinematic": "Киношный стиль",
        "fantasy": "Фэнтези",
        "pixel_art": "Pixel Art",
        "3d_render": "3D Render",
        "graffiti": "Граффити",
        "warm": "Теплые тона",
        "cold": "Холодные тона",
        "bw": "Черно-белое",
        "vintage": "Винтаж",
        "to_night": "День → Ночь",
        "to_day": "Ночь → День",
        "to_winter": "Зима",
        "to_spring": "Весна",
        "change_bg": "Смена фона",
        "add_elements": "Добавление элементов",
        "change_location": "Смена локации",
        "change_clothes": "Смена одежды",
        "cosplay": "Косплей",
        "change_character": "Смена персонажа",
        "format_16_9": "Формат 16:9",
        "format_9_16": "Формат 9:16",
        "format_1_1": "Формат 1:1",
        "outpaint": "Расширение границ",
        "bokeh": "Bokeh эффект",
        "remove_object": "Удаление объекта",
    }
    
    return names.get(function, function)


# ==================== НАВИГАЦИЯ ====================

@router.callback_query(lambda c: c.data == "back_to_photo_menu")
async def back_to_photo_menu(callback: types.CallbackQuery, state: FSMContext):
    """Возврат в главное меню фото"""
    await start_photo_mode(callback, state)


@router.callback_query(lambda c: c.data == "back_to_categories")
async def back_to_categories(callback: types.CallbackQuery, state: FSMContext):
    """Возврат к категориям редактирования"""
    await state.set_state(PhotoStates.editing_choosing_category)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✨ Улучшение", callback_data="cat_enhance")],
            [InlineKeyboardButton(text="🎨 Стилизация", callback_data="cat_style")],
            [InlineKeyboardButton(text="🌈 Цвета и атмосфера", callback_data="cat_color")],
            [InlineKeyboardButton(text="🔄 Трансформации", callback_data="cat_transform")],
            [InlineKeyboardButton(text="📐 Технические", callback_data="cat_technical")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_photo_menu")],
        ]
    )
    
    await callback.message.answer(
        "✅ **Фото загружено**\n\n"
        "Выбери категорию редактирования:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await callback.answer()