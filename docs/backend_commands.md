# Backend Commands

Этот документ описывает, какие команды backend должен уметь выполнять для работы Telegram-бота.

---

## 1. Пользователь и чат

### get_or_create_user_by_telegram
Находит пользователя по Telegram-данным или создает нового.

Вход:
- telegram_user_id
- telegram_chat_id
- username
- first_name
- last_name
- language_code

Выход:
- user_id
- is_new_user
- user_context

---

### get_user_context
Возвращает базовый контекст пользователя.

Вход:
- user_id

Выход:
- user_id
- timezone
- active_goal_id
- reminders_enabled
- onboarding_completed

---

### get_chat_context
Возвращает текущий контекст чата пользователя.

Вход:
- user_id

Выход:
- active_goal_id
- active_goal_title
- current_bot_state
- current_bot_substate
- has_other_active_goals


---

### clear_chat_state
Очищает глобальное состояние чата.

Вход:
- user_id

Выход:
- success

---

### update_user_timezone
Обновляет часовой пояс пользователя.

Вход:
- user_id
- timezone

Выход:
- success
- updated_user_context

---

## 2. Цели

### create_goal
Создает новую цель пользователя.

Вход:
- user_id
- title
- description
- category
- target_date
- priority

Выход:
- goal_id
- goal_context

---

### list_user_goals
Возвращает список целей пользователя.

Вход:
- user_id

Выход:
- goals[]

---

### get_goal_context
Возвращает полный контекст по выбранной цели.

Вход:
- user_id
- goal_id

Выход:
- goal_context

---

### update_goal
Обновляет данные цели.

Вход:
- user_id
- goal_id
- patch_data

Выход:
- updated_goal_context

---

### change_goal_status
Меняет статус цели.

Вход:
- user_id
- goal_id
- status

Выход:
- updated_goal_context

---

### request_goal_replanning
Запускает пересборку плана по цели.

Вход:
- user_id
- goal_id
- reason

Выход:
- success
- goal_context

---

### complete_goal
Отмечает цель как завершенную.

Вход:
- user_id
- goal_id

Выход:
- updated_goal_context

---

### pause_goal
Ставит цель на паузу.

Вход:
- user_id
- goal_id

Выход:
- updated_goal_context

---

### resume_goal
Возобновляет выполнение цели.

Вход:
- user_id
- goal_id

Выход:
- updated_goal_context

---

## 3. Профилирование

### start_goal_profiling
Начинает сбор контекста по цели.

Вход:
- user_id
- goal_id

Выход:
- profiling_state

---

### get_current_profiling_question
Возвращает текущий вопрос, который бот должен задать.

Вход:
- user_id
- goal_id

Выход:
- question_key
- question_text
- profiling_progress

---

### submit_profiling_answer
Сохраняет ответ пользователя на вопрос.

Вход:
- user_id
- goal_id
- answer_payload

Выход:
- profiling_state
- next_question_or_completion_flag

---

### get_profiling_state
Возвращает текущее состояние профилирования.

Вход:
- user_id
- goal_id

Выход:
- profiling_state

---

### complete_profiling_if_ready
Проверяет, достаточно ли данных для завершения профилирования.

Вход:
- user_id
- goal_id

Выход:
- is_completed
- missing_fields[]

---

## 4. План

### request_plan_generation
Запрашивает генерацию плана по цели.

Вход:
- user_id
- goal_id

Выход:
- success
- generation_job_id

---

### get_latest_plan
Возвращает последнюю версию плана по цели.

Вход:
- user_id
- goal_id

Выход:
- plan_view

---

### get_plan_for_review
Возвращает план в формате для показа пользователю.

Вход:
- user_id
- goal_id

Выход:
- plan_view

---

### accept_plan
Подтверждает выбранный план.

Вход:
- user_id
- goal_id
- plan_id

Выход:
- updated_goal_context
- activated_plan_view

---

### request_plan_revision
Создает новую итерацию плана на основе комментариев пользователя.

Вход:
- user_id
- goal_id
- revision_feedback

Выход:
- success
- revision_job_id

---

### archive_old_plan_versions
Архивирует старые версии плана.

Вход:
- goal_id

Выход:
- archived_versions_count

---

### activate_plan
Активирует конкретную версию плана.

Вход:
- user_id
- goal_id
- plan_id

Выход:
- activated_plan_view

---

## 5. Ежедневные задачи и check-in

### get_today_tasks
Возвращает задачи по цели на конкретный день.

Вход:
- user_id
- goal_id
- date

Выход:
- today_tasks

---

### get_or_create_today_checkin
Находит или создает check-in на сегодня.

Вход:
- user_id
- goal_id
- date

Выход:
- checkin_view

---

### submit_checkin_text
Сохраняет текстовый отчет пользователя за день.

Вход:
- user_id
- goal_id
- date
- text

Выход:
- updated_checkin_view

---

### mark_step_attempt
Фиксирует попытку выполнения шага.

