# VIDEO GENERATOR PROJECT - Replicate Integration

## 📋 Общая информация

**Проект**: AI Video Generator с Replicate API Integration
**Язык**: Python 3.10+
**Framework**: Aiogram 3.4.1 (Telegram Bot)
**AI Model**: Veo 3.1 Fast (Black Forest Labs через Replicate API)
**API**: Replicate, OpenAI GPT-4

## 🎯 Основная функциональность

Система позволяет пользователям через Telegram создавать многосцебовые видео с помощью AI:

1. **Текстовый промт** → пользователь пишет что хочет видеть
2. **GPT-4 обработка** → улучшение и разбиение на сцены
3. **Видеогенерация** → каждая сцена генерируется через Replicate API (Veo 3.1)
4. **Связность** → используется `last_frame` для визуальной связности между сценами
5. **Склеивание** → все видео объединяются в одно через moviepy
6. **Отправка** → финальное видео отправляется в Telegram

## 📁 Структура проекта

```
d:\VIDEO/
├── main.py                 # Основной бот с обработчиками Telegram
├── config.py               # Конфигурация и загрузка переменных окружения
├── video_generator.py      # VeoVideoGenerator - интеграция с Replicate API
├── video_stitcher.py       # VideoStitcher - склеивание видео
├── scene_connector.py      # SceneConnector - обеспечение связности сцен
├── requirements.txt        # Зависимости Python
├── .env                    # Переменные окружения (токены)
├── .env.example            # Пример .env
├── INTEGRATION_GUIDE.md    # Полная документация интеграции
├── QUICK_START.md          # Быстрый старт
├── parameters/             # JSON конфиги моделей
│   ├── veo_3_1_fast.json
│   ├── kling_2_5_turbo.json
│   └── sora_2.json
├── temp_videos/            # Временные видео и фреймы
├── output_videos/          # Финальные видео
└── .zencoder/              # Информация о репозитории
    └── rules/
        └── repo.md         # Этот файл
```

## 🔧 Основные модули

### 1. **video_generator.py** - VeoVideoGenerator

- **Класс**: VeoVideoGenerator
- **Методы**:
  - `generate_scene()` - генерирует видео одной сцены через Replicate API
  - `download_video()` - скачивает видео по URL
  - `_enhance_prompt_for_continuity()` - улучшает промт для связности
- **Ключевая фишка**: Поддержка `last_frame_url` параметра для визуальной связности

### 2. **video_stitcher.py** - VideoStitcher

- **Класс**: VideoStitcher
- **Методы**:
  - `extract_last_frame()` - извлекает последний фрейм из видео
  - `extract_first_frame_url()` - извлекает первый фрейм
  - `stitch_videos()` - склеивает несколько видео в одно
  - `cleanup_temp_files()` - удаляет временные файлы
- **Зависимость**: moviepy, Pillow

### 3. **scene_connector.py** - SceneConnector

- **Класс**: SceneConnector
- **Методы**:
  - `enhance_scene_for_continuity()` - улучшает одну сцену с учетом соседних
  - `enhance_all_scenes_for_continuity()` - улучшает все сцены одновременно
- **Процесс**: Анализирует атмосферу и описания соседних сцен через GPT-4

### 4. **main.py** - Основной бот

- **Фреймворк**: Aiogram 3.4.1
- **Состояния**: VideoStates с разными этапами (выбор модели, параметры, промт, и т.д.)
- **Ключевая функция**: `generate_video_async()` - асинхронная генерация видео в фоновом режиме

## 🔑 Требуемые токены

1. **BOT_TOKEN** - Telegram Bot API токен (от @BotFather)
2. **OPENAI_API_KEY** - OpenAI API ключ (для GPT-4)
3. **REPLICATE_API_TOKEN** - Replicate API токен (новый, для Veo 3.1)

Вставить в `d:\VIDEO\.env`:

```
BOT_TOKEN=xxx
OPENAI_API_KEY=xxx
REPLICATE_API_TOKEN=xxx
```

## 📦 Зависимости

```
aiogram==3.4.1          # Telegram Bot Framework
python-dotenv==1.0.0    # Загрузка .env
openai>=1.14.0          # OpenAI API (GPT-4)
replicate>=1.17.0       # Replicate API (новое)
requests>=2.31.0        # HTTP запросы
moviepy>=1.0.3          # Видеоредактирование
Pillow>=10.0.0          # Работа с изображениями
```

## 🎬 Процесс генерации видео

```
1. Пользователь → Telegram: "/start" → выбирает "📹 Текст Видео"
2. Выбирает модель (Veo 3.1 Fast рекомендуется)
3. Выбирает параметры (звук, качество, соотношение сторон)
4. Пишет промт (описание видео)
5. Выбирает длительность и количество сцен
6. Нажимает "✅ Принять"

        ↓ НАЧИНАЕТСЯ АСИНХРОННАЯ ГЕНЕРАЦИЯ ↓

7. GPT-4 улучшает и разбивает на сцены (~10 сек)
8. SceneConnector анализирует связность (~30 сек)
9. ДЛЯ КАЖДОЙ СЦЕНЫ:
   - Replicate API генерирует видео (~2-3 мин)
   - Скачивается видео (~30 сек)
   - Извлекается последний фрейм (~10 сек)
10. VideoStitcher склеивает все видео (~1-2 мин)
11. Финальное видео отправляется в Telegram
12. Временные файлы удаляются
```

