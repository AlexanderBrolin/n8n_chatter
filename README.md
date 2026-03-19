# N8nFront — веб-платформа чатов для n8n-ботов

Замена Telegram в качестве фронтенда для n8n чат-ботов. Собственная платформа с регистрацией ботов, чат-интерфейсом и Telegram-совместимым Bot API — существующие n8n-воркфлоу переносятся заменой одного URL.

## Зачем

- Telegram ненадёжен в РФ, а боты — для внутреннего использования
- Несколько хостов n8n используют чат-ботов через webhook
- Нужно единое решение: веб-платформа со своей авторизацией и управлением доступом

## Что внутри

### Админка (`/admin/`)
- Dashboard со статистикой (боты, пользователи, сообщения)
- CRUD ботов — создание генерирует токен, показывает API URL для n8n
- CRUD пользователей чата — назначение доступа к конкретным ботам
- Аудит-лог всех действий

### Чат (`/chat/`)
- Full-screen мессенджер в стиле Telegram Web
- Список доступных ботов, история сообщений
- Отправка текста + множественных файлов в одном сообщении
- Markdown-рендеринг в сообщениях бота (marked.js)
- Изображения как inline-превью, документы как карточки
- SSE (Server-Sent Events) для получения ответов бота в реал-тайме

### Bot API (Telegram-совместимый)

Префикс: `/api/bot/{token}/...`

| Метод | Описание |
|-------|----------|
| `getMe` | Информация о боте |
| `getUpdates` | Long-polling для получения обновлений (`offset`, `limit`, `timeout`) |
| `sendMessage` | Отправка текста (`chat_id`, `text`, `parse_mode`, `reply_markup`) |
| `editMessageText` | Редактирование сообщения бота |
| `deleteMessage` | Удаление сообщения (soft delete) |
| `sendDocument` | Отправка файла (`chat_id`, `document`, `caption`) |
| `sendPhoto` | Отправка изображения (`chat_id`, `photo`, `caption`) |
| `getFile` | Метаданные файла (`file_id`) |
| `sendChatAction` | Индикатор «бот печатает...» |
| `answerCallbackQuery` | Подтверждение нажатия inline-кнопки |
| `setWebhook` | Регистрация webhook URL |
| `deleteWebhook` | Удаление webhook (`drop_pending_updates`) |
| `getWebhookInfo` | Текущий webhook и количество ожидающих обновлений |

Webhook-payload к n8n идентичен формату Telegram `Update`:
```json
{
  "update_id": 123,
  "message": {
    "message_id": 456,
    "from": {"id": 1, "is_bot": false, "first_name": "Иван", "username": "ivan"},
    "chat": {"id": 789, "type": "private"},
    "date": 1234567890,
    "text": "Привет!"
  }
}
```

### n8n Community Nodes (`n8n-nodes-n8nfront`)

Отдельный npm-пакет с двумя нодами:
- **N8nFront Trigger** — webhook-триггер, автоматически регистрирует webhook при активации workflow
- **N8nFront** — action-нода: sendMessage, sendDocument, sendPhoto, getFile, getMe

## Стек

- **Backend**: Flask + Gunicorn (gevent) + SQLAlchemy
- **Frontend**: Jinja2 + Alpine.js + Tailwind CSS (CDN)
- **БД**: PostgreSQL 16 (собственный контейнер)
- **Реал-тайм**: SSE (in-memory pub/sub broker)
- **Деплой**: Docker Compose

## Быстрый старт

### 1. Настройка

Отредактируйте `envfile`:
```
SECRET_KEY=ваш-секретный-ключ
DB_USER=n8n_front
DB_PASSWORD=надёжный-пароль
DB_NAME=n8n_front
APP_PORT=5001
```

### 2. Запуск

```bash
docker compose --env-file envfile up -d --build
```

### 3. Создание администратора

```bash
docker compose exec n8n-front flask --app server.app:create_app seed
```
Создаёт пользователя `admin` / `admin`.

### 4. Настройка

1. Откройте `http://your-host:5001/auth/login`, войдите как admin
2. Создайте бота: Боты → Новый бот → укажите имя и webhook URL вашего n8n-воркфлоу
3. Скопируйте сгенерированный токен бота
4. Создайте пользователя чата: Пользователи → Новый → назначьте доступ к боту
5. Пользователь заходит в `http://your-host:5001/chat/`, логинится и пишет боту

