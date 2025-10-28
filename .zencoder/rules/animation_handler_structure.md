# 🎨 Animation Handler - Структура и Состояния

## Назначение

Обработчик для **анимирования картин** (Image-to-Video). Отличается от других разделов:

- ❌ НЕ разбивается на сцены
- ✅ Генерируется ОДНО видео
- ✅ Используется исходное изображение (опционально)

## Поток выполнения

```
/animation → Выбор модели
    ↓
Выбор соотношения сторон (16:9, 9:16, 1:1)
    ↓
Выбор длительности (5 или 10 сек)
    ↓
Загружать ли исходное изображение? (ДА/НЕТ)
    ↓
[ЕСЛИ ДА] Ожидание загрузки картины
    ↓
Ввод основного промта
    ↓
Добавить отрицательный промт? (ДА/НЕТ)
    ↓
[ЕСЛИ ДА] Ожидание отрицательного промта
    ↓
Улучшить промт через ИИ? (ДА/НЕТ)
    ↓
[ЕСЛИ ДА] Улучшение через GPT/Gemini
    ↓
🎬 ГЕНЕРАЦИЯ ВИДЕО (1 видео, без сцен)
    ↓
✅ Видео готово
```

## Состояния FSM

| Состояние                     | Что происходит                                  | Следующее состояние                          |
| ----------------------------- | ----------------------------------------------- | -------------------------------------------- |
| `choosing_model`              | Пользователь выбирает модель (Kling, Sora, Veo) | `choosing_aspect_ratio`                      |
| `choosing_aspect_ratio`       | Выбор 16:9 / 9:16 / 1:1                         | `choosing_duration`                          |
| `choosing_duration`           | Выбор 5 или 10 сек                              | `choosing_image_option`                      |
| `choosing_image_option`       | Загружать ли картину? (ДА/НЕТ)                  | `waiting_for_image` или `waiting_for_prompt` |
| `waiting_for_image`           | Пользователь загружает изображение              | `waiting_for_prompt`                         |
| `waiting_for_prompt`          | Пользователь пишет основной промт               | `waiting_for_negative_prompt`                |
| `waiting_for_negative_prompt` | Выбор: добавить отрицательный промт?            | `choosing_enhance_option`                    |
| `choosing_enhance_option`     | Улучшить промт через ИИ?                        | `generating`                                 |
| `generating`                  | Генерация видео через Replicate API             | ❌ Завершено                                 |

## Callback Data Шифрование

### Модели

```
anim_model_kling  → kwaivgi/kling-v2.5-turbo-pro
anim_model_sora   → openai/sora-2
anim_model_veo    → google/veo-3.1-fast
```

### Соотношение сторон

```
anim_aspect_169  → 16:9 (Горизонтальное)
anim_aspect_916  → 9:16 (Вертикальное)
anim_aspect_11   → 1:1 (Квадрат)
```

### Длительность

```
anim_duration_5   → 5 сек
anim_duration_10  → 10 сек
```

### Опции

```
anim_image_yes    → Загружать изображение
anim_image_no     → Генерировать без изображения
anim_neg_yes      → Добавить отрицательный промт
anim_neg_no       → Пропустить отрицательный промт
anim_enhance_yes  → Улучшить промт через ИИ
anim_enhance_no   → Использовать промт как есть
```

## Сохраняемые данные в FSM

```python
{
    "model": "kwaivgi/kling-v2.5-turbo-pro",          # Выбранная модель
    "model_name": "🎬 Kling v2.5 Turbo Pro",           # Отображаемое имя
    "aspect_ratio": "16:9",                            # Соотношение сторон
    "duration": 5,                                     # Длительность в сек
    "image_id": "file_id_123..." или None,             # Telegram file_id картины (опционально)
    "prompt": "Красивый пейзаж...",                    # Основной промт
    "negative_prompt": "размутое, низкое качество",    # Отрицательный промт (опционально)
}
```

## Функции обработчика

### Основные

