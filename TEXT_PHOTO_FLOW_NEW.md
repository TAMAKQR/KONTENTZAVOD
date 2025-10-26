# Новый Flow генерации Текст+Фото видео

## 🔄 До (старый способ)

```
Пользователь загружает фото
         ↓
Система создает сцены
         ↓
❌ СРАЗУ ГЕНЕРИРУЕТ ВИДЕО (без подтверждения)
         ↓
Видео готово или ошибка
```

## 🔄 После (новый способ) ✅

```
Пользователь загружает фото
         ↓
Система создает сцены
         ↓
👁️ ПОКАЗЫВАЕТ СЦЕНУ 1 ДЛЯ ПОДТВЕРЖДЕНИЯ
│
├─ ✅ Далее → К сцене 2
├─ ✏️ Редактировать → Изменить промт
├─ 🔄 Регенерировать → К сцене 1 заново
└─ ⬅️ Отмена → Главное меню
         ↓
👁️ ПОКАЗЫВАЕТ СЦЕНУ 2 ДЛЯ ПОДТВЕРЖДЕНИЯ
         ↓
👁️ ПОКАЗЫВАЕТ СЦЕНУ 3 ДЛЯ ПОДТВЕРЖДЕНИЯ
         ↓
✅ ВСЕ ПОДТВЕРЖДЕНЫ → ГЕНЕРИРУЕТ ВИДЕО
         ↓
Видео готово!
```

---

## 📊 Структура данных для каждой сцены

```python
# Что видит пользователь:

🎬 Сцена 1 из 3
──────────────────────────────

📝 Промт:
    Красивый пляж с волнами - Часть 1

📸 Фото:
    https://i.ibb.co/abc123.jpg...

⏱️  Длительность: 5 сек
🎨 Атмосфера: cinematic
📐 Соотношение: 16:9

──────────────────────────────
[✅ Далее]  [✏️ Редактировать]
[🔄 Регенерировать]  [⬅️ Отмена]
```

---

## 🔀 Логика перехода между сценами

```
Сцена 1          Сцена 2          Сцена 3          Генерация
  │                │                │                 │
  ├─ ✅ Далее ────→ ├─ ✅ Далее ────→ ├─ ✅ Далее ────→ ▶️ Генерирует
  │                │                │
  ├─ ✏️ Редак ────→ ├─ ✏️ Редак ────→ └─ ✏️ Редак ────→ (показать снова)
  │                │
  └─ 🔄 Реген ────→ (вернуться к Сцене 1)


Если пользователь на Сцене 3 нажимает "🔄 Регенерировать":
  Сцена 3 → Сцена 1 (начиная с первой)
```

---

## 🔗 Соответствие Фото ↔ Сцена ↔ URL

```
ЗАГРУЗКА ФОТО              СЦЕНЫ                    API ЗАПРОС
─────────────────          ──────                   ──────────────

📷 Фото 1 (пляж)
  file_id_1 ──────→ 📥 Загрузка на ImgBB
                    │
                    └──→ URL_1: https://i.ibb.co/abc...
                           │
                           └──→ Сцена 1 (индекс 0)
                                  │
                                  └──→ API: {
                                         "prompt": "...- Часть 1",
                                         "start_image_url": URL_1  ✅
                                       }

📷 Фото 2 (закат)
  file_id_2 ──────→ 📥 Загрузка на ImgBB
                    │
                    └──→ URL_2: https://i.ibb.co/def...
                           │
                           └──→ Сцена 2 (индекс 1)
                                  │
                                  └──→ API: {
                                         "prompt": "...- Часть 2",
                                         "start_image_url": URL_2  ✅
                                       }

📷 Фото 3 (пальмы)
  file_id_3 ──────→ 📥 Загрузка на ImgBB
                    │
                    └──→ URL_3: https://i.ibb.co/ghi...
                           │
                           └──→ Сцена 3 (индекс 2)
                                  │
                                  └──→ API: {
                                         "prompt": "...- Часть 3",
                                         "start_image_url": URL_3  ✅
                                       }
```

**Правило:** `scene_image_urls[i]` = URL фото для `scenes[i]`

