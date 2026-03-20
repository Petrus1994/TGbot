# Stack Decisions

Этот документ фиксирует, какие технологии используются в проекте и зачем они нужны.

---

## 1. Общий принцип

Для MVP проект должен быть максимально простым:
- один backend
- одна база данных
- одно хранилище файлов
- один scheduler/worker
- один Telegram-бот

Без микросервисов и лишней сложности.

---

## 2. Telegram

### Выбор
Telegram Bot API

### Зачем
Нужен для общения пользователя с ботом:
- команды
- сообщения
- кнопки
- отправка и получение фото
- reminders
- progress messages
- weekly summaries

---

## 3. Backend

### Выбор
Один backend-сервис

### Зачем
Backend отвечает за:
- бизнес-логику
- работу с базой данных
- работу с AI
- управление целями
- check-ins
- proof validation flow
- reminders
- аудит событий

### Примечание
Конкретный backend framework выбирает разработчик.
Главное требование: backend должен поддерживать API, работу с PostgreSQL, storage и scheduler.

---

## 4. База данных

### Выбор
PostgreSQL

### Зачем
Нужна для хранения:
- пользователей
- целей
- планов
- шагов плана
- check-ins
- reminders
- сессий
- событий
- логов
- ссылок на файлы

### Почему PostgreSQL
- надежная
- хорошо подходит для backend-проектов
- поддерживает JSONB
- подходит для сложных связей между сущностями

---

## 5. Storage для файлов

### Выбор
S3-compatible storage

Возможные варианты:
- Supabase Storage
- AWS S3
- Cloudflare R2

### Зачем
Нужно хранить:
- фотопруфы
- скриншоты
- другие пользовательские файлы

### Важно
Сами файлы не должны храниться в PostgreSQL как бинарные данные.
В PostgreSQL должны храниться только метаданные файлов.

---

## 6. AI provider

### Выбор
OpenAI API

### Зачем
Используется для:
- генерации плана по цели
- корректировки плана
- weekly summaries
- мотивационных сообщений
- анализа proof и изображений
- определения, подтверждает ли proof выполнение шага

### Важно
AI должен работать с контекстом одной конкретной цели, а не со всей историей пользователя сразу.

---

## 7. Scheduler / background jobs

### Выбор
Один scheduler или worker-процесс

### Зачем
Нужен для:
- ежедневных reminders
- ежедневных progress messages
- weekly summaries
- фоновых AI-задач
- повторных попыток при ошибках отправки

### Важно
Напоминания должны учитывать:
- timezone пользователя
- goal_id
- дедупликацию отправок

---

## 8. Deploy

### Выбор
Один backend deploy + одна база + одно storage

Возможные платформы:
- Render
- Railway
- VPS
- Docker-based hosting

### Зачем
Нужно развернуть:
- backend
- webhook endpoint
- scheduler
- доступ к PostgreSQL
- доступ к storage

### Рекомендация
Для MVP выбрать максимально простой managed hosting.

---

## 9. Environments

Должны быть как минимум 3 окружения:

### local
Для локальной разработки.

### staging
Для тестирования фич перед production.

### production
Для реальных пользователей.

---

## 10. Secrets / env variables

Проект должен хранить секреты отдельно от кода.

Основные секреты:
- TELEGRAM_BOT_TOKEN
- DATABASE_URL
- OPENAI_API_KEY
- STORAGE_ACCESS_KEY
- STORAGE_SECRET_KEY
- STORAGE_BUCKET_NAME
- APP_BASE_URL
- INTERNAL_API_SECRET

### Важно
Секреты нельзя хранить в коде и нельзя коммитить в репозиторий.

---

## 11. Observability

### Минимальные требования
- structured logs
- логирование ошибок
- логирование входящих Telegram events
- логирование исходящих сообщений
- логирование AI runs
- логирование reminder deliveries

### Зачем
Чтобы понимать:
- почему бот не ответил
- почему reminder не отправился
- почему proof не прошел
- где именно произошла ошибка

---

## 12. Security

### Минимальные требования
- проверка доступа пользователя только к своим целям
- проверка доступа только к своим check-ins и файлам
- дедупликация Telegram events
- ограничение размера файлов
- private file storage
- защита секретов
- rate limiting на критичных endpoints

---

## 13. GitHub

### Выбор
GitHub как основное место хранения проекта

### Зачем
Там должны храниться:
- код
- документация
- история изменений
- задачи через issues при необходимости

### Структура
- `docs/` — документация
- `src/` или другая папка с кодом
- `.env.example`
- `README.md`

---

## 14. Документация

Основные документы проекта хранятся в папке `docs/`.

Обязательные файлы:
- `product_flow.md`
- `entities.md`
- `statuses.md`
- `events.md`
- `backend_commands.md`
- `backend_responses.md`
- `multi_goal_rules.md`
- `stack_decisions.md`

---

## 15. MVP architecture decision

Для первой версии принимается следующая архитектура:

- Telegram bot
- один backend
- PostgreSQL
- S3-compatible storage
- OpenAI API
- scheduler / background jobs
- GitHub для кода и docs

Это считается базовой архитектурой проекта.