### 5. Подключение n8n-воркфлоу

**Вариант A — Community Nodes (рекомендуется):**

Установите `n8n-nodes-n8nfront`, используйте ноды N8nFront Trigger + N8nFront.

**Вариант B — стандартные n8n-ноды:**

1. Webhook Trigger → в настройках бота укажите URL этого триггера как webhook URL
2. В выражениях используйте те же поля что и для Telegram:
   - `{{ $json.message.text }}` — текст сообщения
   - `{{ $json.message.from.username }}` — имя пользователя
   - `{{ $json.message.chat.id }}` — ID чата (для ответа)
3. Для ответа используйте HTTP Request ноду:
   ```
   POST http://n8n-front-host:5001/api/bot/{TOKEN}/sendMessage
   Body: {"chat_id": "{{ $json.message.chat.id }}", "text": "Ответ бота"}
   ```

**Вариант C — миграция с Telegram:**

В существующем воркфлоу замените `https://api.telegram.org/bot{token}` на `http://n8n-front-host:5001/api/bot/{token}` — выражения вида `{{ $json.message.text }}` продолжат работать без изменений.

### 6. Миграция Python-ботов с Telegram

Chatter реализует Telegram-совместимый Bot API — существующие Python-боты переносятся с минимальными изменениями в коде.

#### Поддерживаемые библиотеки

| Библиотека | Версия | Поддержка |
|------------|--------|-----------|
| `python-telegram-bot` | 20.x+ | Полная (polling + webhook) |
| `aiogram` | 3.x | Полная (polling + webhook) |
| `requests` / `httpx` (raw API) | любая | Полная |

#### Принцип работы

Bot API платформы Chatter повторяет API Telegram: те же эндпоинты, тот же формат JSON. Поэтому вместо переписывания бота достаточно сменить базовый URL — с `https://api.telegram.org/bot` на `https://your-chatter.com/api/bot`.

Поддерживается как **webhook-режим** (бот слушает входящие запросы от Chatter), так и **polling-режим** (бот сам запрашивает обновления через `getUpdates` с long polling).

---

#### Пошаговая инструкция

##### Шаг 1. Создать бота в админке Chatter

1. Откройте админку: `http://your-host:5001/admin/`
2. Перейдите: Боты → Новый бот
3. Заполните имя и username
4. **Webhook URL оставьте пустым** — для polling-режима webhook не нужен
5. Нажмите «Создать» — скопируйте сгенерированный **API-токен**
6. Назначьте бота нужным пользователям (или включите флаг «Доступен всем»)

##### Шаг 2. Установить зависимости

Для `python-telegram-bot`:
```bash
pip install python-telegram-bot>=20.0
```

Для `aiogram`:
```bash
pip install aiogram>=3.0
```

##### Шаг 3. Изменить код бота

**Вариант A — с хелпером `chatter_bot.py` (рекомендуется)**

Скопируйте файл `chatter_bot.py` из репозитория Chatter в проект бота. Затем:

```python
# ===== БЫЛО (Telegram) =====
from telegram.ext import Application, CommandHandler, MessageHandler, filters

TOKEN = "123456:ABC-DEF..."
application = Application.builder().token(TOKEN).build()

# ===== СТАЛО (Chatter) =====
from telegram.ext import CommandHandler, MessageHandler, filters
from chatter_bot import chatter_application

TOKEN = "ваш-токен-из-админки-chatter"
CHATTER_URL = "https://chat.company.com"  # URL вашего Chatter
application = chatter_application(TOKEN, CHATTER_URL)
```

Всё остальное — хендлеры, фильтры, `run_polling()` — остаётся **без изменений**.

**Вариант B — без хелпера (ручная настройка)**

```python
from telegram.ext import Application

TOKEN = "ваш-токен-из-админки-chatter"
CHATTER_URL = "https://chat.company.com"

application = (
    Application.builder()
    .token(TOKEN)
    .base_url(f"{CHATTER_URL}/api/bot")
    .base_file_url(f"{CHATTER_URL}/api/bot")
    .build()
)
```

**Вариант C — aiogram 3.x**

