from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.users import router as users_router
from app.api.goals import router as goals_router
from app.api.profiling import router as profiling_router
from app.api.routes.plan import router as plan_router
from app.api.routes.checkin import router as checkin_router
from app.api.routes.progress import router as progress_router
from app.api.routes.proof import router as proof_router

# 👇 НОВЫЙ ИМПОРТ
from app.api.daily_plans import router as daily_plans_router


app = FastAPI(title="TGbot Backend", version="0.1.0")

app.include_router(health_router)
app.include_router(users_router)
app.include_router(goals_router)
app.include_router(profiling_router)
app.include_router(plan_router)
app.include_router(checkin_router)
app.include_router(progress_router)
app.include_router(proof_router)

# 👇 НОВЫЙ РОУТЕР
app.include_router(daily_plans_router)