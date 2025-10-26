# 🎬 Параметры моделей Replicate API - Полное руководство

Этот документ содержит **точные тонкости и ограничения** для каждой модели на основе актуального API Replicate.

---

## 📊 Сравнительная таблица

| Параметр               | Kling v2.5 Turbo Pro           | Sora 2           | Veo 3.1 Fast          |
| ---------------------- | ------------------------------ | ---------------- | --------------------- |
| **Model ID**           | `kwaivgi/kling-v2.5-turbo-pro` | `openai/sora-2`  | `google/veo-3.1-fast` |
| **Duration**           | **5, 10 сек**                  | **20 сек**       | **5-16 сек**          |
| **Aspect Ratio**       | 16:9, 9:16, 1:1                | 1920x1080 (16:9) | 16:9, 9:16, 1:1       |
| **Quality/Resolution** | ❌ НЕТ                         | ❌ НЕТ           | ❌ НЕТ                |
| **Start/Last Frame**   | ✅ `start_image`               | ✅ `image`       | ✅ `last_frame_url`   |
| **Negative Prompt**    | ✅ Поддерживает                | ❌ НЕТ           | ❌ НЕТ                |
| **Pricing**            | ~$0.07/сек                     | ~$0.08/сек       | ~$0.05/сек            |

---

## 🎬 1. KLING v2.5 TURBO PRO

### Model ID

```
kwaivgi/kling-v2.5-turbo-pro
```

### Параметры

```json
{
  "prompt": {
    "type": "string",
    "required": true,
    "description": "Text prompt for video generation"
  },
  "duration": {
    "type": "integer",
    "enum": [5, 10],
    "default": 5,
    "description": "Duration ТОЛЬКО 5 или 10 секунд!"
  },
  "aspect_ratio": {
    "type": "string",
    "enum": ["16:9", "9:16", "1:1"],
    "default": "16:9",
    "description": "Соотношение сторон"
  },
  "start_image": {
    "type": "string",
    "format": "uri",
    "nullable": true,
    "description": "First frame for image-to-video (связность сцен)"
  },
  "negative_prompt": {
    "type": "string",
    "default": "",
    "description": "Things you don't want to see"
  }
}
```

### ⚠️ Тонкости

1. **Duration ЖЕСТКИЕ ограничения**: Только 5 или 10 секунд

   - ❌ 4 сек - ОШИБКА
   - ❌ 8 сек - ОШИБКА
   - ✅ 5 сек - OK
   - ✅ 10 сек - OK

2. **Нет параметра качества**: Все видео генерируются с одинаковым качеством на стороне Replicate

   - ❌ `quality`, `resolution`, `fps` - НЕ СУЩЕСТВУЮТ
   - Выбор 720p/1080p/4K в боте - это **мертвый код**

3. **Negative Prompt работает хорошо**:

   - Помогает исключить нежелательные элементы
   - Пример: `"blurry, low quality, distorted"`

4. **Start Image для связности**:
   - Передавайте как `start_image` (НЕ `last_frame_url`!)
   - Должно быть валидный JPEG/PNG URL
   - Помогает сделать переход между сценами гладким

### 💡 Рекомендации

- **Для сериального контента**: Используйте `start_image` для связности
- **Длительность**: Чередуйте 5 и 10 сек для разнообразия
- **Промты**: Очень отзывчив на детальные описания

### 💰 Стоимость

- 5 сек: ~$0.35
- 10 сек: ~$0.70

---

## 🎞️ 2. SORA 2

### Model ID

```
openai/sora-2
```

### Параметры

```json
{
  "prompt": {
    "type": "string",
    "required": true,
    "description": "Text prompt for video generation"
  },
  "image": {
    "type": "string",
    "format": "uri",
    "nullable": true,
    "deprecated": true,
    "description": "Deprecated: Use start_image instead"
  },
  "start_image": {
    "type": "string",
    "format": "uri",
    "nullable": true,
    "description": "First frame of the video"
  },
  "duration": {
    "type": "integer",
    "default": 20,
    "description": "Duration ФИКСИРОВАНО 20 секунд!"
  },
  "aspect_ratio": {
    "type": "string",
    "enum": ["1920x1080"],
    "default": "1920x1080",
    "description": "ТОЛЬКО 16:9 (1920x1080)"
  },
  "negative_prompt": {
    "type": "string",
    "default": "",
    "description": "❌ НЕ ПОДДЕРЖИВАЕТСЯ, игнорируется"
  }
}
```

