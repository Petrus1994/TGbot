from pydantic import BaseModel


class GetOrCreateUserRequest(BaseModel):
    telegram_user_id: int
    telegram_chat_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    language_code: str | None = None


class UserResponse(BaseModel):
    user_id: str
    telegram_user_id: int
    telegram_chat_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    language_code: str | None = None
    timezone: str | None = None
    status: str
    is_new_user: bool
