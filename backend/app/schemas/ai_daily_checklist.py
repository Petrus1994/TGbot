from pydantic import BaseModel, Field, field_validator


ALLOWED_RESOURCE_TYPES = {"video", "article", "reference", "checklist", "tool"}
ALLOWED_TASK_TYPES = {
    "fitness",
    "music",
    "language",
    "study",
    "work",
    "habit",
    "speech",
    "drawing",
    "meditation",
    "rehab",
    "nutrition",
    "activity",
    "generic",
}
ALLOWED_DIFFICULTIES = {"easy", "medium", "hard"}
ALLOWED_PROOF_TYPES = {"text", "photo", "screenshot", "file", "video"}
ALLOWED_DETAIL_LEVELS = {1, 2, 3}
ALLOWED_BUCKETS = {"must", "should", "bonus"}
ALLOWED_PRIORITIES = {"high", "medium", "low"}


class AIDailyTaskStep(BaseModel):
    order: int
    title: str
    instruction: str
    duration_minutes: int | None = None
    sets: int | None = None
    reps: int | None = None
    rest_seconds: int | None = None
    notes: list[str] = Field(default_factory=list)

    @field_validator("order")
    @classmethod
    def validate_order(cls, value: int) -> int:
        if value < 1:
            raise ValueError("step order must be >= 1")
        return value

    @field_validator("title", "instruction")
    @classmethod
    def validate_non_empty_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("field must not be empty")
        return value

    @field_validator("duration_minutes")
    @classmethod
    def validate_duration(cls, value: int | None) -> int | None:
        if value is not None and value < 1:
            raise ValueError("duration_minutes must be >= 1")
        return value

    @field_validator("sets", "reps")
    @classmethod
    def validate_positive_ints(cls, value: int | None) -> int | None:
        if value is not None and value < 1:
            raise ValueError("numeric field must be >= 1")
        return value

    @field_validator("rest_seconds")
    @classmethod
    def validate_rest_seconds(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("rest_seconds must be >= 0")
        return value


class AIDailyTaskResource(BaseModel):
    title: str
    resource_type: str
    note: str | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("resource title must not be empty")
        return value

    @field_validator("resource_type")
    @classmethod
    def validate_resource_type(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in ALLOWED_RESOURCE_TYPES:
            raise ValueError(
                f"resource_type must be one of: {sorted(ALLOWED_RESOURCE_TYPES)}"
            )
        return value


class AIDetailedDailyTask(BaseModel):
    title: str
    objective: str | None = None
    description: str | None = None
    instructions: str | None = None
    why_today: str | None = None
    success_criteria: str | None = None
    estimated_minutes: int | None = None

    detail_level: int = 1
    bucket: str = "must"
    priority: str = "medium"

    is_required: bool = True
    proof_required: bool = False
    recommended_proof_type: str | None = None
    proof_prompt: str | None = None

    task_type: str = "generic"
    difficulty: str | None = None

    tips: list[str] = Field(default_factory=list)
    technique_cues: list[str] = Field(default_factory=list)
    common_mistakes: list[str] = Field(default_factory=list)
    steps: list[AIDailyTaskStep] = Field(default_factory=list)
    resources: list[AIDailyTaskResource] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("task title must not be empty")
        return value

    @field_validator("estimated_minutes")
    @classmethod
    def validate_estimated_minutes(cls, value: int | None) -> int | None:
        if value is not None and value < 1:
            raise ValueError("estimated_minutes must be >= 1")
        return value

    @field_validator("task_type")
    @classmethod
    def validate_task_type(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in ALLOWED_TASK_TYPES:
            raise ValueError(f"task_type must be one of: {sorted(ALLOWED_TASK_TYPES)}")
        return value

    @field_validator("difficulty")
    @classmethod
    def validate_difficulty(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().lower()
        if value not in ALLOWED_DIFFICULTIES:
            raise ValueError(
                f"difficulty must be one of: {sorted(ALLOWED_DIFFICULTIES)}"
            )
        return value

    @field_validator("recommended_proof_type")
    @classmethod
    def validate_recommended_proof_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().lower()
        if value not in ALLOWED_PROOF_TYPES:
            raise ValueError(
                f"recommended_proof_type must be one of: {sorted(ALLOWED_PROOF_TYPES)}"
            )
        return value

    @field_validator("detail_level")
    @classmethod
    def validate_detail_level(cls, value: int) -> int:
        if value not in ALLOWED_DETAIL_LEVELS:
            raise ValueError(
                f"detail_level must be one of: {sorted(ALLOWED_DETAIL_LEVELS)}"
            )
        return value

    @field_validator("bucket")
    @classmethod
    def validate_bucket(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in ALLOWED_BUCKETS:
            raise ValueError(f"bucket must be one of: {sorted(ALLOWED_BUCKETS)}")
        return value

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in ALLOWED_PRIORITIES:
            raise ValueError(f"priority must be one of: {sorted(ALLOWED_PRIORITIES)}")
        return value


class AIDailyChecklistResponse(BaseModel):
    headline: str
    focus_message: str | None = None
    main_task_title: str | None = None
    total_estimated_minutes: int | None = None
    tasks: list[AIDetailedDailyTask] = Field(default_factory=list)

    @field_validator("headline")
    @classmethod
    def validate_headline(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("headline must not be empty")
        return value

    @field_validator("main_task_title")
    @classmethod
    def validate_main_task_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("total_estimated_minutes")
    @classmethod
    def validate_total_estimated_minutes(cls, value: int | None) -> int | None:
        if value is not None and value < 1:
            raise ValueError("total_estimated_minutes must be >= 1")
        return value