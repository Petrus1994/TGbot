# Database Schema

Этот документ описывает логическую схему базы данных проекта.

Цель схемы:
- зафиксировать основные таблицы
- зафиксировать поля
- зафиксировать связи между таблицами
- зафиксировать ключевые ограничения
- подготовить основу для дальнейшей реализации PostgreSQL schema

---

## 1. Общие принципы

### 1.1. Основной принцип
Почти все бизнес-данные должны быть привязаны к:
- `user_id`
- `goal_id` (если данные относятся к конкретной цели)

### 1.2. Multi-goal isolation
Данные разных целей одного пользователя не должны смешиваться.
Для этого:
- check-ins всегда привязаны к `goal_id`
- proof всегда привязан к `goal_id` и `daily_checkin_id`
- goal session хранится отдельно для каждой цели
- progress считается отдельно по каждой цели

### 1.3. Файлы
Сами файлы не хранятся в PostgreSQL.
В базе хранятся только:
- метаданные файла
- ссылка на storage key
- связи файла с goal/check-in/step

### 1.4. Времена
Во всех таблицах рекомендуется хранить:
- `created_at`
- `updated_at` там, где данные изменяются
- даты и времена в UTC
- timezone пользователя хранить отдельно в профиле/контексте

---

## 2. Таблица users

Назначение:
Основная таблица пользователей Telegram-бота.

Поля:
- `id` bigint / uuid, primary key
- `telegram_user_id` bigint, unique, not null
- `telegram_chat_id` bigint, not null
- `username` text, null
- `first_name` text, null
- `last_name` text, null
- `language_code` text, null
- `timezone` text, null
- `status` text, not null
- `is_blocked` boolean, not null, default false
- `created_at` timestamptz, not null
- `updated_at` timestamptz, not null
- `last_seen_at` timestamptz, null

Ограничения:
- unique(`telegram_user_id`)

Индексы:
- index on `telegram_chat_id`
- index on `status`

---

## 3. Таблица user_profiles

Назначение:
Хранит общую анкету и общие характеристики пользователя.

Поля:
- `id` bigint / uuid, primary key
- `user_id` fk -> users.id, not null
- `age` integer, null
- `sex` text, null
- `height_cm` integer, null
- `weight_kg` numeric, null
- `activity_level` text, null
- `experience_level` text, null
- `constraints_json` jsonb, null
- `preferences_json` jsonb, null
- `motivation_json` jsonb, null
- `onboarding_completed_at` timestamptz, null
- `created_at` timestamptz, not null
- `updated_at` timestamptz, not null

Ограничения:
- unique(`user_id`)

Индексы:
- index on `user_id`

---

## 4. Таблица goals

Назначение:
Хранит отдельные цели пользователя.

Поля:
- `id` bigint / uuid, primary key
- `user_id` fk -> users.id, not null
- `title` text, not null
- `description` text, null
- `category` text, null
- `target_metric_name` text, null
- `target_metric_value` numeric, null
- `target_date` date, null
- `status` text, not null
- `priority` integer, null
- `time_budget_value` numeric, null
- `time_budget_unit` text, null
- `created_at` timestamptz, not null
- `updated_at` timestamptz, not null
- `activated_at` timestamptz, null
- `completed_at` timestamptz, null

Ограничения:
- fk(`user_id`) -> users.id

Индексы:
- index on `user_id`
- index on `status`
- index on (`user_id`, `status`)
- index on `target_date`

---

## 5. Таблица goal_sessions

Назначение:
Хранит состояние сценария бота отдельно для каждой цели.

Поля:
- `id` bigint / uuid, primary key
- `user_id` fk -> users.id, not null
- `goal_id` fk -> goals.id, not null
- `state` text, not null
- `substate` text, null
- `context_json` jsonb, null
- `updated_at` timestamptz, not null
- `created_at` timestamptz, not null

Ограничения:
- unique(`goal_id`)
- fk(`user_id`) -> users.id
- fk(`goal_id`) -> goals.id

Индексы:
- index on `user_id`
- index on `goal_id`
- index on `state`

---

## 6. Таблица user_chat_context

Назначение:
Хранит глобальный chat-context пользователя, включая активную цель.

Поля:
- `id` bigint / uuid, primary key
- `user_id` fk -> users.id, not null
- `active_goal_id` fk -> goals.id, null
- `last_selected_goal_id` fk -> goals.id, null
- `state` text, null
- `substate` text, null
- `updated_at` timestamptz, not null
- `created_at` timestamptz, not null

Ограничения:
- unique(`user_id`)

Индексы:
- index on `user_id`
- index on `active_goal_id`

---

## 7. Таблица plans

Назначение:
Хранит версии плана по конкретной цели.

