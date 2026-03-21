-- db/seed.sql
-- Seed data for local/dev/staging testing
-- Safe to keep in GitHub if used only with fake/test data

BEGIN;

-- =========================================================
-- Test user
-- =========================================================

WITH inserted_user AS (
  INSERT INTO users (
    telegram_user_id,
    telegram_chat_id,
    username,
    first_name,
    last_name,
    language_code,
    timezone,
    status,
    is_blocked,
    last_seen_at
  )
  VALUES (
    100000001,
    100000001,
    'test_user',
    'Test',
    'User',
    'ru',
    'Europe/Moscow',
    'active',
    FALSE,
    NOW()
  )
  ON CONFLICT (telegram_user_id) DO UPDATE
  SET
    telegram_chat_id = EXCLUDED.telegram_chat_id,
    username = EXCLUDED.username,
    first_name = EXCLUDED.first_name,
    last_name = EXCLUDED.last_name,
    language_code = EXCLUDED.language_code,
    timezone = EXCLUDED.timezone,
    status = EXCLUDED.status,
    is_blocked = EXCLUDED.is_blocked,
    last_seen_at = EXCLUDED.last_seen_at,
    updated_at = NOW()
  RETURNING id
),
upsert_profile AS (
  INSERT INTO user_profiles (
    user_id,
    age,
    sex,
    height_cm,
    weight_kg,
    activity_level,
    experience_level,
    constraints_json,
    preferences_json,
    motivation_json,
    onboarding_completed_at
  )
  SELECT
    id,
    28,
    'male',
    180,
    78.50,
    'medium',
    'beginner',
    '{"injuries": [], "time_limits": ["workdays_after_19_00"]}'::jsonb,
    '{"preferred_days": ["mon","wed","fri","sat"], "preferred_time": "evening"}'::jsonb,
    '{"why": "improve health and discipline"}'::jsonb,
    NOW()
  FROM inserted_user
  ON CONFLICT (user_id) DO UPDATE
  SET
    age = EXCLUDED.age,
    sex = EXCLUDED.sex,
    height_cm = EXCLUDED.height_cm,
    weight_kg = EXCLUDED.weight_kg,
    activity_level = EXCLUDED.activity_level,
    experience_level = EXCLUDED.experience_level,
    constraints_json = EXCLUDED.constraints_json,
    preferences_json = EXCLUDED.preferences_json,
    motivation_json = EXCLUDED.motivation_json,
    onboarding_completed_at = EXCLUDED.onboarding_completed_at,
    updated_at = NOW()
  RETURNING user_id
),
upsert_goal_1 AS (
  INSERT INTO goals (
    user_id,
    title,
    description,
    category,
    target_metric_name,
    target_metric_value,
    target_date,
    status,
    priority,
    time_budget_value,
    time_budget_unit,
    activated_at
  )
  SELECT
    user_id,
    'Похудеть на 5 кг',
    'Снизить вес безопасно за счет режима питания и регулярной активности',
    'fitness',
    'weight_loss_kg',
    5.00,
    CURRENT_DATE + INTERVAL '90 days',
    'active',
    1,
    45,
    'minutes_per_day',
    NOW()
  FROM upsert_profile
  ON CONFLICT DO NOTHING
  RETURNING id, user_id
),
existing_goal_1 AS (
  SELECT g.id, g.user_id
  FROM goals g
  JOIN inserted_user u ON u.id = g.user_id
  WHERE g.title = 'Похудеть на 5 кг'
  ORDER BY g.created_at ASC
  LIMIT 1
),
goal_1 AS (
  SELECT id, user_id FROM upsert_goal_1
  UNION ALL
  SELECT id, user_id FROM existing_goal_1
  LIMIT 1
),
upsert_goal_2 AS (
  INSERT INTO goals (
    user_id,
    title,
    description,
    category,
    target_metric_name,
    target_metric_value,
    target_date,
    status,
    priority,
    time_budget_value,
    time_budget_unit,
    activated_at
  )
  SELECT
    user_id,
    'Научиться играть 10 песен на гитаре',
    'Освоить базовые аккорды, бой и выучить 10 простых песен',
    'music',
    'songs_learned',
    10.00,
    CURRENT_DATE + INTERVAL '120 days',
    'draft',
    2,
    30,
    'minutes_per_day',
    NULL
  FROM upsert_profile
  ON CONFLICT DO NOTHING
  RETURNING id, user_id
),
existing_goal_2 AS (
  SELECT g.id, g.user_id
  FROM goals g
  JOIN inserted_user u ON u.id = g.user_id
  WHERE g.title = 'Научиться играть 10 песен на гитаре'
  ORDER BY g.created_at ASC
  LIMIT 1
),
goal_2 AS (
  SELECT id, user_id FROM upsert_goal_2
  UNION ALL
  SELECT id, user_id FROM existing_goal_2
  LIMIT 1
),
upsert_goal_session_1 AS (
  INSERT INTO goal_sessions (
    user_id,
    goal_id,
    state,
    substate,
    context_json
  )
  SELECT
    g.user_id,
    g.id,
    'active_execution',
    'waiting_for_today_proof',
    '{"current_day": 3, "plan_version": 1}'::jsonb
  FROM goal_1 g
  ON CONFLICT (goal_id) DO UPDATE
  SET
    user_id = EXCLUDED.user_id,
    state = EXCLUDED.state,
    substate = EXCLUDED.substate,
    context_json = EXCLUDED.context_json,
    updated_at = NOW()
  RETURNING goal_id
),
upsert_goal_session_2 AS (
  INSERT INTO goal_sessions (
    user_id,
    goal_id,
    state,
    substate,
    context_json
  )
  SELECT
    g.user_id,
    g.id,
    'awaiting_goal_details',
    'draft_created',
    '{"note": "secondary goal not active yet"}'::jsonb
  FROM goal_2 g
  ON CONFLICT (goal_id) DO UPDATE
  SET
    user_id = EXCLUDED.user_id,
    state = EXCLUDED.state,
    substate = EXCLUDED.substate,
    context_json = EXCLUDED.context_json,
    updated_at = NOW()
  RETURNING goal_id
),
upsert_chat_context AS (
  INSERT INTO user_chat_context (
    user_id,
    active_goal_id,
    last_selected_goal_id,
    state,
    substate
  )
  SELECT
    u.id,
    g1.id,
    g1.id,
    'goal_active',
    'main_menu'
  FROM inserted_user u
  CROSS JOIN goal_1 g1
  ON CONFLICT (user_id) DO UPDATE
  SET
    active_goal_id = EXCLUDED.active_goal_id,
    last_selected_goal_id = EXCLUDED.last_selected_goal_id,
    state = EXCLUDED.state,
    substate = EXCLUDED.substate,
    updated_at = NOW()
  RETURNING user_id
),
insert_plan AS (
  INSERT INTO plans (
    goal_id,
    version,
    status,
    source,
    generation_model,
    generation_prompt_version,
    summary_text,
    accepted_at
  )
  SELECT
    g1.id,
    1,
    'accepted',
    'ai',
    'gpt-5',
    'v1',
    'План на 12 недель: питание, ходьба, домашние тренировки и еженедельный контроль прогресса',
    NOW()
  FROM goal_1 g1
  ON CONFLICT (goal_id, version) DO UPDATE
  SET
    status = EXCLUDED.status,
    source = EXCLUDED.source,
    generation_model = EXCLUDED.generation_model,
    generation_prompt_version = EXCLUDED.generation_prompt_version,
    summary_text = EXCLUDED.summary_text,
    accepted_at = EXCLUDED.accepted_at,
    updated_at = NOW()
  RETURNING id, goal_id
),
plan_row AS (
  SELECT id, goal_id FROM insert_plan
),
step1 AS (
  INSERT INTO plan_steps (
    plan_id,
    step_order,
    title,
    description,
    instructions_json,
    frequency_type,
    expected_proof_type,
    is_required,
    start_day_offset,
    end_day_offset
  )
  SELECT
    p.id,
    1,
    'Пройти 8000 шагов',
    'Сделать минимум 8000 шагов в течение дня',
    '{"proof_hint": "screenshot from health app or fitness tracker"}'::jsonb,
    'daily',
    'screenshot',
    TRUE,
    0,
    84
  FROM plan_row p
  ON CONFLICT (plan_id, step_order) DO UPDATE
  SET
    title = EXCLUDED.title,
    description = EXCLUDED.description,
    instructions_json = EXCLUDED.instructions_json,
    frequency_type = EXCLUDED.frequency_type,
    expected_proof_type = EXCLUDED.expected_proof_type,
    is_required = EXCLUDED.is_required,
    start_day_offset = EXCLUDED.start_day_offset,
    end_day_offset = EXCLUDED.end_day_offset,
    updated_at = NOW()
  RETURNING id, plan_id
),
step2 AS (
  INSERT INTO plan_steps (
    plan_id,
    step_order,
    title,
    description,
    instructions_json,
    frequency_type,
    expected_proof_type,
    is_required,
    start_day_offset,
    end_day_offset
  )
  SELECT
    p.id,
    2,
    'Сделать домашнюю тренировку 20 минут',
    'Короткая тренировка: приседания, планка, отжимания, растяжка',
    '{"proof_hint": "photo from workout or screenshot of timer"}'::jsonb,
    'daily',
    'photo_text',
    TRUE,
    0,
    84
  FROM plan_row p
  ON CONFLICT (plan_id, step_order) DO UPDATE
  SET
    title = EXCLUDED.title,
    description = EXCLUDED.description,
    instructions_json = EXCLUDED.instructions_json,
    frequency_type = EXCLUDED.frequency_type,
    expected_proof_type = EXCLUDED.expected_proof_type,
    is_required = EXCLUDED.is_required,
    start_day_offset = EXCLUDED.start_day_offset,
    end_day_offset = EXCLUDED.end_day_offset,
    updated_at = NOW()
  RETURNING id, plan_id
),
step3 AS (
  INSERT INTO plan_steps (
    plan_id,
    step_order,
    title,
    description,
    instructions_json,
    frequency_type,
    expected_proof_type,
    is_required,
    start_day_offset,
    end_day_offset
  )
  SELECT
    p.id,
    3,
    'Не выйти за дневной калораж',
    'Соблюдать запланированный лимит калорий на день',
    '{"proof_hint": "screenshot from calorie tracking app"}'::jsonb,
    'daily',
    'screenshot',
    TRUE,
    0,
    84
  FROM plan_row p
  ON CONFLICT (plan_id, step_order) DO UPDATE
  SET
    title = EXCLUDED.title,
    description = EXCLUDED.description,
    instructions_json = EXCLUDED.instructions_json,
    frequency_type = EXCLUDED.frequency_type,
    expected_proof_type = EXCLUDED.expected_proof_type,
    is_required = EXCLUDED.is_required,
    start_day_offset = EXCLUDED.start_day_offset,
    end_day_offset = EXCLUDED.end_day_offset,
    updated_at = NOW()
  RETURNING id, plan_id
),
insert_checkin AS (
  INSERT INTO daily_checkins (
    user_id,
    goal_id,
    plan_id,
    checkin_date,
    status,
    text_report,
    self_score,
    submitted_at,
    reviewed_at
  )
  SELECT
    g1.user_id,
    g1.id,
    p.id,
    CURRENT_DATE,
    'accepted',
    'Сегодня выполнил шаги, тренировку и уложился в калории.',
    8,
    NOW(),
    NOW()
  FROM goal_1 g1
  CROSS JOIN plan_row p
  ON CONFLICT (user_id, goal_id, checkin_date) DO UPDATE
  SET
    plan_id = EXCLUDED.plan_id,
    status = EXCLUDED.status,
    text_report = EXCLUDED.text_report,
    self_score = EXCLUDED.self_score,
    submitted_at = EXCLUDED.submitted_at,
    reviewed_at = EXCLUDED.reviewed_at,
    updated_at = NOW()
  RETURNING id
),
insert_step_report_1 AS (
  INSERT INTO step_reports (
    daily_checkin_id,
    plan_step_id,
    status,
    comment
  )
  SELECT
    c.id,
    s.id,
    'done',
    'Порог шагов достигнут'
  FROM insert_checkin c
  CROSS JOIN step1 s
  ON CONFLICT (daily_checkin_id, plan_step_id) DO UPDATE
  SET
    status = EXCLUDED.status,
    comment = EXCLUDED.comment,
    updated_at = NOW()
  RETURNING id
),
insert_step_report_2 AS (
  INSERT INTO step_reports (
    daily_checkin_id,
    plan_step_id,
    status,
    comment
  )
  SELECT
    c.id,
    s.id,
    'done',
    'Тренировка завершена'
  FROM insert_checkin c
  CROSS JOIN step2 s
  ON CONFLICT (daily_checkin_id, plan_step_id) DO UPDATE
  SET
    status = EXCLUDED.status,
    comment = EXCLUDED.comment,
    updated_at = NOW()
  RETURNING id
),
insert_step_report_3 AS (
  INSERT INTO step_reports (
    daily_checkin_id,
    plan_step_id,
    status,
    comment
  )
  SELECT
    c.id,
    s.id,
    'done',
    'Лимит калорий соблюден'
  FROM insert_checkin c
  CROSS JOIN step3 s
  ON CONFLICT (daily_checkin_id, plan_step_id) DO UPDATE
  SET
    status = EXCLUDED.status,
    comment = EXCLUDED.comment,
    updated_at = NOW()
  RETURNING id
),
insert_file AS (
  INSERT INTO files (
    user_id,
    storage_provider,
    bucket_name,
    storage_key,
    mime_type,
    size_bytes,
    checksum_sha256,
    telegram_file_id,
    telegram_file_unique_id,
    uploaded_at
  )
  SELECT
    u.id,
    'aws_s3',
    'tgbot-test-bucket',
    'users/test-user/goals/goal-1/checkins/' || TO_CHAR(CURRENT_DATE, 'YYYY/MM/DD') || '/proof-1.jpg',
    'image/jpeg',
    245678,
    'test-checksum-sha256-001',
    'telegram_file_id_001',
    'telegram_file_unique_id_001',
    NOW()
  FROM inserted_user u
  ON CONFLICT (storage_provider, bucket_name, storage_key) DO UPDATE
  SET
    mime_type = EXCLUDED.mime_type,
    size_bytes = EXCLUDED.size_bytes,
    checksum_sha256 = EXCLUDED.checksum_sha256,
    telegram_file_id = EXCLUDED.telegram_file_id,
    telegram_file_unique_id = EXCLUDED.telegram_file_unique_id,
    uploaded_at = EXCLUDED.uploaded_at
  RETURNING id
),
insert_checkin_file AS (
  INSERT INTO checkin_files (
    daily_checkin_id,
    file_id,
    kind
  )
  SELECT
    c.id,
    f.id,
    'proof'
  FROM insert_checkin c
  CROSS JOIN insert_file f
  ON CONFLICT (daily_checkin_id, file_id) DO UPDATE
  SET
    kind = EXCLUDED.kind
  RETURNING id
),
insert_validation AS (
  INSERT INTO proof_validations (
    daily_checkin_id,
    plan_step_id,
    file_id,
    status,
    confidence,
    reason_code,
    model_name,
    user_message
  )
  SELECT
    c.id,
    s.id,
    f.id,
    'validated',
    0.9400,
    'match_enough_evidence',
    'gpt-4.1-mini',
    'Доказательство принято. Можно двигаться дальше.'
  FROM insert_checkin c
  CROSS JOIN step2 s
  CROSS JOIN insert_file f
  RETURNING id
),
insert_reminder AS (
  INSERT INTO reminders (
    user_id,
    goal_id,
    enabled,
    local_time,
    timezone,
    channel,
    message_template_key
  )
  SELECT
    g1.user_id,
    g1.id,
    TRUE,
    '09:00:00',
    'Europe/Moscow',
    'telegram',
    'daily_checkin_reminder'
  FROM goal_1 g1
  RETURNING id
),
existing_reminder AS (
  SELECT r.id
  FROM reminders r
  JOIN goal_1 g1 ON g1.id = r.goal_id
  WHERE r.local_time = '09:00:00'
  ORDER BY r.created_at ASC
  LIMIT 1
),
reminder_row AS (
  SELECT id FROM insert_reminder
  UNION ALL
  SELECT id FROM existing_reminder
  LIMIT 1
),
insert_reminder_delivery AS (
  INSERT INTO reminder_deliveries (
    reminder_id,
    delivery_date,
    scheduled_for,
    sent_at,
    status,
    error_text,
    telegram_message_id
  )
  SELECT
    r.id,
    CURRENT_DATE,
    NOW(),
    NOW(),
    'sent',
    NULL,
    'telegram_message_001'
  FROM reminder_row r
  ON CONFLICT (reminder_id, delivery_date) DO UPDATE
  SET
    scheduled_for = EXCLUDED.scheduled_for,
    sent_at = EXCLUDED.sent_at,
    status = EXCLUDED.status,
    error_text = EXCLUDED.error_text,
    telegram_message_id = EXCLUDED.telegram_message_id
  RETURNING id
),
insert_inbound_event AS (
  INSERT INTO inbound_events (
    source,
    external_event_id,
    payload_json,
    status,
    received_at,
    processed_at,
    error_text
  )
  VALUES (
    'telegram',
    'test-update-001',
    '{"update_id": 900001, "message": {"text": "/start"}}'::jsonb,
    'processed',
    NOW(),
    NOW(),
    NULL
  )
  ON CONFLICT (source, external_event_id) DO UPDATE
  SET
    payload_json = EXCLUDED.payload_json,
    status = EXCLUDED.status,
    received_at = EXCLUDED.received_at,
    processed_at = EXCLUDED.processed_at,
    error_text = EXCLUDED.error_text
  RETURNING id
),
insert_outbound_message AS (
  INSERT INTO outbound_messages (
    user_id,
    goal_id,
    channel,
    message_type,
    request_payload_json,
    response_payload_json,
    status,
    error_text,
    sent_at
  )
  SELECT
    g1.user_id,
    g1.id,
    'telegram',
    'daily_progress',
    '{"text": "Ты приблизился к цели на 2%"}'::jsonb,
    '{"telegram_message_id": "out-msg-001"}'::jsonb,
    'sent',
    NULL,
    NOW()
  FROM goal_1 g1
  RETURNING id
),
insert_ai_run AS (
  INSERT INTO ai_runs (
    user_id,
    goal_id,
    purpose,
    model,
    input_tokens,
    output_tokens,
    status,
    request_hash,
    response_json,
    error_text,
    completed_at
  )
  SELECT
    g1.user_id,
    g1.id,
    'goal_plan',
    'gpt-5',
    2100,
    980,
    'completed',
    'test-request-hash-001',
    '{"summary": "plan generated successfully"}'::jsonb,
    NULL,
    NOW()
  FROM goal_1 g1
  RETURNING id
)
SELECT 'seed completed' AS result;

COMMIT;
