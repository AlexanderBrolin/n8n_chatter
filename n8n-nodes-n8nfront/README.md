# n8n-nodes-n8nfront

Community-ноды для подключения [N8nFront](https://github.com/ITSS) — веб-платформы чат-ботов с Telegram-совместимым Bot API.

N8nFront — это самостоятельная чат-платформа для внутренних ботов. Она заменяет Telegram в сценариях, где n8n-воркфлоу обрабатывают сообщения пользователей. API платформы совместимо с Telegram Bot API — существующие воркфлоу переносятся с минимальными изменениями.

## Установка

В n8n: **Settings → Community Nodes → Install** → ввести `n8n-nodes-n8nfront`.

Или через CLI:
```bash
npm install n8n-nodes-n8nfront
```

---

## Подготовка: создание бота в N8nFront

Перед настройкой нод в n8n нужно создать бота в админке N8nFront:

1. Зайдите в **админку N8nFront** → раздел **Боты** → **+ Новый бот**
2. Заполните **имя** и **username** бота
3. Поле **Webhook URL** — **оставьте пустым**. Оно заполнится автоматически, когда вы активируете N8nFront Trigger в n8n
4. Нажмите **Создать**
5. Скопируйте **API-токен** бота (кнопка «Показать» → «Копировать»)

> **Зачем поле Webhook URL?**
> Это адрес, куда N8nFront отправляет сообщения пользователей. При использовании ноды N8nFront Trigger она автоматически регистрирует свой webhook через API (`setWebhook`). Вручную заполнять это поле нужно только если вы подключаете бота без ноды — напрямую через URL.

---

## Настройка Credentials в n8n

1. В n8n откройте **Settings → Credentials → Add Credential**
2. Найдите **N8nFront Bot API**
3. Заполните:

| Поле | Что вводить | Пример |
|------|-------------|--------|
| **Base URL** | Адрес вашего сервера N8nFront (без `/api/bot`) | `https://chat.company.ru` |
| **Bot Token** | API-токен бота из админки N8nFront | `a1b2c3d4-e5f6-7890-abcd-ef1234567890` |

4. Нажмите **Test** — если всё верно, появится зелёная галочка (выполняется запрос `getMe`)
5. Сохраните

---

## Ноды

### N8nFront Trigger

Срабатывает, когда пользователь отправляет сообщение или нажимает инлайн-кнопку в чате.

**Настройка:**
1. Добавьте ноду **N8nFront Trigger** на канвас
2. Выберите credentials (созданные выше)
3. Выберите **Events** — типы событий:

| Событие | Когда срабатывает |
|---------|-------------------|
| **Сообщение** | Пользователь отправил текст |
| **Документ** | Пользователь отправил файл |
| **Фото** | Пользователь отправил изображение |
| **Callback (инлайн-кнопка)** | Пользователь нажал инлайн-кнопку |

4. **Активируйте** воркфлоу — нода автоматически зарегистрирует webhook

**Выходные данные** (формат идентичен Telegram Bot API):

Для сообщений:
```json
{
  "update_id": 42,
  "message": {
    "message_id": 123,
    "from": {
      "id": 1,
      "is_bot": false,
      "first_name": "Иван",
      "username": "ivan"
    },
    "chat": {
      "id": 5,
      "type": "private"
    },
    "date": 1710700000,
    "text": "Привет!"
  }
}
```

Для callback-кнопок:
```json
{
  "update_id": 43,
  "callback_query": {
    "id": "cb_abc123",
    "from": {
      "id": 1,
      "first_name": "Иван",
      "username": "ivan"
    },
    "message": { "message_id": 123, "chat": { "id": 5 } },
    "data": "approve_request"
  }
}
```

> **Совместимость с Telegram:** выражения вроде `{{ $json.message.text }}`, `{{ $json.message.from.username }}`, `{{ $json.message.chat.id }}` работают так же, как с Telegram Bot API.

---

### N8nFront (Action)

Нода для отправки сообщений, файлов и управления чатом.

#### Операции

##### Отправить сообщение (`sendMessage`)

Отправляет текстовое сообщение пользователю.

| Параметр | Обязателен | Описание |
|----------|:----------:|----------|
| Chat ID | да | ID чата — берётся из триггера: `{{ $json.message.chat.id }}` |
| Текст | да | Текст сообщения. Поддерживает Markdown и HTML |
| Parse Mode | нет | `Markdown` или `HTML` для форматирования |
| Reply Markup | нет | JSON инлайн-клавиатуры (см. раздел «Инлайн-кнопки») |

**Пример простого ответа:**
- Chat ID: `{{ $json.message.chat.id }}`
- Текст: `Здравствуйте, {{ $json.message.from.first_name }}! Чем могу помочь?`
- Parse Mode: `Markdown`

---

##### Редактировать сообщение (`editMessageText`)

Изменяет текст ранее отправленного сообщения бота.

| Параметр | Обязателен | Описание |
|----------|:----------:|----------|
| Chat ID | да | ID чата |
| Message ID | да | ID сообщения для редактирования |
| Текст | да | Новый текст |
| Parse Mode | нет | Режим форматирования |
| Reply Markup | нет | Новая клавиатура (или пустое для удаления) |

**Типичный сценарий:** бот отправляет «Обрабатываю...», затем редактирует это сообщение на результат:
1. Нода sendMessage → сохранить `{{ $json.result.message_id }}`
2. Обработка данных...
3. Нода editMessageText → Chat ID тот же, Message ID из шага 1, новый текст

---

##### Удалить сообщение (`deleteMessage`)

Удаляет сообщение в чате (мягкое удаление — сообщение заменяется на «Сообщение удалено»).

| Параметр | Обязателен | Описание |
|----------|:----------:|----------|
| Chat ID | да | ID чата |
| Message ID | да | ID сообщения для удаления |

---

##### Отправить документ (`sendDocument`)

Отправляет файл пользователю.

| Параметр | Обязателен | Описание |
|----------|:----------:|----------|
| Chat ID | да | ID чата |
| Binary Property | да | Имя бинарного свойства с файлом (по умолчанию `data`) |
| Подпись | нет | Текст-подпись к файлу |

**Пример:** получить файл из HTTP Request ноды → передать в sendDocument.

---

##### Отправить фото (`sendPhoto`)

Аналогично sendDocument, но для изображений — в чате будет показано превью.

---

##### Скачать файл (`downloadFile`)

Скачивает файл, отправленный пользователем, как бинарные данные для обработки в n8n.

| Параметр | Обязателен | Описание |
|----------|:----------:|----------|
| File ID | да | ID файла из данных сообщения: `{{ $json.message.document.file_id }}` |
| Binary Property | нет | Куда записать файл (по умолчанию `data`) |

**Пример:** пользователь прислал Excel-файл → downloadFile → Spreadsheet File нода → обработка.

---

##### Получить файл — инфо (`getFile`)

Возвращает метаданные файла (размер, путь) без скачивания. Используйте **downloadFile** для получения самого файла.

---

##### Индикатор набора (`sendChatAction`)

Показывает пользователю анимацию «бот печатает...». Используйте перед длительными операциями.

| Параметр | Обязателен | Описание |
|----------|:----------:|----------|
| Chat ID | да | ID чата |

---

##### Ответить на callback (`answerCallbackQuery`)

Подтверждает нажатие inline-кнопки. Аналог `answerCallbackQuery` в Telegram Bot API.

| Параметр | Обязателен | Описание |
|----------|:----------:|----------|
| Callback Query ID | да | ID callback-запроса: `{{ $json.callback_query.id }}` |

**Типичный сценарий:** пользователь нажимает кнопку → Trigger получает callback_query → answerCallbackQuery подтверждает нажатие → далее обработка.

---

##### Информация о боте (`getMe`)

Возвращает информацию о текущем боте (id, имя, username). Параметров нет.

---

## Инлайн-кнопки (Reply Markup)

Бот может отправлять сообщения с кнопками. Формат совместим с Telegram `InlineKeyboardMarkup`.

**Пример Reply Markup JSON:**
```json
{
  "inline_keyboard": [
    [
      {"text": "Да", "callback_data": "confirm_yes"},
      {"text": "Нет", "callback_data": "confirm_no"}
    ],
    [
      {"text": "Открыть сайт", "url": "https://example.com"}
    ]
  ]
}
```

- `callback_data` — при нажатии кнопки воркфлоу получит callback_query с этим значением в `{{ $json.callback_query.data }}`
- `url` — кнопка откроет ссылку в новой вкладке

**Сценарий с кнопками:**

1. **N8nFront Trigger** (events: Сообщение, Callback)
2. **IF** → проверить: `{{ $json.callback_query }}` существует?
   - **Да (callback):** обработать `{{ $json.callback_query.data }}`
   - **Нет (сообщение):** отправить сообщение с кнопками

---

## Примеры воркфлоу

### Простой эхо-бот

```
N8nFront Trigger → N8nFront (sendMessage)
```
- Trigger: events = Сообщение
- sendMessage: Chat ID = `{{ $json.message.chat.id }}`, Текст = `Вы написали: {{ $json.message.text }}`

### Бот с обработкой файлов

```
N8nFront Trigger → N8nFront (downloadFile) → Spreadsheet File → Code → N8nFront (sendMessage)
```
- Trigger: events = Документ
- downloadFile: File ID = `{{ $json.message.document.file_id }}`
- Обработать Excel/CSV в n8n
- Отправить результат текстом

### Бот с кнопками подтверждения

```
N8nFront Trigger → IF (callback?) → [Да] N8nFront (answerCallbackQuery) → N8nFront (editMessageText)
                                   → [Нет] N8nFront (sendMessage + reply_markup)
```
- answerCallbackQuery: Callback Query ID = `{{ $json.callback_query.id }}`
- editMessageText: Chat ID = `{{ $json.callback_query.message.chat.id }}`, Message ID = `{{ $json.callback_query.message.message_id }}`

---

## Миграция с Telegram Bot API

Если у вас есть работающий воркфлоу с Telegram Bot нодой:

1. Замените **Telegram Trigger** на **N8nFront Trigger**
2. Замените **Telegram** ноду на **N8nFront**
3. Выражения **не меняются**: `{{ $json.message.text }}`, `{{ $json.message.chat.id }}`, `{{ $json.message.from.username }}` — всё работает идентично

---

## Лицензия

MIT