Поля:
- `id` bigint / uuid, primary key
- `goal_id` fk -> goals.id, not null
- `version` integer, not null
- `status` text, not null
- `source` text, null
- `generation_model` text, null
- `generation_prompt_version` text, null
- `summary_text` text, null
- `created_at` timestamptz, not null
- `updated_at` timestamptz, not null
- `accepted_at` timestamptz, null
- `archived_at` timestamptz, null

Ограничения:
- unique(`goal_id`, `version`)

Индексы:
- index on `goal_id`
- index on (`goal_id`, `status`)
- index on `status`

---

## 8. Таблица plan_steps

Назначение:
Хранит отдельные шаги конкретного плана.

Поля:
- `id` bigint / uuid, primary key
- `plan_id` fk -> plans.id, not null
- `step_order` integer, not null
- `title` text, not null
- `description` text, null
- `instructions_json` jsonb, null
- `frequency_type` text, null
- `expected_proof_type` text, null
- `is_required` boolean, not null, default true
- `start_day_offset` integer, null
- `end_day_offset` integer, null
- `created_at` timestamptz, not null
- `updated_at` timestamptz, not null

Ограничения:
- unique(`plan_id`, `step_order`)

Индексы:
- index on `plan_id`
- index on `frequency_type`

---

## 9. Таблица daily_checkins

Назначение:
Хранит ежедневный отчет пользователя по конкретной цели.

Поля:
- `id` bigint / uuid, primary key
- `user_id` fk -> users.id, not null
- `goal_id` fk -> goals.id, not null
- `plan_id` fk -> plans.id, not null
- `checkin_date` date, not null
- `status` text, not null
- `text_report` text, null
- `self_score` integer, null
- `submitted_at` timestamptz, null
- `reviewed_at` timestamptz, null
- `created_at` timestamptz, not null
- `updated_at` timestamptz, not null

Ограничения:
- unique(`user_id`, `goal_id`, `checkin_date`)

Индексы:
- index on `user_id`
- index on `goal_id`
- index on `checkin_date`
- index on (`goal_id`, `checkin_date`)
- index on `status`

---

## 10. Таблица step_reports

Назначение:
Хранит статус выполнения конкретных шагов внутри daily check-in.

Поля:
- `id` bigint / uuid, primary key
- `daily_checkin_id` fk -> daily_checkins.id, not null
- `plan_step_id` fk -> plan_steps.id, not null
- `status` text, not null
- `comment` text, null
- `created_at` timestamptz, not null
- `updated_at` timestamptz, not null

Ограничения:
- unique(`daily_checkin_id`, `plan_step_id`)

Индексы:
- index on `daily_checkin_id`
- index on `plan_step_id`
- index on `status`

---

## 11. Таблица files

Назначение:
Хранит метаданные пользовательских файлов, которые реально лежат в AWS S3.

Поля:
- `id` bigint / uuid, primary key
- `user_id` fk -> users.id, not null
- `storage_provider` text, not null
- `bucket_name` text, not null
- `storage_key` text, not null
- `mime_type` text, not null
- `size_bytes` bigint, not null
- `checksum_sha256` text, null
- `telegram_file_id` text, null
- `telegram_file_unique_id` text, null
- `uploaded_at` timestamptz, not null
- `created_at` timestamptz, not null

Ограничения:
- unique(`storage_provider`, `bucket_name`, `storage_key`)

Индексы:
- index on `user_id`
- index on `telegram_file_unique_id`
- index on `uploaded_at`

---

## 12. Таблица checkin_files

Назначение:
Связывает файлы с daily check-in.

Поля:
- `id` bigint / uuid, primary key
- `daily_checkin_id` fk -> daily_checkins.id, not null
- `file_id` fk -> files.id, not null
- `kind` text, not null
- `created_at` timestamptz, not null

Ограничения:
- unique(`daily_checkin_id`, `file_id`)

Индексы:
- index on `daily_checkin_id`
- index on `file_id`
- index on `kind`

---

## 13. Таблица proof_validations

Назначение:
Хранит результат проверки proof по шагу.

Поля:
- `id` bigint / uuid, primary key
- `daily_checkin_id` fk -> daily_checkins.id, not null
- `plan_step_id` fk -> plan_steps.id, not null
- `file_id` fk -> files.id, not null
- `status` text, not null
- `confidence` numeric, null
- `reason_code` text, null
- `model_name` text, null
- `user_message` text, null
- `created_at` timestamptz, not null

Индексы:
- index on `daily_checkin_id`
- index on `plan_step_id`
- index on `file_id`
- index on `status`
- index on `created_at`

---

## 14. Таблица reminders

Назначение:
Хранит настройки напоминаний по целям.

Поля:
- `id` bigint / uuid, primary key
- `user_id` fk -> users.id, not null
- `goal_id` fk -> goals.id, not null
- `enabled` boolean, not null, default true
- `local_time` time, not null
- `timezone` text, not null
- `channel` text, not null
- `message_template_key` text, null
- `created_at` timestamptz, not null
- `updated_at` timestamptz, not null

