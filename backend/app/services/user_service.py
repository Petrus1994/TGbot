from sqlalchemy import text
from app.db import engine
from app.schemas.user import GetOrCreateUserRequest


def get_or_create_user(payload: GetOrCreateUserRequest) -> dict:
    with engine.begin() as connection:
        existing = connection.execute(
            text(
                """
                SELECT
                    id,
                    telegram_user_id,
                    telegram_chat_id,
                    username,
                    first_name,
                    last_name,
                    language_code,
                    timezone,
                    status
                FROM users
                WHERE telegram_user_id = :telegram_user_id
                """
            ),
            {"telegram_user_id": payload.telegram_user_id},
        ).mappings().first()

        if existing:
            connection.execute(
                text(
                    """
                    UPDATE users
                    SET
                        telegram_chat_id = :telegram_chat_id,
                        username = :username,
                        first_name = :first_name,
                        last_name = :last_name,
                        language_code = :language_code,
                        last_seen_at = NOW(),
                        updated_at = NOW()
                    WHERE telegram_user_id = :telegram_user_id
                    """
                ),
                {
                    "telegram_user_id": payload.telegram_user_id,
                    "telegram_chat_id": payload.telegram_chat_id,
                    "username": payload.username,
                    "first_name": payload.first_name,
                    "last_name": payload.last_name,
                    "language_code": payload.language_code,
                },
            )

            refreshed = connection.execute(
                text(
                    """
                    SELECT
                        id,
                        telegram_user_id,
                        telegram_chat_id,
                        username,
                        first_name,
                        last_name,
                        language_code,
                        timezone,
                        status
                    FROM users
                    WHERE telegram_user_id = :telegram_user_id
                    """
                ),
                {"telegram_user_id": payload.telegram_user_id},
            ).mappings().first()

            return {
                "user_id": str(refreshed["id"]),
                "telegram_user_id": refreshed["telegram_user_id"],
                "telegram_chat_id": refreshed["telegram_chat_id"],
                "username": refreshed["username"],
                "first_name": refreshed["first_name"],
                "last_name": refreshed["last_name"],
                "language_code": refreshed["language_code"],
                "timezone": refreshed["timezone"],
                "status": refreshed["status"],
                "is_new_user": False,
            }

        created = connection.execute(
            text(
                """
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
                    :telegram_user_id,
                    :telegram_chat_id,
                    :username,
                    :first_name,
                    :last_name,
                    :language_code,
                    'UTC',
                    'active',
                    FALSE,
                    NOW()
                )
                RETURNING id, telegram_user_id, telegram_chat_id, username, first_name, last_name, language_code, timezone, status
                """
            ),
            {
                "telegram_user_id": payload.telegram_user_id,
                "telegram_chat_id": payload.telegram_chat_id,
                "username": payload.username,
                "first_name": payload.first_name,
                "last_name": payload.last_name,
                "language_code": payload.language_code,
            },
        ).mappings().first()

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
                    NULL,
                    NULL,
                    'new_user',
                    'start'
                )
                ON CONFLICT (user_id) DO NOTHING
                """
            ),
            {"user_id": created["id"]},
        )

        return {
            "user_id": str(created["id"]),
            "telegram_user_id": created["telegram_user_id"],
            "telegram_chat_id": created["telegram_chat_id"],
            "username": created["username"],
            "first_name": created["first_name"],
            "last_name": created["last_name"],
            "language_code": created["language_code"],
            "timezone": created["timezone"],
            "status": created["status"],
            "is_new_user": True,
        }