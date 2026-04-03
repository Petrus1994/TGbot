from enum import Enum


class DailyPlanStatus(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    done = "done"
    skipped = "skipped"