---

## 💻 Код логики переходов

```python
async def show_text_photo_scene_for_confirmation(
    message: types.Message,
    state: FSMContext,
    scene_index: int
):
    """
    Показывает сцену #scene_index

    Логика:
    1. Если scene_index >= количество сцен → Генерировать видео
    2. Иначе → Показать сцену для подтверждения
    """
    data = await state.get_data()
    scenes = data.get("scenes", [])
    scene_image_urls = data.get("scene_image_urls", [])

    if scene_index >= len(scenes):
        # ✅ Все сцены подтверждены!
        await generate_text_photo_video(message, state)
        return

    # Получаем данные текущей сцены
    scene = scenes[scene_index]
    scene_image_url = scene_image_urls[scene_index]  # ← Фото для этой сцены!

    # Показываем пользователю
    scene_text = f"""
    🎬 Сцена {scene['id']} из {len(scenes)}
    ─ {40*'─'}

    📝 Промт: {scene['prompt']}
    📸 Фото: {scene_image_url}
    ⏱️  Длительность: 5 сек
    """

    await message.answer(scene_text, reply_markup=keyboard)
```

---

## 🎯 Обработчики Callback

### 1. Подтверждение сцены

```python
@router.callback_query(lambda c: c.data.startswith("text_photo_scene_approve_"))
async def approve_text_photo_scene(callback, state):
    scene_index = int(callback.data.split("_")[-1])

    # Переходим к следующей
    next_index = scene_index + 1
    await show_text_photo_scene_for_confirmation(
        callback.message,
        state,
        next_index  # ← Следующая сцена!
    )
```

### 2. Редактирование сцены

```python
@router.callback_query(lambda c: c.data.startswith("text_photo_scene_edit_"))
async def edit_text_photo_scene(callback, state):
    scene_index = int(callback.data.split("_")[-1])

    # Сохраняем индекс и просим новый промт
    await state.update_data(editing_scene_index=scene_index)
    await state.set_state(VideoStates.text_photo_editing_scene)

    await callback.message.answer(
        f"✏️ Редактирование сцены {scene_index + 1}\n"
        f"Напиши новый промт:"
    )
```

### 3. Сохранение отредактированной сцены

```python
@router.message(VideoStates.text_photo_editing_scene)
async def save_edited_text_photo_scene(message, state):
    data = await state.get_data()
    scenes = data.get("scenes", [])
    editing_index = data.get("editing_scene_index")

    # Обновляем промт
    scenes[editing_index]["prompt"] = (
        f"{message.text} - Часть {editing_index + 1}"
    )

    await state.update_data(scenes=scenes)

    # Показываем обновленную сцену заново
    await show_text_photo_scene_for_confirmation(
        message,
        state,
        editing_index  # ← Показываем ту же сцену
    )
```

### 4. Регенерирование всех сцен

```python
@router.callback_query(lambda c: c.data == "text_photo_scenes_regenerate_all")
async def regenerate_text_photo_scenes(callback, state):
    # Сбрасываем к первой сцене
    await state.update_data(current_scene_index=0)
    await show_text_photo_scene_for_confirmation(
        callback.message,
        state,
        0  # ← Начиная с первой!
    )
```

---

## ⏱️ Время выполнения

```
Просмотр сцен:          ~5-10 сек (зависит от пользователя)
Генерация 3 сцен:       ~3-5 минут (параллельно!)
Скачивание видео:       ~1-2 минуты
Склеивание:             ~1 минута
Отправка:               ~30 сек
─────────────────────────────────────
ИТОГО:                  ~6-9 минут
```

---

## ✅ Чек-лист изменений

- [x] Добавлено состояние `text_photo_editing_scene`
- [x] Добавлена функция `show_text_photo_scene_for_confirmation()`
- [x] Добавлена функция `generate_text_photo_video()` (в отдельный блок)
- [x] Добавлены обработчики для подтверждения/редактирования сцен
- [x] Изменён flow: загрузка фото → подтверждение сцен → генерация
- [x] Отображение URL фото для каждой сцены
- [x] Кнопки управления сценами