Индексы:
- index on `user_id`
- index on `goal_id`
- index on `enabled`
- index on (`enabled`, `timezone`, `local_time`)

---

## 15. Таблица reminder_deliveries

Назначение:
Хранит историю отправок reminders.

Поля:
- `id` bigint / uuid, primary key
- `reminder_id` fk -> reminders.id, not null
- `delivery_date` date, not null
- `scheduled_for` timestamptz, not null
- `sent_at` timestamptz, null
- `status` text, not null
- `error_text` text, null
- `telegram_message_id` text, null
- `created_at` timestamptz, not null

Ограничения:
- unique(`reminder_id`, `delivery_date`)

Индексы:
- index on `reminder_id`
- index on `delivery_date`
- index on `status`
- index on `scheduled_for`

---

## 16. Таблица inbound_events

Назначение:
Хранит сырые входящие события от Telegram для идемпотентной обработки и аудита.

Поля:
- `id` bigint / uuid, primary key
- `source` text, not null
- `external_event_id` text, not null
- `payload_json` jsonb, not null
- `status` text, not null
- `received_at` timestamptz, not null
- `processed_at` timestamptz, null
- `error_text` text, null
- `created_at` timestamptz, not null

Ограничения:
- unique(`source`, `external_event_id`)

Индексы:
- index on `status`
- index on `received_at`

---

## 17. Таблица outbound_messages

Назначение:
Хранит лог исходящих сообщений бота.

Поля:
- `id` bigint / uuid, primary key
- `user_id` fk -> users.id, not null
- `goal_id` fk -> goals.id, null
- `channel` text, not null
- `message_type` text, not null
- `request_payload_json` jsonb, not null
- `response_payload_json` jsonb, null
- `status` text, not null
- `error_text` text, null
- `created_at` timestamptz, not null
- `sent_at` timestamptz, null

Индексы:
- index on `user_id`
- index on `goal_id`
- index on `status`
- index on `created_at`

---

## 18. Таблица ai_runs

Назначение:
Хранит метаданные AI-вызовов.

Поля:
- `id` bigint / uuid, primary key
- `user_id` fk -> users.id, not null
- `goal_id` fk -> goals.id, null
- `purpose` text, not null
- `model` text, not null
- `input_tokens` integer, null
- `output_tokens` integer, null
- `status` text, not null
- `request_hash` text, null
- `response_json` jsonb, null
- `error_text` text, null
- `created_at` timestamptz, not null
- `completed_at` timestamptz, null

Индексы:
- index on `user_id`
- index on `goal_id`
- index on `purpose`
- index on `status`
- index on `created_at`

---

## 19. Основные связи между таблицами

### User level
- `users` 1 -> 1 `user_profiles`
- `users` 1 -> many `goals`
- `users` 1 -> 1 `user_chat_context`
- `users` 1 -> many `reminders`
- `users` 1 -> many `files`
- `users` 1 -> many `outbound_messages`
- `users` 1 -> many `ai_runs`

### Goal level
- `goals` 1 -> 1 `goal_sessions`
- `goals` 1 -> many `plans`
- `goals` 1 -> many `daily_checkins`
- `goals` 1 -> many `reminders`

### Plan level
- `plans` 1 -> many `plan_steps`

### Check-in level
- `daily_checkins` 1 -> many `step_reports`
- `daily_checkins` 1 -> many `checkin_files`
- `daily_checkins` 1 -> many `proof_validations`

### File level
- `files` 1 -> many `checkin_files`
- `files` 1 -> many `proof_validations`

---

## 20. Ключевые ограничения, которые обязательны

### 20.1. Уникальность пользователя
- `telegram_user_id` должен быть уникальным

### 20.2. Один daily check-in на цель в день
- unique(`user_id`, `goal_id`, `checkin_date`)

### 20.3. Уникальность версии плана
- unique(`goal_id`, `version`)

### 20.4. Уникальность входящего события Telegram
- unique(`source`, `external_event_id`)

### 20.5. Уникальность reminder delivery на дату
- unique(`reminder_id`, `delivery_date`)

### 20.6. Уникальность шага внутри check-in
- unique(`daily_checkin_id`, `plan_step_id`)

---

## 21. Что еще нужно сделать после этого документа

После фиксации логической схемы следующим шагом нужно:

1. решить, используете ли вы `uuid` или `bigint` как primary keys
2. превратить эту схему в реальный SQL schema / migration files
3. зафиксировать enum-значения для статусов
4. подготовить seed / test data для разработки
5. проверить сценарии:
   - одна цель
   - две цели
   - proof accepted / rejected / uncertain
   - reminders
   - weekly summaries