```python
from aiogram import Bot, Dispatcher

TOKEN = "ваш-токен-из-админки-chatter"
CHATTER_URL = "https://chat.company.com/api/bot"

bot = Bot(token=TOKEN, base_url=CHATTER_URL)
dp = Dispatcher()

# Хендлеры — без изменений
# dp.message(...)

# Polling — без изменений
dp.run_polling(bot)
```

**Вариант D — raw requests / httpx**

Замените базовый URL в HTTP-вызовах:

```python
import requests

TOKEN = "ваш-токен"
# Было:    BASE = f"https://api.telegram.org/bot{TOKEN}"
# Стало:
BASE = f"https://chat.company.com/api/bot/{TOKEN}"

# Отправка сообщения — без изменений:
requests.post(f"{BASE}/sendMessage", json={
    "chat_id": chat_id,
    "text": "Привет!",
})
```

> **Обратите внимание:** в URL Telegram токен идёт сразу после `bot` без `/`: `bot{TOKEN}/sendMessage`. В Chatter токен — отдельный сегмент пути: `bot/{TOKEN}/sendMessage`. Если вы используете raw HTTP-запросы, проверьте формат URL.

##### Шаг 4. Запустить бота

```bash
python bot.py
```

Бот подключится к Chatter, вызовет `getMe` (проверка токена) → `deleteWebhook` → запустит polling через `getUpdates`. Отправьте сообщение боту в чате Chatter — он ответит.

---

#### Примеры: типовые операции

**Текстовые сообщения и команды:**
```python
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, filters, CallbackContext

async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Привет! Я работаю в Chatter.")

async def echo(update: Update, context: CallbackContext):
    await update.message.reply_text(f"Вы написали: {update.message.text}")

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
application.run_polling()
```

**Inline-кнопки (callback_query):**
```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CallbackContext

async def ask(update: Update, context: CallbackContext):
    keyboard = [[
        InlineKeyboardButton("Да", callback_data="yes"),
        InlineKeyboardButton("Нет", callback_data="no"),
    ]]
    await update.message.reply_text(
        "Вам нравится Chatter?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

async def button(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()  # подтверждение нажатия
    await query.edit_message_text(f"Вы выбрали: {query.data}")

application.add_handler(CommandHandler("ask", ask))
application.add_handler(CallbackQueryHandler(button))
```

**Отправка и получение фото:**
```python
async def handle_photo(update: Update, context: CallbackContext):
    # Получить файл
    photo = update.message.photo[-1]  # наибольший размер
    file = await context.bot.get_file(photo.file_id)
    await file.download_to_drive("photo.jpg")

    # Отправить фото обратно
    with open("photo.jpg", "rb") as f:
        await context.bot.send_photo(
            chat_id=update.message.chat.id,
            photo=f,
            caption="Получил ваше фото!",
        )

application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
```

**Отправка документов:**
```python
async def send_report(update: Update, context: CallbackContext):
    with open("report.pdf", "rb") as f:
        await context.bot.send_document(
            chat_id=update.message.chat.id,
            document=f,
            caption="Отчёт за месяц",
        )
```

**Markdown-форматирование:**
```python
async def formatted(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "*Жирный*, _курсив_, `код`, [ссылка](https://example.com)",
        parse_mode="Markdown",
    )
```

---

#### Различия Chatter и Telegram Bot API

| Возможность | Telegram | Chatter | Комментарий |
|------------|---------|---------|-------------|
| `getUpdates` (polling) | Да | Да | Long polling до 30 сек |
| `setWebhook` / `deleteWebhook` | Да | Да | Полная совместимость |
| `sendMessage` + inline keyboard | Да | Да | |
| `editMessageText` | Да | Да | |
| `deleteMessage` | Да | Да | Soft delete |
| `sendPhoto` / `sendDocument` | Да | Да | Макс. 50 MB |
| `getFile` + скачивание | Да | Да | |
| `sendChatAction` (typing) | Да | Да | |
| `answerCallbackQuery` | Да | Да | |
| `getMe` | Да | Да | |
| Групповые чаты | Да | Да | Создаются через админку |
| `reply_to_message_id` | Да | Нет | Не поддерживается |
| `forwardMessage` | Да | Нет | Не поддерживается |
| `sendVenue` / `sendLocation` | Да | Нет | Не поддерживается |
| `sendSticker` | Да | Нет | Не поддерживается |
| `ReplyKeyboardMarkup` | Да | Нет | Только `InlineKeyboardMarkup` |
| `chat_id` по username (`@user`) | Да | Нет | Только числовой `chat_id` (= ID беседы) |
| Bot username в командах (`/start@bot`) | Да | Нет | Просто `/start` |
| `photo.width` / `photo.height` | Да | Всегда 0 | Размеры не вычисляются |

