from __future__ import annotations

from uuid import UUID

from sqlalchemy import desc, select, update, delete
from sqlalchemy.orm import Session

from app.models.plan import GoalPlan, PlanStatus


class PlanRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------
    # GETTERS
    # ------------------------------------------------

    def get_latest_by_goal_id(self, goal_id: UUID) -> GoalPlan | None:
        stmt = (
            select(GoalPlan)
            .where(GoalPlan.goal_id == goal_id)
            .order_by(desc(GoalPlan.created_at))
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_active_plan_by_goal_id(self, goal_id: UUID) -> GoalPlan | None:
        """
        Приоритет:
        1. accepted план
        2. последний draft
        """

        # сначала ищем accepted
        stmt = (
            select(GoalPlan)
            .where(
                GoalPlan.goal_id == goal_id,
                GoalPlan.status == PlanStatus.accepted,
            )
            .order_by(desc(GoalPlan.created_at))
            .limit(1)
        )
        accepted = self.db.execute(stmt).scalar_one_or_none()

        if accepted:
            return accepted

        # fallback на последний draft
        stmt = (
            select(GoalPlan)
            .where(
                GoalPlan.goal_id == goal_id,
                GoalPlan.status == PlanStatus.draft,
            )
            .order_by(desc(GoalPlan.created_at))
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    # ------------------------------------------------
    # CREATE / UPDATE
    # ------------------------------------------------

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

    # ------------------------------------------------
    # HELPERS ДЛЯ CLEAN FLOW
    # ------------------------------------------------

    def deactivate_old_drafts(self, goal_id: UUID) -> None:
        """
        Переводит старые draft-планы в archived (если у тебя есть такой статус)
        или просто оставляет только последний активный.
        """

        # если нет archived — можно просто ничего не делать
        # или удалить старые драфты (см. метод ниже)

        stmt = (
            update(GoalPlan)
            .where(
                GoalPlan.goal_id == goal_id,
                GoalPlan.status == PlanStatus.draft,
            )
            .values(status=PlanStatus.archived)
        )

        try:
            self.db.execute(stmt)
            self.db.commit()
        except Exception:
            self.db.rollback()

    def delete_by_goal_id(self, goal_id: UUID) -> None:
        """
        Полностью удаляет все планы для goal (жесткий reset)
        """
        stmt = delete(GoalPlan).where(GoalPlan.goal_id == goal_id)

        try:
            self.db.execute(stmt)
            self.db.commit()
        except Exception:
            self.db.rollback()