- `start_animation()` - Инициирует меню выбора модели
- `choose_animation_model()` - Обработка выбора модели
- `choose_aspect_ratio()` - Обработка выбора соотношения сторон
- `choose_duration()` - Обработка выбора длительности
- `choose_image_yes()` / `choose_image_no()` - Выбор загрузки картины

### Обработка входных данных

- `process_animation_image()` - Получение картины от пользователя
- `process_animation_prompt()` - Получение основного промта
- `process_negative_prompt()` - Получение отрицательного промта

### Улучшение

- `add_negative_prompt()` / `skip_negative_prompt()` - Выбор отрицательного промта
- `enhance_prompt_yes()` / `enhance_prompt_no()` - Выбор улучшения через ИИ

### Генерация

- `start_generation()` - Запуск генерации видео через Replicate API

## TODO: Реализация

### 1. Улучшение промта (enhance_prompt_yes)

```python
# Использовать GPT-4 / Gemini для улучшения
original_prompt = "Красивый пейзаж"
enhanced_prompt = await enhance_prompt_with_gpt(original_prompt)
# Результат: "Захватывающий дух пейзаж горных вершин с покрытыми снегом пиками..."
```

### 2. Загрузка изображения в Replicate

```python
# Получить Telegram URL картины
file = await message.bot.get_file(image_id)
image_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"

# Передать в Replicate как start_image параметр
```

### 3. Генерация видео через Replicate API

```python
# Для Kling v2.5 Turbo Pro
# Параметры: prompt, duration, aspect_ratio, start_image (опционально), negative_prompt

response = await replicate_client.predictions.create(
    model="kwaivgi/kling-v2.5-turbo-pro",
    input={
        "prompt": enhanced_prompt,
        "duration": 5,
        "aspect_ratio": "16:9",
        "start_image": image_url if image_url else None,
        "negative_prompt": negative_prompt,
    }
)
```

### 4. Отправка видео в Telegram

```python
# Скачать видео с URL
video_path = await download_video(response.output_url)

# Отправить в Telegram
await callback.message.answer_video(
    video=FSInputFile(video_path),
    caption="🎉 Вот твоя анимация!"
)
```

## Параметры Kling v2.5 Turbo Pro

```json
{
  "model": "kwaivgi/kling-v2.5-turbo-pro",
  "parameters": {
    "prompt": "Text prompt for video generation",
    "duration": [5, 10], // seconds
    "aspect_ratio": ["16:9", "9:16", "1:1"],
    "start_image": "URL to image (optional, for image-to-video)",
    "negative_prompt": "Things you don't want to see"
  }
}
```

## Логирование

Все действия логируются:

```
✅ Получено изображение для анимации: file_id_123
🎬 Начало генерации видео: kwaivgi/kling-v2.5-turbo-pro
   📝 Промт: Красивый пейзаж...
   ❌ Отр. промт: размутое, артефакты
```

## Интеграция с main.py

**Главное меню (/start):**

```
📹 Текст → Видео
📸 Текст → Фото
🎨 Анимирование картины ← НОВОЕ
🖼️ Редактировать фото
```

**Help (/help):**

```
🎨 Анимирование картины - Оживи картину с помощью AI (одно видео)
```

---

## Различие между разделами

| Разделы              | Видео      | Фото           | Анимирование     |
| -------------------- | ---------- | -------------- | ---------------- |
| Разбиение на сцены   | ✅ Да (3+) | ✅ Да (3+)     | ❌ Нет (1 видео) |
| Исходное изображение | ❌ Нет     | ✅ Опционально | ✅ Опционально   |
| Отрицательный промт  | ❌ Нет     | ❌ Нет         | ✅ Есть          |
| Улучшение ИИ         | ✅ Есть    | ❌ Нет         | ✅ Есть          |
| Выход                | Видео      | Фотографии     | Видео            |

---

**Статус:** 🟡 В разработке (осталось реализовать TODO пункты)
**Дата:** 28.10.2025
