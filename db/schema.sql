-- db/schema.sql
-- PostgreSQL schema for AI Goal Tracker Telegram Bot

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- =========================================================
-- Utility: updated_at trigger
-- =========================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =========================================================
-- users
-- =========================================================

CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  telegram_user_id BIGINT NOT NULL UNIQUE,
  telegram_chat_id BIGINT NOT NULL,
  username TEXT,
  first_name TEXT,
  last_name TEXT,
  language_code TEXT,
  timezone TEXT,
  status TEXT NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'inactive', 'blocked')),
  is_blocked BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_users_telegram_chat_id ON users (telegram_chat_id);
CREATE INDEX IF NOT EXISTS idx_users_status ON users (status);

CREATE TRIGGER trg_users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- =========================================================
-- user_profiles
-- =========================================================

CREATE TABLE IF NOT EXISTS user_profiles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
  age INTEGER CHECK (age IS NULL OR age >= 0),
  sex TEXT,
  height_cm INTEGER CHECK (height_cm IS NULL OR height_cm > 0),
  weight_kg NUMERIC(6,2) CHECK (weight_kg IS NULL OR weight_kg > 0),
  activity_level TEXT,
  experience_level TEXT,
  constraints_json JSONB,
  preferences_json JSONB,
  motivation_json JSONB,
  onboarding_completed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id ON user_profiles (user_id);

CREATE TRIGGER trg_user_profiles_updated_at
BEFORE UPDATE ON user_profiles
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- =========================================================
-- goals
-- =========================================================

CREATE TABLE IF NOT EXISTS goals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  description TEXT,
  category TEXT,
  target_metric_name TEXT,
  target_metric_value NUMERIC(12,2),
  target_date DATE,
  status TEXT NOT NULL DEFAULT 'draft'
    CHECK (
      status IN (
        'draft',
        'profiling',
        'planning',
        'awaiting_plan_approval',
        'active',
        'paused',
        'completed',
        'cancelled'
      )
    ),
  priority INTEGER CHECK (priority IS NULL OR priority >= 0),
  time_budget_value NUMERIC(10,2),
  time_budget_unit TEXT
    CHECK (
      time_budget_unit IS NULL OR
      time_budget_unit IN ('minutes_per_day', 'hours_per_day', 'hours_per_week')
    ),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  activated_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_goals_user_id ON goals (user_id);
CREATE INDEX IF NOT EXISTS idx_goals_status ON goals (status);
CREATE INDEX IF NOT EXISTS idx_goals_user_status ON goals (user_id, status);
CREATE INDEX IF NOT EXISTS idx_goals_target_date ON goals (target_date);

CREATE TRIGGER trg_goals_updated_at
BEFORE UPDATE ON goals
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- =========================================================
-- goal_sessions
-- =========================================================

CREATE TABLE IF NOT EXISTS goal_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  goal_id UUID NOT NULL UNIQUE REFERENCES goals(id) ON DELETE CASCADE,
  state TEXT NOT NULL DEFAULT 'idle'
    CHECK (
      state IN (
        'idle',
        'awaiting_goal_details',
        'awaiting_profiling_answer',
        'awaiting_time_budget',
        'awaiting_plan_review',
        'awaiting_plan_revision_feedback',
        'active_execution',
        'awaiting_proof',
        'awaiting_replacement_proof',
        'paused',
        'completed'
      )
    ),
  substate TEXT,
  context_json JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_goal_sessions_user_id ON goal_sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_goal_sessions_goal_id ON goal_sessions (goal_id);
CREATE INDEX IF NOT EXISTS idx_goal_sessions_state ON goal_sessions (state);

CREATE TRIGGER trg_goal_sessions_updated_at
BEFORE UPDATE ON goal_sessions
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- =========================================================
-- user_chat_context
-- =========================================================

