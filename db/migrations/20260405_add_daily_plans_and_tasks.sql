BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- =========================================================
-- daily_plans
-- =========================================================

CREATE TABLE IF NOT EXISTS daily_plans (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  goal_id UUID NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
  day_number INTEGER NOT NULL CHECK (day_number > 0),
  planned_date DATE,
  focus TEXT,
  summary TEXT,
  headline TEXT,
  focus_message TEXT,
  main_task_title TEXT,
  total_estimated_minutes INTEGER CHECK (total_estimated_minutes IS NULL OR total_estimated_minutes >= 0),
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'in_progress', 'done', 'skipped')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (goal_id, day_number)
);

ALTER TABLE daily_plans
  ADD COLUMN IF NOT EXISTS planned_date DATE,
  ADD COLUMN IF NOT EXISTS focus TEXT,
  ADD COLUMN IF NOT EXISTS summary TEXT,
  ADD COLUMN IF NOT EXISTS headline TEXT,
  ADD COLUMN IF NOT EXISTS focus_message TEXT,
  ADD COLUMN IF NOT EXISTS main_task_title TEXT,
  ADD COLUMN IF NOT EXISTS total_estimated_minutes INTEGER,
  ADD COLUMN IF NOT EXISTS status TEXT,
  ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

ALTER TABLE daily_plans
  ALTER COLUMN status SET DEFAULT 'pending';

UPDATE daily_plans
SET status = 'pending'
WHERE status IS NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'daily_plans_status_check'
  ) THEN
    ALTER TABLE daily_plans
      ADD CONSTRAINT daily_plans_status_check
      CHECK (status IN ('pending', 'in_progress', 'done', 'skipped'));
  END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_daily_plans_goal_id ON daily_plans (goal_id);
CREATE INDEX IF NOT EXISTS idx_daily_plans_goal_day ON daily_plans (goal_id, day_number);
CREATE INDEX IF NOT EXISTS idx_daily_plans_goal_planned_date ON daily_plans (goal_id, planned_date);
CREATE INDEX IF NOT EXISTS idx_daily_plans_status ON daily_plans (status);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'daily_plans_goal_id_day_number_key'
  ) THEN
    ALTER TABLE daily_plans
      ADD CONSTRAINT daily_plans_goal_id_day_number_key UNIQUE (goal_id, day_number);
  END IF;
END
$$;

DROP TRIGGER IF EXISTS trg_daily_plans_updated_at ON daily_plans;
CREATE TRIGGER trg_daily_plans_updated_at
BEFORE UPDATE ON daily_plans
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- =========================================================
-- daily_tasks
-- =========================================================

CREATE TABLE IF NOT EXISTS daily_tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  daily_plan_id UUID NOT NULL REFERENCES daily_plans(id) ON DELETE CASCADE,
  goal_id UUID NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  objective TEXT,
  description TEXT,
  instructions TEXT,
  why_today TEXT,
  success_criteria TEXT,
  estimated_minutes INTEGER CHECK (estimated_minutes IS NULL OR estimated_minutes >= 0),
  detail_level INTEGER NOT NULL DEFAULT 1 CHECK (detail_level >= 1),
  bucket TEXT,
  priority TEXT,
  order_index INTEGER NOT NULL CHECK (order_index > 0),
  is_required BOOLEAN NOT NULL DEFAULT TRUE,
  proof_required BOOLEAN NOT NULL DEFAULT FALSE,
  recommended_proof_type TEXT,
  proof_prompt TEXT,
  task_type TEXT,
  difficulty TEXT,
  tips JSONB NOT NULL DEFAULT '[]'::jsonb,
  technique_cues JSONB NOT NULL DEFAULT '[]'::jsonb,
  common_mistakes JSONB NOT NULL DEFAULT '[]'::jsonb,
  steps JSONB NOT NULL DEFAULT '[]'::jsonb,
  resources JSONB NOT NULL DEFAULT '[]'::jsonb,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'in_progress', 'done', 'skipped')),
  completed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (daily_plan_id, order_index)
);

