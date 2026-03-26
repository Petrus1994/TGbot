from enum import Enum


class ProofType(str, Enum):
    photo = "photo"
    screenshot = "screenshot"
    file = "file"
    text = "text"


class ProofStatus(str, Enum):
    uploaded = "uploaded"
    pending_review = "pending_review"
    accepted = "accepted"
    rejected = "rejected"