---

#### Переменные окружения (рекомендуемый подход)

Для удобства переключения между Telegram и Chatter используйте переменные окружения:

```python
import os
from telegram.ext import Application

TOKEN = os.environ["BOT_TOKEN"]
PLATFORM = os.environ.get("BOT_PLATFORM", "telegram")  # "telegram" или "chatter"
CHATTER_URL = os.environ.get("CHATTER_URL", "")

builder = Application.builder().token(TOKEN)
if PLATFORM == "chatter":
    api_url = CHATTER_URL.rstrip("/") + "/api/bot"
    builder = builder.base_url(api_url).base_file_url(api_url)
application = builder.build()
```

```bash
# Для Telegram:
BOT_TOKEN=123456:ABC-DEF python bot.py

# Для Chatter:
BOT_PLATFORM=chatter CHATTER_URL=https://chat.company.com BOT_TOKEN=ваш-токен python bot.py
```

---

#### FAQ / Troubleshooting

**Q: Бот запускается, но не получает сообщения.**
A: Проверьте:
1. Webhook URL в админке Chatter пуст (для polling-режима webhook не нужен)
2. Бот назначен пользователю (Админка → Пользователи → назначить бота)
3. Redis работает (polling хранит очередь обновлений в Redis)
4. Токен совпадает с тем, что в админке

**Q: Ошибка `409 Conflict: can't use getUpdates method while webhook is active`.**
A: У бота установлен webhook URL в админке. Очистите его (Админка → Боты → Редактировать → убрать Webhook URL) или вызовите `deleteWebhook` программно.

**Q: Бот отвечает в Telegram, но не в Chatter.**
A: Убедитесь, что `base_url` указывает на Chatter, а не на `api.telegram.org`. Проверьте, что `base_file_url` тоже указывает на Chatter (нужно для скачивания файлов).

**Q: Файлы / фото не скачиваются.**
A: Убедитесь, что `base_file_url` установлен в `{CHATTER_URL}/api/bot`. Без этого библиотека будет пытаться скачать файлы с `api.telegram.org`.

**Q: `photo.width` и `photo.height` равны 0.**
A: Это ожидаемое поведение — Chatter не вычисляет размеры изображений. Если вашему боту нужны размеры, вычислите их после скачивания (например, через `Pillow`).

**Q: `ReplyKeyboardMarkup` не работает.**
A: Chatter поддерживает только `InlineKeyboardMarkup` (кнопки под сообщением). `ReplyKeyboardMarkup` (кнопки вместо клавиатуры) не реализован. Используйте inline-кнопки или Quick Replies (настраиваются в админке бота).

**Q: Как запустить один и тот же бот одновременно в Telegram и Chatter?**
A: Запустите два экземпляра процесса с разными переменными окружения:
```bash
# Терминал 1 — Telegram
BOT_TOKEN=telegram-token python bot.py

# Терминал 2 — Chatter
BOT_PLATFORM=chatter CHATTER_URL=https://chat.company.com BOT_TOKEN=chatter-token python bot.py
```

---

### 7. Продакшн (nginx)

Используйте прилагаемый `nginx.conf` как основу. Ключевое — отключение буферизации для SSE:
```nginx
location ~ /chat/api/conversations/.*/stream {
    proxy_pass http://n8n-front:5000;
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 3600s;
}
```

## Push-уведомления (Web Push)

Платформа поддерживает push-уведомления через Web Push API — они приходят даже при неактивной вкладке или свёрнутом браузере.

### 1. Установка зависимости

```bash
pip install pywebpush
```

Или при использовании Docker — зависимость уже включена в `requirements.txt`.

### 2. Генерация VAPID-ключей

```bash
python -c "
from py_vapid import Vapid
from py_vapid.utils import b64urlencode
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
v = Vapid()
v.generate_keys()
print('VAPID_PRIVATE_KEY=' + v.private_pem().decode().replace('\n', '\\\\n'))
print('VAPID_PUBLIC_KEY=' + b64urlencode(v.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)))
"
```