### ⚠️ Тонкости

1. **Duration ФИКСИРОВАН на 20 секунд**:

   - ❌ Нельзя изменить
   - ✅ Всегда 20 сек
   - Это очень долгое видео!

2. **Aspect Ratio ТОЛЬКО 16:9**:

   - ❌ 9:16 - ОШИБКА
   - ❌ 1:1 - ОШИБКА
   - ✅ 1920x1080 (16:9) - только этот

3. **Нет Negative Prompt**:

   - Параметр существует, но **игнорируется**
   - Не тратьте время на его заполнение

4. **Deprecated параметр `image`**:

   - ❌ Не используйте `image`
   - ✅ Используйте `start_image`

5. **Качество видео**:
   - ❌ НЕТ параметра качества
   - Видео генерируется в "стандартном" качестве

### 💡 Рекомендации

- **НЕ рекомендуется** для динамичного контента (20 сек - слишком долго)
- **Хорош для**: Длительные сцены с развитием сюжета
- **Start Image**: Используйте для связности сцен
- **Промты**: Может быть "ленив" на коротких запросах - давайте детали

### 💰 Стоимость

- 20 сек: ~$1.60 (дорого!)

---

## 🎥 3. VEO 3.1 FAST

### Model ID

```
google/veo-3.1-fast
```

### Параметры

```json
{
  "prompt": {
    "type": "string",
    "required": true,
    "description": "Text prompt for video generation"
  },
  "duration": {
    "type": "integer",
    "enum": [5, 10, 15],
    "default": 5,
    "description": "Duration 5, 10, или 15 сек (максимум 15!)"
  },
  "aspect_ratio": {
    "type": "string",
    "enum": ["16:9", "9:16", "1:1"],
    "default": "16:9",
    "description": "Соотношение сторон"
  },
  "last_frame_url": {
    "type": "string",
    "format": "uri",
    "nullable": true,
    "description": "Last frame from previous video (for continuity)"
  },
  "negative_prompt": {
    "type": "string",
    "default": "",
    "description": "❌ НЕ ПОДДЕРЖИВАЕТСЯ"
  }
}
```

### ⚠️ Тонкости

1. **Duration гибче чем Kling**:

   - ✅ 5 сек
   - ✅ 10 сек
   - ✅ 15 сек (максимум!)
   - ❌ Более 15 сек - ОШИБКА
   - ❌ 8 сек - работает как 5 (округление?)

2. **Aspect Ratio как у Kling**:

   - ✅ 16:9, 9:16, 1:1
   - Полная поддержка

3. **last_frame_url для связности**:

   - ✅ Поддерживает для связности (НЕ `start_image`!)
   - Используйте ПОСЛЕДНИЙ фрейм предыдущего видео
   - Помогает визуальной преемственности

4. **Negative Prompt НЕ работает**:

   - Параметр может быть, но **игнорируется**
   - ❌ Не используйте

5. **Качество видео**:
   - ❌ НЕТ параметра качества
   - Генерируется в одном качестве

### 💡 Рекомендации

- **РЕКОМЕНДУЕТСЯ** для большинства задач
- **Быстрый**: Fast версия, меньше времени ждать
- **Гибкий**: Поддерживает 5, 10, 15 сек
- **Связность**: Хорошо работает с `last_frame_url`
- **Баланс**: Качество/время/стоимость в балансе

### 💰 Стоимость

- 5 сек: ~$0.25
- 10 сек: ~$0.50
- 15 сек: ~$0.75

---

## 🔴 КРИТИЧЕСКИЕ ОШИБКИ

### 1. Путаница между моделями

