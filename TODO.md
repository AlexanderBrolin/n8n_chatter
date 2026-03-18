# TODO

## Реализовано

### Фаза 1: Фундамент
- [x] Структура проекта, config.py, app.py (factory pattern)
- [x] Модели данных (AdminUser, ChatUser, Bot, Conversation, Message, FileAttachment, AuditLog, user_bot_access M2M)
- [x] Админ-авторизация (сессии, декораторы login_required / superadmin_required)
- [x] seed.py — CLI-команда создания первого админа
- [x] base.html, login.html — шаблоны админки
- [x] Dockerfile, docker-compose.yml, .gitignore, envfile, nginx.conf

### Фаза 2: Админка
- [x] Dashboard со статистикой (боты, пользователи, сообщения, чаты) + последние записи аудита
- [x] CRUD ботов (создание, редактирование, генерация токена, toggle active, удаление)
- [x] CRUD пользователей чата (создание, редактирование, смена пароля, toggle block, удаление)
- [x] Назначение доступа пользователь ↔ бот (M2M через чекбоксы)
- [x] Аудит-лог (пагинация)

### Фаза 3: Bot API
- [x] Telegram-совместимые эндпоинты: getMe, sendMessage, sendDocument, sendPhoto, getFile
- [x] setWebhook, deleteWebhook, getWebhookInfo (для n8n community nodes)
- [x] Исходящий webhook к n8n (Telegram Update format, fire-and-forget)
- [x] Скачивание файлов через Bot API

### Фаза 4: Чат-интерфейс
- [x] Авторизация пользователей чата (отдельные сессии от админки)
- [x] Chat API: список ботов, conversations, messages (пагинация), отправка сообщений
- [x] Страница чата (Alpine.js): sidebar с ботами/чатами, область сообщений, ввод текста
- [x] Markdown-рендеринг (marked.js)
- [x] Множественные файлы в одном сообщении

### Фаза 5: SSE + файлы
- [x] SSE брокер (in-memory pub/sub, queue-based)
- [x] SSE эндпоинт + подключение Alpine.js
- [x] Загрузка файлов (user → n8n через webhook, n8n → user через Bot API)
- [x] Превью изображений inline, карточки документов

### Фаза 6: Polish
- [x] Мобильная адаптация (sidebar схлопывается)
- [x] nginx конфигурация для SSE (proxy_buffering off)

### Фаза 7: Надёжность и UX
- [x] SSE auto-reconnect с exponential backoff (per-conversation + user-level)
- [x] Индикатор "бот печатает..." (typing indicator) + sendChatAction Bot API
- [x] Многострочный ввод текста (Shift+Enter — новая строка, Enter — отправить)
- [x] Пустые состояния (нет ботов, нет чатов, нет сообщений — подсказки пользователю)
- [x] Индикатор загрузки при отправке сообщения/файла (spinner на кнопке, disabled inputs)
- [x] Счётчик непрочитанных сообщений в sidebar (badge с числом)
- [x] Уведомления (звук + browser Notification + badge в заголовке вкладки)
- [x] Обработка ошибок webhook (retry с backoff до 3 попыток, логирование)
- [x] Валидация размера файла на фронтенде до загрузки (лимит 50 МБ)
- [x] User-level SSE stream для уведомлений во всех чатах

### Дополнительно
- [x] n8n Community Nodes: пакет n8n-nodes-n8nfront (Trigger + Action ноды)

### Фаза 8: Масштабирование
- [x] Redis pub/sub вместо in-memory SSE брокера (для нескольких workers)
- [x] Gunicorn workers > 1 (настраивается через GUNICORN_WORKERS, по умолчанию 2)
- [x] Пагинация в админке (боты, пользователи — по 20 на страницу)

### Фаза 9: Функциональность
- [x] Поиск по сообщениям (PostgreSQL full-text search с русской конфигурацией + ILIKE fallback)
- [x] Удаление сообщений (soft delete — пользователем своих + ботом через deleteMessage API)
- [x] Редактирование сообщений (editMessageText в Bot API, отметка «ред.» в UI)
- [x] Inline-кнопки (reply_markup в Bot API, callback_query webhook — Telegram-совместимо)
- [x] Групповые чаты (conversation_members M2M, админка CRUD, sender_name в UI)
- [x] Шаблоны быстрых ответов для ботов (QuickReply модель, управление в админке, pill-кнопки в чате)

---

## Осталось сделать

### Авторизация
- [ ] Google OAuth для пользователей чата
- [ ] Keycloak SSO интеграция
- [ ] Смена пароля пользователем чата (self-service)

### n8n Community Nodes
- [x] Операция downloadFile (скачать файл как binary для обработки в n8n)
- [x] Операция editMessage (editMessageText)
- [x] Операция deleteMessage
- [x] Reply markup (inline-кнопки) в sendMessage и editMessageText
- [x] Callback query событие в Trigger-ноде
- [x] Операция sendChatAction (индикатор набора)
- [x] Версия 2.0.0, пакет готов к публикации (`npm publish`)
- [ ] Опубликовать в npm registry
- [ ] Добавить в n8n Creator Portal для верификации

### DevOps
- [ ] CI/CD pipeline (GitHub Actions или GitLab CI)
- [ ] Alembic миграции (сейчас db.create_all())
- [ ] Health check endpoint (/healthz)
- [ ] Prometheus метрики (сообщений/сек, webhook latency)
- [ ] Бэкап PostgreSQL (cron + pg_dump)
- [ ] Rate limiting на Bot API и Chat API
