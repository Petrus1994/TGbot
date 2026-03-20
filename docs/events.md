# Events

События делятся на 3 группы:
- пользовательские
- системные
- по расписанию

---

## 1. Пользовательские события

### start_command_received
Пользователь нажал /start.

### main_menu_opened
Пользователь открыл главное меню.

### goals_list_requested
Пользователь запросил список своих целей.

### new_goal_requested
Пользователь начал создание новой цели.

### goal_description_submitted
Пользователь отправил описание цели.

### goal_category_selected
Пользователь выбрал категорию цели, если используются кнопки или шаблоны.

### goal_deadline_submitted
Пользователь указал срок достижения цели.

### goal_priority_submitted
Пользователь указал приоритет цели.

### profiling_question_answered
Пользователь ответил на уточняющий вопрос по цели.

### current_level_submitted
Пользователь указал свой текущий уровень в нужной деятельности.

### constraints_submitted
Пользователь указал ограничения: время, здоровье, деньги, условия и т.д.

### resources_submitted
Пользователь указал доступные ресурсы: инструменты, оборудование, материалы, наставник и т.д.

### motivation_submitted
Пользователь описал мотивацию или причину достижения цели.

### time_budget_submitted
Пользователь указал, сколько времени готов уделять цели в день или в неделю.

### plan_review_opened
Пользователь открыл план на просмотр.

### plan_accepted
Пользователь принял план.

### plan_revision_requested
Пользователь попросил переработать план.

### plan_revision_feedback_submitted
Пользователь отправил комментарии, как изменить план.

### today_tasks_requested
Пользователь запросил задачи на сегодня по выбранной цели.

### daily_checkin_opened_by_user
Пользователь открыл сценарий ежедневного отчета.

### daily_text_report_submitted
Пользователь отправил текстовый отчет за день.

### proof_image_submitted
Пользователь отправил фото как proof выполнения.

### proof_screenshot_submitted
Пользователь отправил скриншот как proof выполнения.

### replacement_proof_submitted
Пользователь отправил новый proof вместо отклоненного.

### step_comment_submitted
Пользователь оставил комментарий по шагу или выполнению.

### goal_paused_requested
Пользователь запросил паузу по цели.

### goal_resumed_requested
Пользователь возобновил работу по цели.

### goal_completed_requested
Пользователь отметил цель как завершенную.

### goal_cancelled_requested
Пользователь отменил цель.

### goal_replanning_requested
Пользователь запросил пересборку плана по цели.

### reminder_time_submitted
Пользователь указал удобное время напоминаний.

### reminder_enabled
Пользователь включил напоминания.

### reminder_disabled
Пользователь выключил напоминания.

### timezone_updated
Пользователь обновил часовой пояс.

---

## 2. Системные события

### user_created
В системе создан новый пользователь.

### user_loaded
Существующий пользователь найден и загружен.

### bot_session_started
Создана или активирована сессия чата.

### user_chat_context_updated
Обновлен общий контекст чата пользователя.

### goal_draft_created
Создан черновик цели.

### goal_created
Цель сохранена в системе.

### goal_context_updated
Контекст цели обновлен после новых ответов пользователя.

### goal_status_changed
Изменился статус цели.

### goal_activated
Цель переведена в активное выполнение.

### goal_paused
Цель поставлена на паузу.

### goal_resumed
Цель возобновлена.

### goal_completed
Цель завершена.

### goal_cancelled
Цель отменена.

### profiling_started
Начат этап сбора данных по цели.

### profiling_question_generated
Сформирован следующий уточняющий вопрос по цели.

### profiling_progress_updated
Обновлен прогресс профилирования.

### profiling_completed
Все обязательные данные по цели собраны.

### user_profile_updated
Профиль пользователя обновлен.

### plan_generation_requested
Backend запросил генерацию плана.

### ai_plan_generation_started
Началась AI-генерация плана.

### ai_plan_generation_completed
AI успешно сгенерировал план.

### ai_plan_generation_failed
Во время генерации плана произошла ошибка.

### plan_draft_created
Создан черновик плана.

### plan_steps_created
Сохранены шаги плана.

### plan_ready_for_review
План готов к показу пользователю.

### plan_status_changed
Статус плана изменен.

### new_plan_version_created
Создана новая версия плана.

### plan_archived
Предыдущая версия плана отправлена в архив.

### plan_activated
План активирован и используется для выполнения.

### daily_checkin_created
Создан ежедневный check-in по цели.

### daily_checkin_updated
Check-in обновлен.

### daily_checkin_submitted
Пользователь завершил отправку отчета за день.

### daily_checkin_missed
Пользователь не отправил check-in вовремя.

### step_attempt_recorded
Зафиксирована попытка выполнить шаг плана.

### daily_step_completed
Шаг плана за день подтвержден.

### daily_step_failed
Шаг плана за день не подтвержден.

### day_plan_completed
Все задачи по цели за день завершены.

### next_step_unlocked
Открыт следующий шаг или следующий день выполнения.

### proof_file_saved
Файл proof сохранен в storage и метаданные записаны в систему.

### proof_attached_to_checkin
Файл прикреплен к daily check-in.

### proof_validation_requested
Запущена проверка proof.

### image_analysis_started
Начат анализ изображения.

### image_analysis_completed
Анализ изображения завершен.

### proof_validation_passed
Proof принят.

### proof_validation_failed
Proof отклонен.

### proof_validation_uncertain
Система не уверена в результате проверки.

### proof_rejected_needs_better_evidence
Для подтверждения шага нужен более четкий proof.

### goal_progress_recomputed
Пересчитан текущий прогресс по цели.

### goal_progress_snapshot_created
Создан снимок прогресса по цели на дату.

### weekly_progress_snapshot_created
Создан недельный снимок прогресса.

### streak_updated
Обновлена серия подряд выполненных дней.

### streak_broken
Серия выполнений прервалась.

### outbound_message_created
Подготовлено исходящее сообщение пользователю.

### outbound_message_sent
Сообщение успешно отправлено.

### outbound_message_failed
Сообщение не удалось отправить.

---

## 3. События по расписанию

### daily_reminder_triggered
Сработал ежедневный reminder по цели.

### daily_reminder_sent
Ежедневное напоминание отправлено.

### daily_reminder_failed
Не удалось отправить ежедневное напоминание.

### daily_progress_job_started
Запущен job расчета ежедневного прогресса.

### daily_progress_calculated
Ежедневный прогресс рассчитан.

### daily_progress_message_sent
Сообщение с ежедневным прогрессом отправлено.

### daily_progress_message_failed
Не удалось отправить сообщение с ежедневным прогрессом.

### weekly_summary_job_started
Запущен job сборки weekly summary.

### weekly_summary_compiled
Данные для weekly summary собраны.

### weekly_summary_generated
Сформирован текст weekly summary.

### weekly_summary_sent
Weekly summary отправлен пользователю.

### weekly_summary_failed
Не удалось отправить weekly summary.

### missed_day_detected
Обнаружен пропущенный день по цели.

### reengagement_message_generated
Сформировано сообщение для возврата пользователя в выполнение.

### reengagement_message_sent
Сообщение для возврата пользователя отправлено.

## Task events

task_marked_done
task_marked_not_done
task_comment_submitted
task_attachment_submitted

## System events

task_report_created
task_report_updated
proof_attached_to_task
proof_validation_completed (optional, soft)

## Important rule

proof validation НЕ блокирует выполнение сценария