```python
# ❌ НЕПРАВИЛЬНО - Sora не имеет этих параметров
replicate.run("openai/sora-2", input={
    "prompt": "...",
    "duration": 10,           # ❌ Sora ТОЛЬКО 20!
    "aspect_ratio": "9:16",   # ❌ Sora ТОЛЬКО 16:9!
    "negative_prompt": "..."  # ❌ Sora это игнорирует!
})

# ✅ ПРАВИЛЬНО для Sora
replicate.run("openai/sora-2", input={
    "prompt": "...",
    "start_image": "https://..."  # опционально
})

# ✅ ПРАВИЛЬНО для Kling
replicate.run("kwaivgi/kling-v2.5-turbo-pro", input={
    "prompt": "...",
    "duration": 5,            # ✅ 5 или 10
    "aspect_ratio": "16:9",
    "start_image": "https://...",  # для связности
    "negative_prompt": "blurry"
})

# ✅ ПРАВИЛЬНО для Veo
replicate.run("google/veo-3.1-fast", input={
    "prompt": "...",
    "duration": 10,           # ✅ 5, 10 или 15
    "aspect_ratio": "9:16",
    "last_frame_url": "https://..."  # для связности (НЕ start_image!)
})
```

---

## 🎯 ТОНКОСТЬ №1: Качество видео

**ВСЕ модели генерируют видео с ФИКСИРОВАННЫМ качеством на стороне Replicate.**

- ❌ Нельзя выбрать 720p vs 1080p vs 4K через API
- ❌ Нельзя изменить FPS
- ❌ Нельзя изменить битрейт
- ✅ Качество зависит только от модели и версии на Replicate

**В вашем боте выбор качества (720p/1080p/4K) - это мертвый код!**

---

## 🎯 ТОНКОСТЬ №2: Связность сцен

| Модель    | Параметр         | Тип | Из чего?                          |
| --------- | ---------------- | --- | --------------------------------- |
| **Kling** | `start_image`    | URL | ПЕРВЫЙ фрейм предыдущего видео    |
| **Sora**  | `start_image`    | URL | ПЕРВЫЙ фрейм предыдущего видео    |
| **Veo**   | `last_frame_url` | URL | ПОСЛЕДНИЙ фрейм предыдущего видео |

**Важно**: Veo использует ПОСЛЕДНИЙ фрейм (противоположно Kling/Sora!)

---

## 🎯 ТОНКОСТЬ №3: Duration

| Модель    | Допустимые значения |
| --------- | ------------------- |
| **Kling** | 5, 10 (жестко)      |
| **Sora**  | 20 (фиксировано)    |
| **Veo**   | 5, 10, 15 (гибко)   |

---

## 📋 ЛУЧШИЕ ПРАКТИКИ

### Для сериального контента (3+ сцен)

1. Используйте **Veo 3.1 Fast** (рекомендуется)
2. Длительность: Чередуйте 5 и 10 сек
3. Передавайте `last_frame_url` для связности
4. Используйте GPT для улучшения промтов

### Для одной длительной сцены

1. Используйте **Sora 2** (20 сек)
2. Но помните: **дорого!** (~$1.60)

### Быстрая генерация

1. **Kling** - 5 сек (самый быстрый)
2. Используйте `start_image` для связности

---

## 🔧 ИМПЛЕМЕНТАЦИЯ В КОДЕ

### Текущий баг в `video_generator.py`

Метод `generate_scene()` не использует параметр `quality`:

```python
# ❌ НЕПРАВИЛЬНО - качество никуда не передается
input_params = {
    "prompt": prompt,
    "duration": duration,
    "aspect_ratio": aspect_ratio
}
# quality параметр просто игнорируется!
```

### Исправление

Удалить выбор качества из UI или заменить на другие параметры:

- Вместо качества: выбор `negative_prompt` для Kling
- Вместо качества: выбор длительности (5/10/15 для Veo)

---

## 📞 ССЫЛКИ

- [Replicate Kling](https://replicate.com/kwaivgi/kling-v2.5-turbo-pro)
- [Replicate Sora](https://replicate.com/openai/sora-2)
- [Replicate Veo](https://replicate.com/google/veo-3.1-fast)

---

**Последнее обновление**: 2025-01-26
**Статус**: ✅ Актуально на основе реального API