## 🔄 Данные поток

```
User Prompt (text)
    ↓
enhance_prompt_with_gpt() → JSON с сценами
    ↓
SceneConnector.enhance_all_scenes_for_continuity() → Улучшенные сцены
    ↓
FOR EACH SCENE:
    ├─ VeoVideoGenerator.generate_scene(prompt, last_frame_url)
    │   ↓ Replicate API ↓
    │   Video URL
    │
    ├─ VeoVideoGenerator.download_video()
    │   ↓ requests.get() ↓
    │   Local video file
    │
    └─ VideoStitcher.extract_last_frame()
        ↓ moviepy + Pillow ↓
        Last frame JPEG (для next scene)
    ↓
VideoStitcher.stitch_videos(all_video_paths)
    ↓ moviepy concatenate ↓
    Final video file
    ↓
Send to Telegram
```

## ⚙️ Параметры генерации

### Качество видео

- `720p` - HD (быстро, хороший для соцсетей)
- `1080p` - Full HD (рекомендуется, баланс качества и скорости)
- `4K` - Ultra (медленно, максимальное качество)

### Соотношение сторон

- `16:9` - Горизонтальное (YouTube, Desktop)
- `9:16` - Вертикальное (TikTok, Instagram, YouTube Shorts)
- `1:1` - Квадрат (Instagram Feed)

### Длительность сцены

- 4-8 сек - Рекомендуется для Veo
- Max: 16 сек на видео (ограничение Replicate)

## ⏱️ Время выполнения

**На одну 8-сек сцену:**

- Генерация в Replicate: 2-3 минуты
- Скачивание: 30 сек
- Извлечение фреймов: 10 сек
- **Итого: ~3-4 минуты**

**Для 3 сцен:**

- GPT обработка: 10 сек
- SceneConnector: 30 сек
- Генерация 3 сцен: 9-12 минут
- Склеивание: 1-2 минуты
- **ВСЕГО: ~12-15 минут**

## 🐛 Обработка ошибок

### VeoVideoGenerator

- Проверяет `REPLICATE_API_TOKEN` при инициализации
- Возвращает `{"status": "error", "error": "..."}` при ошибке
- Автоматический retry не реализован (можно добавить)

### VideoStitcher

- Проверяет существование файлов
- Пропускает поврежденные видео с предупреждением
- Возвращает `None` если склеивание не удалось

### SceneConnector

- Падбак на оригинальное описание при ошибке GPT
- Не прерывает процесс (система продолжает работу)

## 🎨 Кастомизация

### Изменить модель Veo

```python
# В video_generator.py
self.model = "google/veo-3-1-fast"  # текущая (рекомендуется)
self.model = "google/veo-3-1"       # более мощная версия (медленнее)
```

### Изменить параметры по умолчанию

```python
# В main.py (функция generate_video_async)
quality = "1080p"        # измените сюда
duration = 8             # длительность сцены
aspect_ratio = "16:9"    # соотношение сторон
```

### Отключить очистку временных файлов

```python
# В конце generate_video_async
# await asyncio.to_thread(stitcher.cleanup_temp_files)  # закомментируйте
```

## 📊 Логирование

Все операции логируются в консоль:

- ✅ Успешные операции
- ❌ Ошибки с полным stack trace
- ⚠️ Предупреждения
- ⏳ Статус-уведомления в Telegram

## 🔗 Интеграция с внешними сервисами

### Replicate API

- **Endpoint**: https://replicate.com/api/v1/
- **Model**: `google/veo-3-1-fast`
- **Параметры**: prompt, duration_seconds, resolution, aspect_ratio, guidance_scale, last_frame (опционально)
- **Auth**: Header `Authorization: Bearer {REPLICATE_API_TOKEN}`

### OpenAI API

- **Endpoint**: https://api.openai.com/v1/
- **Model**: gpt-4
- **Использование**: Улучшение промтов и анализ связности сцен

### Telegram Bot API

- **Framework**: Aiogram 3.4.1
- **Используемые методы**: send_message, send_video, edit_message_text
- **Обработчики**: FSM (Finite State Machine) для управления состояниями

## 🚀 Запуск

```bash
# 1. Установить зависимости
pip install -r requirements.txt

# 2. Добавить токены в .env
# BOT_TOKEN, OPENAI_API_KEY, REPLICATE_API_TOKEN

# 3. Запустить бот
python main.py
```

## 📝 Рекомендации

1. **Для производства**: Использовать базу данных (SQLite/PostgreSQL) вместо MemoryStorage
2. **Для масштабирования**: Добавить очередь задач (Celery/RabbitMQ)
3. **Для надежности**: Реализовать retry logic и fallback механизмы
4. **Для оптимизации**: Кэширование часто генерируемых сцен

## 🔒 Безопасность

- ⚠️ Токены хранятся в `.env` (не коммитить в git!)
- ⚠️ Использовать `.gitignore` для исключения `.env`
- ⚠️ Ограничить доступ к API токенам на продакшене

## 📞 Поддержка

- 📖 INTEGRATION_GUIDE.md - Полная документация
- ⚡ QUICK_START.md - Быстрый старт
- 💻 Исходный код хорошо задокументирован с комментариями

---

**Проект создан**: 2025
**Последнее обновление**: Интеграция Replicate API
**Статус**: ✅ Готов к использованию
