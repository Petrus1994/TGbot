from sqlalchemy import text
from fastapi import HTTPException

from app.db import engine
from app.schemas.goal import CreateGoalRequest


def create_goal(payload: CreateGoalRequest) -> dict:
    with engine.begin() as connection:
        user = connection.execute(
            text("SELECT id FROM users WHERE id = :user_id"),
            {"user_id": payload.user_id},
        ).mappings().first()

        if not user:
            raise HTTPException(status_code=404, detail="user_not_found")

        goal = connection.execute(
            text(
                """
                INSERT INTO goals (
                    user_id,
                    title,
                    description,
                    category,
                    target_date,
                    status,
                    priority
                )
                VALUES (
                    :user_id,
                    :title,
                    :description,
                    :category,
                    :target_date,
                    'draft',
                    :priority
                )
                RETURNING id, user_id, title, description, category, target_date, status, priority
                """
            ),
            {
                "user_id": payload.user_id,
                "title": payload.title,
                "description": payload.description,
                "category": payload.category,
                "target_date": payload.target_date,
                "priority": payload.priority,
            },
        ).mappings().first()

        connection.execute(
            text(
                """
                INSERT INTO goal_sessions (
                    user_id,
                    goal_id,
                    state,
                    substate,
                    context_json
                )
                VALUES (
                    :user_id,
                    :goal_id,
                    'awaiting_goal_details',
                    'goal_created',
                    '{}'::jsonb
                )
                ON CONFLICT (goal_id) DO NOTHING
                """
            ),
            {
                "user_id": payload.user_id,
                "goal_id": goal["id"],
            },
        )

        return {
            "goal_id": str(goal["id"]),
            "user_id": str(goal["user_id"]),
            "title": goal["title"],
            "description": goal["description"],
            "category": goal["category"],
            "target_date": goal["target_date"],
            "status": goal["status"],
            "priority": goal["priority"],
        }


def list_user_goals(user_id: str) -> list[dict]:
    with engine.begin() as connection:
        user = connection.execute(
            text("SELECT id FROM users WHERE id = :user_id"),
            {"user_id": user_id},
        ).mappings().first()

        if not user:
            raise HTTPException(status_code=404, detail="user_not_found")

        rows = connection.execute(
            text(
                """
                SELECT
                    id,
                    title,
                    status,
                    category,
                    priority,
                    target_date
                FROM goals
                WHERE user_id = :user_id
                ORDER BY created_at DESC
                """
            ),
            {"user_id": user_id},
        ).mappings().all()

        return [
            {
                "goal_id": str(row["id"]),
                "title": row["title"],
                "status": row["status"],
                "category": row["category"],
                "priority": row["priority"],
                "target_date": row["target_date"],
            }
            for row in rows
        ]


def set_active_goal(user_id: str, goal_id: str) -> dict:
    with engine.begin() as connection:
        goal = connection.execute(
            text(
                """
                SELECT id, user_id
                FROM goals
                WHERE id = :goal_id
                """
            ),
            {"goal_id": goal_id},
        ).mappings().first()

        if not goal:
            raise HTTPException(status_code=404, detail="goal_not_found")

        if str(goal["user_id"]) != user_id:
            raise HTTPException(status_code=403, detail="unauthorized_goal_access")

        connection.execute(
            text(
                """
                INSERT INTO user_chat_context (
                    user_id,
                    active_goal_id,
                    last_selected_goal_id,
                    state,
                    substate
                )
                VALUES (
                    :user_id,
                    :goal_id,
                    :goal_id,
                    'goal_active',
                    'selected'
                )
                ON CONFLICT (user_id)
                DO UPDATE SET
                    active_goal_id = EXCLUDED.active_goal_id,
                    last_selected_goal_id = EXCLUDED.last_selected_goal_id,
                    state = EXCLUDED.state,
                    substate = EXCLUDED.substate,
                    updated_at = NOW()
                """
            ),
            {
                "user_id": user_id,
                "goal_id": goal_id,
            },
        )

        context = connection.execute(
            text(
                """
                SELECT
                    user_id,
                    active_goal_id,
                    last_selected_goal_id,
                    state,
                    substate
                FROM user_chat_context
                WHERE user_id = :user_id
                """
            ),
            {"user_id": user_id},
        ).mappings().first()

        return {
            "user_id": str(context["user_id"]),
            "active_goal_id": str(context["active_goal_id"]) if context["active_goal_id"] else None,
            "last_selected_goal_id": str(context["last_selected_goal_id"]) if context["last_selected_goal_id"] else None,
            "state": context["state"],
            "substate": context["substate"],
        }


def get_goal_by_id(goal_id: str) -> dict | None:
    with engine.begin() as connection:
        goal = connection.execute(
            text(
                """
                SELECT
                    id,
                    user_id,
                    title,
                    description,
                    category,
                    target_date,
                    status,
                    priority
                FROM goals
                WHERE id = :goal_id
                """
            ),
            {"goal_id": goal_id},
        ).mappings().first()

        if not goal:
            return None

        return {
            "goal_id": str(goal["id"]),
            "user_id": str(goal["user_id"]),
            "title": goal["title"],
            "description": goal["description"],
            "category": goal["category"],
            "target_date": goal["target_date"],
            "status": goal["status"],
            "priority": goal["priority"],
        }


def get_goal_status(goal_id: str) -> str:
    with engine.begin() as connection:
        goal = connection.execute(
            text(
                """
                SELECT status
                FROM goals
                WHERE id = :goal_id
                """
            ),
            {"goal_id": goal_id},
        ).mappings().first()

        if not goal:
            raise HTTPException(status_code=404, detail="goal_not_found")

        return goal["status"]


def update_goal_status(goal_id: str, status: str) -> dict:
    allowed_statuses = {"draft", "active", "completed", "failed"}

    if status not in allowed_statuses:
        raise HTTPException(status_code=400, detail="invalid_goal_status")

    with engine.begin() as connection:
        goal = connection.execute(
            text(
                """
                UPDATE goals
                SET status = :status
                WHERE id = :goal_id
                RETURNING id, status
                """
            ),
            {
                "goal_id": goal_id,
                "status": status,
            },
        ).mappings().first()

        if not goal:
            raise HTTPException(status_code=404, detail="goal_not_found")

        return {
            "goal_id": str(goal["id"]),
            "status": goal["status"],
        }