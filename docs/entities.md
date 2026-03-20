# Entities

## 1. User
Пользователь Telegram-бота.

Поля:
- id
- telegram_user_id
- telegram_chat_id
- username
- first_name
- last_name
- language_code
- timezone
- created_at
- updated_at
- last_seen_at
- is_blocked
- status

---

## 2. UserProfile
Анкета пользователя с общей информацией о нем.

Поля:
- id
- user_id
- age
- sex
- height_cm
- weight_kg
- activity_level
- experience_level
- constraints_json
- preferences_json
- motivation_json
- onboarding_completed_at

---

## 3. Goal
Отдельная цель пользователя.
Один пользователь может иметь несколько целей.

Поля:
- id
- user_id
- title
- description
- category
- target_metric_name
- target_metric_value
- target_date
- status
- priority
- created_at
- updated_at
- activated_at
- completed_at

---

## 4. GoalSession
Состояние сценария бота по конкретной цели.
Нужно, чтобы несколько целей не путались между собой.

Поля:
- id
- user_id
- goal_id
- state
- substate
- context_json
- updated_at

---

## 5. UserChatContext
Глобальный контекст чата пользователя.
Хранит, какая цель сейчас выбрана в чате как активная.

Поля:
- id
- user_id
- active_goal_id
- last_selected_goal_id
- updated_at

---

## 6. Plan
План достижения цели.
У одной цели может быть несколько версий плана.

Поля:
- id
- goal_id
- version
- status
- source
- generation_model
- generation_prompt_version
- created_at

---

## 7. PlanStep
Отдельный шаг плана.

Поля:
- id
- plan_id
- step_order
- title
- description
- instructions_json
- frequency_type
- expected_proof_type
- is_required
- start_day_offset
- end_day_offset
- created_at

---

## 8. DailyCheckin
Ежедневный отчет по конкретной цели.

Поля:
- id
- user_id
- goal_id
- plan_id
- checkin_date
- status
- text_report
- self_score
- submitted_at
- reviewed_at
- created_at

---

## 9. StepReport
Отчет по конкретному шагу внутри daily check-in.

Поля:
- id
- daily_checkin_id
- plan_step_id
- status
- comment
- created_at

---

## 10. File
Метаданные файла, который прислал пользователь.

Поля:
- id
- user_id
- storage_provider
- storage_key
- bucket_name
- mime_type
- size_bytes
- checksum_sha256
- telegram_file_id
- telegram_file_unique_id
- uploaded_at

---

## 11. CheckinFile
Связка между daily check-in и файлом.

Поля:
- id
- daily_checkin_id
- file_id
- kind
- created_at

---

## 12. ProofValidation
Результат проверки фотопруфа или скриншота.

Поля:
- id
- daily_checkin_id
- plan_step_id
- file_id
- status
- confidence
- reason_code
- model_name
- created_at

---

## 13. Reminder
Настройка напоминания по цели.

Поля:
- id
- user_id
- goal_id
- enabled
- local_time
- timezone
- channel
- message_template_key
- created_at
- updated_at

---

## 14. ReminderDelivery
История отправок напоминаний.

Поля:
- id
- reminder_id
- delivery_date
- scheduled_for
- sent_at
- status
- error_text
- telegram_message_id

---

## 15. InboundEvent
Сырое входящее событие от Telegram.

Поля:
- id
- source
- external_event_id
- payload_json
- received_at
- processed_at
- status
- error_text

---

## 16. OutboundMessage
Лог исходящих сообщений бота.

Поля:
- id
- user_id
- channel
- message_type
- request_payload_json
- response_payload_json
- status
- created_at
- sent_at
- error_text

---

## 17. AIRun
Метаданные AI-вызова.

Поля:
- id
- user_id
- goal_id
- purpose
- model
- input_tokens
- output_tokens
- status
- request_hash
- response_json
- created_at
- completed_at
- error_text