ALTER TABLE daily_tasks
  ADD COLUMN IF NOT EXISTS objective TEXT,
  ADD COLUMN IF NOT EXISTS description TEXT,
  ADD COLUMN IF NOT EXISTS instructions TEXT,
  ADD COLUMN IF NOT EXISTS why_today TEXT,
  ADD COLUMN IF NOT EXISTS success_criteria TEXT,
  ADD COLUMN IF NOT EXISTS estimated_minutes INTEGER,
  ADD COLUMN IF NOT EXISTS detail_level INTEGER,
  ADD COLUMN IF NOT EXISTS bucket TEXT,
  ADD COLUMN IF NOT EXISTS priority TEXT,
  ADD COLUMN IF NOT EXISTS order_index INTEGER,
  ADD COLUMN IF NOT EXISTS is_required BOOLEAN,
  ADD COLUMN IF NOT EXISTS proof_required BOOLEAN,
  ADD COLUMN IF NOT EXISTS recommended_proof_type TEXT,
  ADD COLUMN IF NOT EXISTS proof_prompt TEXT,
  ADD COLUMN IF NOT EXISTS task_type TEXT,
  ADD COLUMN IF NOT EXISTS difficulty TEXT,
  ADD COLUMN IF NOT EXISTS tips JSONB,
  ADD COLUMN IF NOT EXISTS technique_cues JSONB,
  ADD COLUMN IF NOT EXISTS common_mistakes JSONB,
  ADD COLUMN IF NOT EXISTS steps JSONB,
  ADD COLUMN IF NOT EXISTS resources JSONB,
  ADD COLUMN IF NOT EXISTS status TEXT,
  ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

UPDATE daily_tasks
SET
  detail_level = COALESCE(detail_level, 1),
  order_index = COALESCE(order_index, 1),
  is_required = COALESCE(is_required, TRUE),
  proof_required = COALESCE(proof_required, FALSE),
  tips = COALESCE(tips, '[]'::jsonb),
  technique_cues = COALESCE(technique_cues, '[]'::jsonb),
  common_mistakes = COALESCE(common_mistakes, '[]'::jsonb),
  steps = COALESCE(steps, '[]'::jsonb),
  resources = COALESCE(resources, '[]'::jsonb),
  status = COALESCE(status, 'pending');

ALTER TABLE daily_tasks
  ALTER COLUMN detail_level SET DEFAULT 1,
  ALTER COLUMN order_index SET DEFAULT 1,
  ALTER COLUMN is_required SET DEFAULT TRUE,
  ALTER COLUMN proof_required SET DEFAULT FALSE,
  ALTER COLUMN tips SET DEFAULT '[]'::jsonb,
  ALTER COLUMN technique_cues SET DEFAULT '[]'::jsonb,
  ALTER COLUMN common_mistakes SET DEFAULT '[]'::jsonb,
  ALTER COLUMN steps SET DEFAULT '[]'::jsonb,
  ALTER COLUMN resources SET DEFAULT '[]'::jsonb,
  ALTER COLUMN status SET DEFAULT 'pending';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'daily_tasks_status_check'
  ) THEN
    ALTER TABLE daily_tasks
      ADD CONSTRAINT daily_tasks_status_check
      CHECK (status IN ('pending', 'in_progress', 'done', 'skipped'));
  END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_daily_tasks_daily_plan_id ON daily_tasks (daily_plan_id);
CREATE INDEX IF NOT EXISTS idx_daily_tasks_goal_id ON daily_tasks (goal_id);
CREATE INDEX IF NOT EXISTS idx_daily_tasks_status ON daily_tasks (status);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'daily_tasks_daily_plan_id_order_index_key'
  ) THEN
    ALTER TABLE daily_tasks
      ADD CONSTRAINT daily_tasks_daily_plan_id_order_index_key UNIQUE (daily_plan_id, order_index);
  END IF;
END
$$;

DROP TRIGGER IF EXISTS trg_daily_tasks_updated_at ON daily_tasks;
CREATE TRIGGER trg_daily_tasks_updated_at
BEFORE UPDATE ON daily_tasks
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

COMMIT;