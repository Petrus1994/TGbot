from enum import Enum


class DailyTaskStatus(str, Enum):
    pending = "pending"
    done = "done"
    skipped = "skipped"