CREATE TABLE IF NOT EXISTS user_chat_context (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
  active_goal_id UUID REFERENCES goals(id) ON DELETE SET NULL,
  last_selected_goal_id UUID REFERENCES goals(id) ON DELETE SET NULL,
  state TEXT,
  substate TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_chat_context_user_id ON user_chat_context (user_id);
CREATE INDEX IF NOT EXISTS idx_user_chat_context_active_goal_id ON user_chat_context (active_goal_id);

CREATE TRIGGER trg_user_chat_context_updated_at
BEFORE UPDATE ON user_chat_context
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- =========================================================
-- plans
-- =========================================================

CREATE TABLE IF NOT EXISTS plans (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  goal_id UUID NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
  version INTEGER NOT NULL CHECK (version > 0),
  status TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft', 'ready_for_review', 'accepted', 'archived')),
  source TEXT CHECK (source IS NULL OR source IN ('ai', 'manual', 'hybrid')),
  generation_model TEXT,
  generation_prompt_version TEXT,
  summary_text TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  accepted_at TIMESTAMPTZ,
  archived_at TIMESTAMPTZ,
  UNIQUE (goal_id, version)
);

CREATE INDEX IF NOT EXISTS idx_plans_goal_id ON plans (goal_id);
CREATE INDEX IF NOT EXISTS idx_plans_goal_status ON plans (goal_id, status);
CREATE INDEX IF NOT EXISTS idx_plans_status ON plans (status);

CREATE TRIGGER trg_plans_updated_at
BEFORE UPDATE ON plans
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- =========================================================
-- plan_steps
-- =========================================================

CREATE TABLE IF NOT EXISTS plan_steps (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  plan_id UUID NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
  step_order INTEGER NOT NULL CHECK (step_order > 0),
  title TEXT NOT NULL,
  description TEXT,
  instructions_json JSONB,
  frequency_type TEXT
    CHECK (
      frequency_type IS NULL OR
      frequency_type IN ('daily', 'weekly', 'custom')
    ),
  expected_proof_type TEXT
    CHECK (
      expected_proof_type IS NULL OR
      expected_proof_type IN ('photo', 'screenshot', 'photo_text', 'text', 'none')
    ),
  is_required BOOLEAN NOT NULL DEFAULT TRUE,
  start_day_offset INTEGER,
  end_day_offset INTEGER,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (plan_id, step_order)
);

CREATE INDEX IF NOT EXISTS idx_plan_steps_plan_id ON plan_steps (plan_id);
CREATE INDEX IF NOT EXISTS idx_plan_steps_frequency_type ON plan_steps (frequency_type);

CREATE TRIGGER trg_plan_steps_updated_at
BEFORE UPDATE ON plan_steps
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- =========================================================
-- daily_checkins
-- =========================================================

CREATE TABLE IF NOT EXISTS daily_checkins (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  goal_id UUID NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
  plan_id UUID NOT NULL REFERENCES plans(id) ON DELETE RESTRICT,
  checkin_date DATE NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (
      status IN (
        'pending',
        'submitted',
        'under_review',
        'accepted',
        'rejected',
        'missed'
      )
    ),
  text_report TEXT,
  self_score INTEGER CHECK (self_score IS NULL OR (self_score >= 0 AND self_score <= 10)),
  submitted_at TIMESTAMPTZ,
  reviewed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, goal_id, checkin_date)
);

CREATE INDEX IF NOT EXISTS idx_daily_checkins_user_id ON daily_checkins (user_id);
CREATE INDEX IF NOT EXISTS idx_daily_checkins_goal_id ON daily_checkins (goal_id);
CREATE INDEX IF NOT EXISTS idx_daily_checkins_checkin_date ON daily_checkins (checkin_date);
CREATE INDEX IF NOT EXISTS idx_daily_checkins_goal_date ON daily_checkins (goal_id, checkin_date);
CREATE INDEX IF NOT EXISTS idx_daily_checkins_status ON daily_checkins (status);

CREATE TRIGGER trg_daily_checkins_updated_at
BEFORE UPDATE ON daily_checkins
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- =========================================================
-- step_reports
-- =========================================================

CREATE TABLE IF NOT EXISTS step_reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  daily_checkin_id UUID NOT NULL REFERENCES daily_checkins(id) ON DELETE CASCADE,
  plan_step_id UUID NOT NULL REFERENCES plan_steps(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'done', 'partial', 'skipped', 'failed')),
  comment TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (daily_checkin_id, plan_step_id)
);

