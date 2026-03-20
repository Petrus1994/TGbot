# Backend Responses

Этот документ описывает, какие готовые объекты backend должен возвращать боту.
Бот не должен сам собирать данные из разных таблиц — backend должен отдавать уже готовый контекст.

---

## 1. UserContext

Базовый контекст пользователя.

Поля:
- user_id
- telegram_user_id
- telegram_chat_id
- first_name
- language_code
- timezone
- onboarding_completed
- active_goal_id
- has_multiple_goals
- reminders_enabled

---

## 2. ChatContext

Текущий контекст чата пользователя.

Поля:
- user_id
- active_goal_id
- active_goal_title
- has_other_active_goals
- available_goal_switch_options[]
- current_bot_state
- current_bot_substate

---

## 3. GoalsList

Список целей пользователя.

Поля:
- goals[]

Каждый элемент goals[]:
- goal_id
- title
- status
- category
- is_active_in_chat_context
- progress_percent
- today_tasks_count
- today_completed_tasks_count
- next_reminder_at

---

## 4. GoalContext

Полный контекст по конкретной цели.

Поля:
- goal_id
- title
- description
- category
- status
- target_date
- priority
- created_at
- activated_at
- progress_percent
- current_streak
- time_budget
- current_plan_id
- current_plan_version
- goal_session_state
- goal_session_substate

---

## 5. ProfilingState

Состояние профилирования по цели.

Поля:
- goal_id
- is_profiling_complete
- current_question_key
- current_question_text
- questions_answered_count
- questions_total_count
- known_profile_fields
- missing_required_fields

---

## 6. PlanView

План в формате для показа пользователю.

Поля:
- plan_id
- goal_id
- version
- status
- generated_by
- created_at
- summary_text
- steps[]

Каждый элемент steps[]:
- step_id
- step_order
- title
- description
- frequency_type
- expected_proof_type
- is_required

---

## 7. TodayTasks

Задачи по цели на выбранный день.

Поля:
- goal_id
- date
- checkin_status
- completed_count
- total_count
- tasks[]

Каждый элемент tasks[]:
- step_id
- title
- description
- status
- expected_proof_type
- proof_required
- proof_status
- can_submit_proof

report_status
user_result (done / not_done)
comment_allowed
attachment_allowed

---

## 8. DailyCheckinView

Полная информация по check-in за день.

Поля:
- checkin_id
- goal_id
- date
- status
- text_report
- submitted_at
- step_reports[]
- files[]

Каждый элемент step_reports[]:
- step_id
- status
- comment

Каждый элемент files[]:
- file_id
- kind
- mime_type
- uploaded_at
- validation_status

---

## 9. ProofValidationResult

Результат проверки proof.

Поля:
- goal_id
- checkin_id
- step_id
- file_id
- status
- confidence
- reason_code
- user_message
- needs_replacement
- next_action

Возможные значения status:
- passed
- failed
- uncertain

ProofValidationResult

- result: accepted / unclear / rejected
- confidence: number

Важно:
- результат не блокирует пользователя

---

## 10. GoalProgressView

Текущий прогресс по цели.

Поля:
- goal_id
- progress_percent
- completed_steps_count
- planned_steps_count
- completed_days_count
- missed_days_count
- current_streak
- days_remaining
- estimated_completion_status

---

## 11. DailyProgressPayload

Готовые данные для ежедневного сообщения о прогрессе.

Поля:
- goal_id
- date
- progress_percent
- progress_delta_percent
- completed_today
- planned_today
- streak
- short_message
- recommendation_text

---

## 12. WeeklySummaryView

Недельный summary по цели.

Поля:
- goal_id
- week_start
- week_end
- planned_tasks_count
- completed_tasks_count
- missed_tasks_count
- completion_percent
- progress_delta_percent
- streak_delta
- summary_text
- motivation_text
- tone

Возможные значения tone:
- supportive
- strict_supportive

---

## 13. ReminderView

Текущая настройка reminder по цели.

Поля:
- reminder_id
- goal_id
- enabled
- local_time
- timezone
- next_run_at

---

## 14. GoalSessionView

Состояние сценария бота по конкретной цели.

Поля:
- goal_id
- state
- substate
- context_json
- updated_at

---

## 15. UserChatSessionView

Общий контекст чата пользователя.

Поля:
- user_id
- active_goal_id
- state
- substate
- updated_at

---

## 16. FileMetadata

Метаданные сохраненного файла.

Поля:
- file_id
- user_id
- mime_type
- size_bytes
- storage_provider
- storage_key
- uploaded_at

---

## 17. ErrorResponse

Стандартный ответ backend при ошибке.

Поля:
- error_code
- error_message
- details
- retryable

Примеры error_code:
- goal_not_found
- plan_not_ready
- invalid_goal_state
- proof_not_attached
- checkin_already_completed
- reminder_not_found
- unauthorized_goal_access
- duplicate_event