### 3. Настройка .env

```env
VAPID_PRIVATE_KEY=-----BEGIN EC PRIVATE KEY-----\nМного букв...\n-----END EC PRIVATE KEY-----
VAPID_PUBLIC_KEY=BBase64-строка-публичного-ключа
VAPID_CLAIMS_EMAIL=mailto:admin@your-domain.com
```

- `VAPID_PRIVATE_KEY` — приватный ключ (PEM-формат, переносы строк заменены на `\n`)
- `VAPID_PUBLIC_KEY` — публичный ключ (base64url)
- `VAPID_CLAIMS_EMAIL` — email для идентификации отправителя (формат `mailto:...`)

### 4. Перезапуск

```bash
docker compose --env-file .env up -d --build
```

После перезапуска пользователи чата получат запрос на разрешение уведомлений. При согласии — push-уведомления будут приходить при каждом новом сообщении от бота.

---

## Настройка SSO-авторизации

Платформа поддерживает три способа входа для пользователей чата:
- **Логин/пароль** — работает по умолчанию, без дополнительной настройки
- **Google OAuth2** — вход через Google Workspace (корпоративные и обычные аккаунты)
- **Keycloak OIDC** — вход через корпоративную систему (ERP, Active Directory и т.д.)

SSO-кнопки появляются на странице входа только при заполненных переменных окружения. Без них страница выглядит как обычная форма логин/пароль.

При первом входе через SSO пользователь создаётся автоматически: username берётся из email (часть до `@`), ему назначаются боты с флагом «Доступен всем». Администратор может позже назначить дополнительных ботов и задать пароль для fallback-входа.

### Google OAuth2

#### 1. Создание проекта в Google Cloud Console