CREATE INDEX IF NOT EXISTS idx_step_reports_daily_checkin_id ON step_reports (daily_checkin_id);
CREATE INDEX IF NOT EXISTS idx_step_reports_plan_step_id ON step_reports (plan_step_id);
CREATE INDEX IF NOT EXISTS idx_step_reports_status ON step_reports (status);

CREATE TRIGGER trg_step_reports_updated_at
BEFORE UPDATE ON step_reports
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- =========================================================
-- files
-- =========================================================

CREATE TABLE IF NOT EXISTS files (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  storage_provider TEXT NOT NULL DEFAULT 'aws_s3',
  bucket_name TEXT NOT NULL,
  storage_key TEXT NOT NULL,
  mime_type TEXT NOT NULL,
  size_bytes BIGINT NOT NULL CHECK (size_bytes >= 0),
  checksum_sha256 TEXT,
  telegram_file_id TEXT,
  telegram_file_unique_id TEXT,
  uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (storage_provider, bucket_name, storage_key)
);

CREATE INDEX IF NOT EXISTS idx_files_user_id ON files (user_id);
CREATE INDEX IF NOT EXISTS idx_files_telegram_file_unique_id ON files (telegram_file_unique_id);
CREATE INDEX IF NOT EXISTS idx_files_uploaded_at ON files (uploaded_at);

-- =========================================================
-- checkin_files
-- =========================================================

CREATE TABLE IF NOT EXISTS checkin_files (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  daily_checkin_id UUID NOT NULL REFERENCES daily_checkins(id) ON DELETE CASCADE,
  file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  kind TEXT NOT NULL DEFAULT 'proof'
    CHECK (kind IN ('proof', 'extra')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (daily_checkin_id, file_id)
);

CREATE INDEX IF NOT EXISTS idx_checkin_files_daily_checkin_id ON checkin_files (daily_checkin_id);
CREATE INDEX IF NOT EXISTS idx_checkin_files_file_id ON checkin_files (file_id);
CREATE INDEX IF NOT EXISTS idx_checkin_files_kind ON checkin_files (kind);

-- =========================================================
-- proof_validations
-- =========================================================

CREATE TABLE IF NOT EXISTS proof_validations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  daily_checkin_id UUID NOT NULL REFERENCES daily_checkins(id) ON DELETE CASCADE,
  plan_step_id UUID NOT NULL REFERENCES plan_steps(id) ON DELETE CASCADE,
  file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  status TEXT NOT NULL
    CHECK (status IN ('uploaded', 'processing', 'validated', 'rejected', 'uncertain')),
  confidence NUMERIC(5,4) CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
  reason_code TEXT,
  model_name TEXT,
  user_message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_proof_validations_daily_checkin_id ON proof_validations (daily_checkin_id);
CREATE INDEX IF NOT EXISTS idx_proof_validations_plan_step_id ON proof_validations (plan_step_id);
CREATE INDEX IF NOT EXISTS idx_proof_validations_file_id ON proof_validations (file_id);
CREATE INDEX IF NOT EXISTS idx_proof_validations_status ON proof_validations (status);
CREATE INDEX IF NOT EXISTS idx_proof_validations_created_at ON proof_validations (created_at);

-- =========================================================
-- reminders
-- =========================================================

CREATE TABLE IF NOT EXISTS reminders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  goal_id UUID NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  local_time TIME NOT NULL,
  timezone TEXT NOT NULL,
  channel TEXT NOT NULL DEFAULT 'telegram'
    CHECK (channel IN ('telegram')),
  message_template_key TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reminders_user_id ON reminders (user_id);
CREATE INDEX IF NOT EXISTS idx_reminders_goal_id ON reminders (goal_id);
CREATE INDEX IF NOT EXISTS idx_reminders_enabled ON reminders (enabled);
CREATE INDEX IF NOT EXISTS idx_reminders_enabled_timezone_local_time
  ON reminders (enabled, timezone, local_time);

CREATE TRIGGER trg_reminders_updated_at
BEFORE UPDATE ON reminders
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- =========================================================
-- reminder_deliveries
-- =========================================================

CREATE TABLE IF NOT EXISTS reminder_deliveries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  reminder_id UUID NOT NULL REFERENCES reminders(id) ON DELETE CASCADE,
  delivery_date DATE NOT NULL,
  scheduled_for TIMESTAMPTZ NOT NULL,
  sent_at TIMESTAMPTZ,
  status TEXT NOT NULL
    CHECK (status IN ('scheduled', 'sent', 'failed', 'cancelled')),
  error_text TEXT,
  telegram_message_id TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (reminder_id, delivery_date)
);

