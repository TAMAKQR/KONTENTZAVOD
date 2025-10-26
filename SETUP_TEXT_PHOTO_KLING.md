# 🚀 Инструкция по установке Text+Photo режима для Kling

## ✅ Что нужно сделать для активации

### 1. Обновить конфигурацию (.env)

Убедитесь что в файле `d:\VIDEO\.env` присутствуют:

```bash
BOT_TOKEN=your_telegram_bot_token
OPENAI_API_KEY=your_openai_api_key
REPLICATE_API_TOKEN=your_replicate_api_token
IMGBB_API_KEY=your_imgbb_api_key  # ✅ КРИТИЧНО для Text+Photo!
```

### 2. Установить зависимости

```bash
pip install -r requirements.txt
```

**Что было добавлено:**

- `aiohttp>=3.8.0` - для асинхронной загрузки фото с Telegram

### 3. Проверить что все файлы созданы

- ✅ `d:\VIDEO\image_utils.py` - новый файл
- ✅ `d:\VIDEO\TEXT_PHOTO_KLING_GUIDE.md` - новый файл
- ✅ `d:\VIDEO\TEXT_PHOTO_IMPLEMENTATION_SUMMARY.md` - новый файл

### 4. Проверить что файлы обновлены

- ✅ `d:\VIDEO\video_generator.py` - добавлен параметр `scene_image_urls`
- ✅ `d:\VIDEO\handlers\video_handler.py` - добавлена функция `start_text_photo_generation()`
- ✅ `d:\VIDEO\requirements.txt` - добавлен `aiohttp`

### 5. Получить ImgBB API ключ (если его нет)

1. Перейдите на https://imgbb.com/
2. Нажмите "Sign up" (регистрация)
3. Подтвердите email
4. Перейдите в "API" раздел
5. Скопируйте API ключ
6. Добавьте в `.env`: `IMGBB_API_KEY=your_key`

### 6. Запустить бот

```bash
python main.py
```

---

## 🎬 Как использовать Text+Photo режим

### Для пользователя:

1. Нажимает `/start` в Telegram
2. Выбирает "📹 Создать видео"
3. Выбирает "📝🖼️ Текст + Фото"
4. Выбирает модель (Kling v2.5 Turbo Pro рекомендуется)
5. Пишет текстовый промт
6. Загружает фотографии (одну за другой):

   ```
   📷 Отправляю 1-е фото
   ✅ Фото 1 загружено!

   📷 Отправляю 2-е фото
   ✅ Фото 2 загружено!

   📷 Отправляю 3-е фото
   ✅ Фото 3 загружено!
   ```

7. Пишет `/готово`
8. **Система обрабатывает и отправляет видео** (~15 минут)

---

## 🔍 Проверка работоспособности

### Чек-лист:

- [ ] `IMGBB_API_KEY` установлен в `.env`
- [ ] `aiohttp>=3.8.0` установлен (`pip list | grep aiohttp`)
- [ ] Файл `image_utils.py` существует
- [ ] Функция `start_text_photo_generation` в `video_handler.py`
- [ ] Бот запущен без ошибок

### Тестирование:

1. **Тест 1: Загрузка фото**

   - Отправьте 1 фото
   - Должно появиться: "✅ Фото 1 загружено!"

2. **Тест 2: Генерация с фото**

   - Загрузите 2 фото
   - Напишите `/готово`
   - Система должна начать генерацию
   - В консоли должны появиться логи загрузки на ImgBB

3. **Тест 3: Финальное видео**
   - Дождитесь завершения (~15 минут)
   - Должно приходить видео в Telegram

---

## ❌ Если что-то не работает

### Ошибка: "IMGBB_API_KEY не установлен"

```
❌ IMGBB_API_KEY не установлен в .env
```

**Решение:**

1. Откройте `.env`
2. Добавьте строку: `IMGBB_API_KEY=your_api_key`
3. Перезагрузите бота

### Ошибка: "Ошибка при скачивании фото с Telegram"

```
❌ Ошибка при скачивании фото с Telegram: ...
```

**Решение:**

- Проверьте интернет соединение
- Попробуйте загрузить фото заново
- Убедитесь что это JPEG/PNG файл

### Ошибка: "Ошибка загрузки на ImgBB"

```
❌ Ошибка загрузки на ImgBB: статус 400
```

**Решение:**

- Проверьте API ключ в `.env`
- Убедитесь что фото не больше 5MB
- Попробуйте другое изображение

### Ошибка: "ModuleNotFoundError: No module named 'image_utils'"

```
❌ ModuleNotFoundError: No module named 'image_utils'
```

**Решение:**

- Убедитесь что файл `image_utils.py` в `d:\VIDEO\`
- Перезагрузите бота

---

## 📊 Параметры для Kling

| Параметр        | Значение            | Обязательно?              |
| --------------- | ------------------- | ------------------------- |
| prompt          | Текстовое описание  | ✅ Да                     |
| start_image     | URL фото (из ImgBB) | ❌ Нет                    |
| duration        | 5 или 10 сек        | ✅ Да (5 по умолчанию)    |
| aspect_ratio    | 16:9, 9:16, 1:1     | ✅ Да (16:9 по умолчанию) |
| negative_prompt | То, что НЕ хотим    | ❌ Нет                    |

---

## 📈 Планы на будущее

### Ближайшие версии:

- [ ] Поддержка Text+Photo для Veo (требует `last_frame_url` вместо `start_image`)
- [ ] Поддержка Text+Photo для Sora (требуется тестирование)
- [ ] Кэширование URL фото (Redis)
- [ ] Поддержка других облачных сервисов (AWS S3, Google Cloud)
- [ ] UI для выбора порядка фото перед генерацией
- [ ] Редактирование промтов для каждой сцены

---

## 🎓 Обучение разработчиков

### Как работает Text+Photo:

1. **Загрузка фото** (image_utils.py)

   ```python
   uploader = ImageUploader()
   url = await uploader.process_telegram_photo(bot, file_id)
   # Возвращает: "https://i.ibb.co/abc123.jpg"
   ```

2. **Передача в генератор** (video_generator.py)

   ```python
   await generator.generate_multiple_scenes(
       scenes=scenes,
       model="kling",
       scene_image_urls=[url1, url2, url3]  # ✅ Каждой сцене своё!
   )
   ```

3. **Генерация в Replicate** (generate_scene)
   ```python
   input_params = {
       "prompt": "...",
       "start_image": "https://i.ibb.co/abc123.jpg"  # ✅ Используется!
   }
   ```

---

## 📚 Дополнительные ресурсы

- **TEXT_PHOTO_KLING_GUIDE.md** - Полное руководство (архитектура, примеры, ошибки)
- **TEXT_PHOTO_IMPLEMENTATION_SUMMARY.md** - Краткое резюме всех изменений
- **MODEL_PARAMETERS_GUIDE.md** - Параметры Kling/Sora/Veo
- **image_utils.py** - Исходный код утилит для фото

---

## ✨ Готово к использованию!

После выполнения всех пунктов выше режим Text+Photo для Kling полностью работоспособен.

**Команда для быстрого старта:**

```bash
pip install -r requirements.txt
python main.py
```

---

**Версия:** 1.0
**Статус:** ✅ Production Ready
**Создано:** 2025
