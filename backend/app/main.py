from fastapi import FastAPI
from app.api.health import router as health_router
from app.api.users import router as users_router
from app.api.goals import router as goals_router

app = FastAPI(title="TGbot Backend")

app.include_router(health_router)
app.include_router(users_router)
app.include_router(goals_router)