Вход:
- user_id
- goal_id
- step_id
- date

Выход:
- updated_step_report

---

### mark_step_done
Отмечает шаг как выполненный.

Вход:
- user_id
- goal_id
- step_id
- date

Выход:
- updated_step_report

---

### mark_step_failed
Отмечает шаг как невыполненный.

Вход:
- user_id
- goal_id
- step_id
- date

Выход:
- updated_step_report

---

### complete_checkin
Завершает check-in за день.

Вход:
- user_id
- goal_id
- date

Выход:
- final_checkin_view

---

### get_checkin_view
Возвращает полную информацию о check-in.

Вход:
- user_id
- goal_id
- date

Выход:
- checkin_view

---

## 6. Файлы и proof

### save_telegram_file
Сохраняет файл, присланный через Telegram, в storage и в системе.

Вход:
- user_id
- telegram_file_id
- telegram_file_unique_id
- file_type
- mime_type
- size_bytes

Выход:
- file_id
- file_metadata

---

### attach_proof_to_checkin
Прикрепляет файл к check-in и шагу.

Вход:
- user_id
- goal_id
- date
- step_id
- file_id

Выход:
- updated_checkin_view

---

### validate_proof
Запускает проверку proof по конкретному шагу.

Вход:
- user_id
- goal_id
- date
- step_id
- file_id

Выход:
- proof_validation_result

---

### replace_proof
Заменяет старый proof на новый.

Вход:
- user_id
- goal_id
- date
- step_id
- old_file_id
- new_file_id

Выход:
- proof_validation_result

---

### list_checkin_files
Возвращает все файлы, прикрепленные к check-in.

Вход:
- user_id
- goal_id
- date

Выход:
- files[]

---

## 7. Прогресс

### recompute_goal_progress
Пересчитывает текущий прогресс по цели.

Вход:
- user_id
- goal_id

Выход:
- goal_progress_view

---

### get_goal_progress
Возвращает прогресс по цели.

Вход:
- user_id
- goal_id

Выход:
- goal_progress_view

---

### get_daily_progress_message
Возвращает готовые данные для ежедневного сообщения о прогрессе.

Вход:
- user_id
- goal_id
- date

Выход:
- daily_progress_payload

---

### get_weekly_summary
Возвращает weekly summary по цели.

Вход:
- user_id
- goal_id
- week_start

Выход:
- weekly_summary_view

---

## 8. Напоминания

### upsert_goal_reminder
Создает или обновляет настройки reminder по цели.

Вход:
- user_id
- goal_id
- enabled
- local_time
- timezone

Выход:
- reminder_view

---

### enable_goal_reminder
Включает reminder.

Вход:
- user_id
- goal_id

Выход:
- reminder_view

---

### disable_goal_reminder
Выключает reminder.

Вход:
- user_id
- goal_id

Выход:
- reminder_view

---

### list_due_reminders
Возвращает reminders, которые нужно отправить сейчас.

Вход:
- now

Выход:
- due_reminders[]

---

### mark_reminder_sent
Помечает отправку reminder как успешную.

Вход:
- reminder_delivery_id

Выход:
- success

---

### mark_reminder_failed
Помечает отправку reminder как неуспешную.

Вход:
- reminder_delivery_id
- error_text

Выход:
- success

---

## 9. Сессии и состояния

### get_goal_session
Возвращает состояние сценария по конкретной цели.

Вход:
- user_id
- goal_id

Выход:
- goal_session

---

### set_goal_session_state
Обновляет состояние сценария по цели.

Вход:
- user_id
- goal_id
- state
- substate
- context

Выход:
- updated_goal_session

---

### clear_goal_session
Очищает состояние сценария по цели.

Вход:
- user_id
- goal_id

Выход:
- success

---

### get_user_chat_session
Возвращает общее состояние чата пользователя.

Вход:
- user_id

Выход:
- user_chat_session

---

### set_user_chat_session
Обновляет общий контекст чата.

Вход:
- user_id
- active_goal_id
- state
- substate

Выход:
- updated_user_chat_session

---

## 10. События и аудит

### store_inbound_event
Сохраняет входящее событие от Telegram.

Вход:
- source
- external_event_id
- payload

Выход:
- inbound_event_id

---

### mark_inbound_event_processed
Помечает событие как обработанное.

Вход:
- event_id

Выход:
- success

---

### append_domain_event
Сохраняет внутреннее доменное событие системы.

Вход:
- event_type
- entity_type
- entity_id
- user_id
- goal_id
- payload

Выход:
- domain_event_id

---

### store_outbound_message
Сохраняет лог исходящего сообщения.

Вход:
- user_id
- payload

Выход:
- outbound_message_id

---

### mark_outbound_message_sent
Помечает исходящее сообщение как успешно отправленное.

Вход:
- message_id
- provider_meta

Выход:
- success

---

### mark_outbound_message_failed
Помечает исходящее сообщение как неуспешное.

Вход:
- message_id
- error_text

Выход:
- success
