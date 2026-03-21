from sqlalchemy import create_engine, text
from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)


def check_db_connection() -> bool:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return True