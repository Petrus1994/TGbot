from __future__ import annotations

from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.plan import GoalPlan, PlanStatus


class PlanRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_latest_by_goal_id(self, goal_id: UUID) -> GoalPlan | None:
        stmt = (
            select(GoalPlan)
            .where(GoalPlan.goal_id == goal_id)
            .order_by(desc(GoalPlan.created_at))
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def create(
        self,
        *,
        goal_id: UUID,
        title: str,
        summary: str | None,
        content_json: str,
        status: PlanStatus = PlanStatus.draft,
    ) -> GoalPlan:
        plan = GoalPlan(
            goal_id=goal_id,
            title=title,
            summary=summary,
            content_json=content_json,
            status=status,
        )
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def save(self, plan: GoalPlan) -> GoalPlan:
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        return plan