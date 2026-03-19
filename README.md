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
v = Vapid()
v.generate_keys()
print('VAPID_PRIVATE_KEY=' + v.private_pem().decode().replace('\n', '\\\\n'))
print('VAPID_PUBLIC_KEY=' + v.public_key)
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
│   ├── bot_api.py           # Telegram-совместимый Bot API
│   ├── chat_api.py          # API для фронтенда чата
│   ├── chat_views.py        # Страница чата
│   ├── webhook.py           # Исходящие вебхуки к n8n
│   ├── sse.py               # SSE брокер (Redis pub/sub)
│   ├── file_handler.py      # Загрузка/скачивание файлов
│   ├── seed.py              # CLI-команда создания первого админа
│   └── templates/           # Jinja2 шаблоны (админка + чат)
├── Dockerfile
├── docker-compose.yml
├── nginx.conf
└── .env
```