1. Откройте [Google Cloud Console](https://console.cloud.google.com/)
2. Создайте новый проект или выберите существующий
3. Перейдите в **APIs & Services → OAuth consent screen**
4. Выберите тип **Internal** (для Google Workspace) или **External** (для всех Google-аккаунтов)
5. Заполните:
   - **App name**: название вашего приложения (например, «Chatter»)
   - **User support email**: ваш email
   - **Developer contact email**: ваш email
6. На шаге **Scopes** добавьте:
   - `openid`
   - `email`
   - `profile`
7. Сохраните

#### 2. Создание OAuth2 Client ID

1. Перейдите в **APIs & Services → Credentials**
2. Нажмите **Create Credentials → OAuth client ID**
3. Тип: **Web application**
4. Название: например, «Chatter»
5. В **Authorized redirect URIs** добавьте:
   ```
   https://your-domain.com/chat/auth/google/callback
   ```
   Для локальной разработки:
   ```
   http://localhost:5001/chat/auth/google/callback
   ```
6. Нажмите **Create**
7. Скопируйте **Client ID** и **Client Secret**

#### 3. Настройка .env

```env
GOOGLE_CLIENT_ID=123456789-abcdef.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-ваш-секрет
GOOGLE_ALLOWED_DOMAINS=company.com,subsidiary.com
```

- `GOOGLE_CLIENT_ID` — Client ID из Google Cloud Console
- `GOOGLE_CLIENT_SECRET` — Client Secret из Google Cloud Console
- `GOOGLE_ALLOWED_DOMAINS` — список разрешённых email-доменов через запятую. Если пусто — допускаются любые Google-аккаунты. Если указано `company.com` — войти смогут только пользователи с email `@company.com`

#### 4. Перезапуск

```bash
docker compose --env-file .env up -d --build
```

На странице входа в чат появится кнопка **Google**.

---

### Keycloak OIDC (ERP)

#### 1. Создание клиента в Keycloak

1. Откройте админку Keycloak: `https://keycloak.your-domain.com/admin/`
2. Выберите нужный **Realm** (или создайте новый)
3. Перейдите в **Clients → Create client**
4. Заполните:
   - **Client type**: OpenID Connect
   - **Client ID**: например, `chatter` (это значение пойдёт в `KEYCLOAK_CLIENT_ID`)
5. Нажмите **Next**
6. Включите **Client authentication** (ON)
7. Убедитесь, что включён **Standard flow** (Authorization Code Flow)
8. Нажмите **Next**
9. В **Valid redirect URIs** добавьте:
   ```
   https://your-domain.com/chat/auth/keycloak/callback
   ```
   Для локальной разработки:
   ```
   http://localhost:5001/chat/auth/keycloak/callback
   ```
10. В **Web origins** добавьте:
    ```
    https://your-domain.com
    ```
11. Нажмите **Save**

#### 2. Получение Client Secret

1. Откройте созданный клиент
2. Перейдите на вкладку **Credentials**
3. Скопируйте **Client Secret**

#### 3. Настройка маппинга email (если не настроен)

По умолчанию Keycloak отдаёт email в токене. Убедитесь:

1. Перейдите в **Client Scopes → email → Mappers**
2. Убедитесь, что маппер **email** существует и включён
3. Если пользователи Keycloak подключены через LDAP/Active Directory — проверьте, что атрибут email синхронизируется

#### 4. Настройка .env

```env
KEYCLOAK_URL=https://keycloak.your-domain.com
KEYCLOAK_REALM=your-realm
KEYCLOAK_CLIENT_ID=chatter
KEYCLOAK_CLIENT_SECRET=ваш-client-secret-из-keycloak
```

- `KEYCLOAK_URL` — базовый URL Keycloak **без** trailing slash и без `/auth`. Примеры:
  - `https://keycloak.company.com` (Keycloak 17+)
  - `https://sso.company.com/auth` (Keycloak < 17, с `/auth` в пути)
- `KEYCLOAK_REALM` — название realm в Keycloak (по умолчанию `master`)
- `KEYCLOAK_CLIENT_ID` — Client ID, указанный при создании клиента
- `KEYCLOAK_CLIENT_SECRET` — секрет со вкладки Credentials

#### 5. Перезапуск

```bash
docker compose --env-file .env up -d --build
```

На странице входа в чат появится кнопка **ERP**.

---

### Как работает SSO

| Сценарий | Что происходит |
|----------|---------------|
| Первый вход через SSO | Создаётся новый пользователь, username = часть email до `@`, назначаются публичные боты |
| Повторный вход через SSO | Находится по provider ID, сессия восстанавливается |
| У пользователя уже есть аккаунт с тем же email | Аккаунты связываются, SSO-логин привязывается к существующему пользователю |
| Админ заранее создал пользователя с email | При SSO-входе аккаунт привяжется автоматически |
| SSO недоступен | Пользователь входит по логину/паролю (если админ задал пароль) |
| Пользователь вошёл через SSO, пароль не задан | При попытке входа по паролю — сообщение «Используйте SSO или обратитесь к администратору» |

### Управление доступом ботов для SSO-пользователей

В настройках каждого бота (Админка → Боты → Редактирование) есть чекбокс **«Доступен всем»**. Боты с этим флагом автоматически назначаются новым пользователям, созданным через SSO.

Для назначения остальных ботов — откройте профиль пользователя в админке и отметьте нужных ботов.

---

## Структура проекта

```
N8n_Front/
├── server/
│   ├── app.py              # Flask app factory
│   ├── config.py            # Конфигурация (включая OAuth)
│   ├── models.py            # SQLAlchemy модели
│   ├── auth.py              # Авторизация админов
│   ├── chat_auth.py         # Авторизация пользователей чата (пароль + Google + Keycloak)
│   ├── oauth.py             # Authlib OAuth провайдеры (Google, Keycloak)
│   ├── views.py             # Админка (dashboard, CRUD ботов/юзеров, аудит)
│   ├── bot_api.py           # Telegram-совместимый Bot API (включая getUpdates)
│   ├── chat_api.py          # API для фронтенда чата
│   ├── chat_views.py        # Страница чата
│   ├── webhook.py           # Исходящие вебхуки / Redis-очередь для polling
│   ├── sse.py               # SSE брокер (Redis pub/sub)
│   ├── file_handler.py      # Загрузка/скачивание файлов
│   ├── seed.py              # CLI-команда создания первого админа
│   └── templates/           # Jinja2 шаблоны (админка + чат)
├── chatter_bot.py          # Python-хелпер для миграции ботов с Telegram
├── Dockerfile
├── docker-compose.yml
├── nginx.conf
└── .env
```