CREATE INDEX IF NOT EXISTS idx_reminder_deliveries_reminder_id ON reminder_deliveries (reminder_id);
CREATE INDEX IF NOT EXISTS idx_reminder_deliveries_delivery_date ON reminder_deliveries (delivery_date);
CREATE INDEX IF NOT EXISTS idx_reminder_deliveries_status ON reminder_deliveries (status);
CREATE INDEX IF NOT EXISTS idx_reminder_deliveries_scheduled_for ON reminder_deliveries (scheduled_for);

-- =========================================================
-- inbound_events
-- =========================================================

CREATE TABLE IF NOT EXISTS inbound_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source TEXT NOT NULL,
  external_event_id TEXT NOT NULL,
  payload_json JSONB NOT NULL,
  status TEXT NOT NULL DEFAULT 'received'
    CHECK (status IN ('received', 'processed', 'failed', 'ignored')),
  received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  processed_at TIMESTAMPTZ,
  error_text TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (source, external_event_id)
);

CREATE INDEX IF NOT EXISTS idx_inbound_events_status ON inbound_events (status);
CREATE INDEX IF NOT EXISTS idx_inbound_events_received_at ON inbound_events (received_at);

-- =========================================================
-- outbound_messages
-- =========================================================

CREATE TABLE IF NOT EXISTS outbound_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  goal_id UUID REFERENCES goals(id) ON DELETE SET NULL,
  channel TEXT NOT NULL DEFAULT 'telegram'
    CHECK (channel IN ('telegram')),
  message_type TEXT NOT NULL,
  request_payload_json JSONB NOT NULL,
  response_payload_json JSONB,
  status TEXT NOT NULL
    CHECK (status IN ('created', 'sent', 'failed')),
  error_text TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  sent_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_outbound_messages_user_id ON outbound_messages (user_id);
CREATE INDEX IF NOT EXISTS idx_outbound_messages_goal_id ON outbound_messages (goal_id);
CREATE INDEX IF NOT EXISTS idx_outbound_messages_status ON outbound_messages (status);
CREATE INDEX IF NOT EXISTS idx_outbound_messages_created_at ON outbound_messages (created_at);

-- =========================================================
-- ai_runs
-- =========================================================

CREATE TABLE IF NOT EXISTS ai_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  goal_id UUID REFERENCES goals(id) ON DELETE SET NULL,
  purpose TEXT NOT NULL
    CHECK (
      purpose IN (
        'goal_plan',
        'checkin_review',
        'motivation',
        'replan',
        'weekly_summary',
        'proof_validation'
      )
    ),
  model TEXT NOT NULL,
  input_tokens INTEGER CHECK (input_tokens IS NULL OR input_tokens >= 0),
  output_tokens INTEGER CHECK (output_tokens IS NULL OR output_tokens >= 0),
  status TEXT NOT NULL
    CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
  request_hash TEXT,
  response_json JSONB,
  error_text TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_ai_runs_user_id ON ai_runs (user_id);
CREATE INDEX IF NOT EXISTS idx_ai_runs_goal_id ON ai_runs (goal_id);
CREATE INDEX IF NOT EXISTS idx_ai_runs_purpose ON ai_runs (purpose);
CREATE INDEX IF NOT EXISTS idx_ai_runs_status ON ai_runs (status);
CREATE INDEX IF NOT EXISTS idx_ai_runs_created_at ON ai_runs (created_at);

COMMIT;
