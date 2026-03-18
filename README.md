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
| `sendMessage` | Отправка текста (`chat_id`, `text`, `parse_mode`) |
| `sendDocument` | Отправка файла (`chat_id`, `document`, `caption`) |
| `sendPhoto` | Отправка изображения (`chat_id`, `photo`, `caption`) |
| `getFile` | Ссылка на скачивание файла (`file_id`) |
| `setWebhook` | Регистрация webhook URL |
| `deleteWebhook` | Удаление webhook |
| `getWebhookInfo` | Текущий webhook |

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

### 6. Продакшн (nginx)

Используйте прилагаемый `nginx.conf` как основу. Ключевое — отключение буферизации для SSE:
```nginx
location ~ /chat/api/conversations/.*/stream {
    proxy_pass http://n8n-front:5000;
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 3600s;
}
```

## Структура проекта

```
N8n_Front/
├── server/
│   ├── app.py              # Flask app factory
│   ├── config.py            # Конфигурация
│   ├── models.py            # SQLAlchemy модели (7 моделей)
│   ├── auth.py              # Авторизация админов
│   ├── chat_auth.py         # Авторизация пользователей чата
│   ├── views.py             # Админка (dashboard, CRUD ботов/юзеров, аудит)
│   ├── bot_api.py           # Telegram-совместимый Bot API
│   ├── chat_api.py          # API для фронтенда чата
│   ├── chat_views.py        # Страница чата
│   ├── webhook.py           # Исходящие вебхуки к n8n
│   ├── sse.py               # SSE брокер (in-memory pub/sub)
│   ├── file_handler.py      # Загрузка/скачивание файлов
│   ├── seed.py              # CLI-команда создания первого админа
│   └── templates/           # Jinja2 шаблоны (админка + чат)
├── Dockerfile
├── docker-compose.yml
├── nginx.conf
└── envfile
```
