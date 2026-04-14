from enum import Enum


class ProofType(str, Enum):
    text = "text"
    photo = "photo"
    screenshot = "screenshot"
    file = "file"
    video = "video"


class ProofStatus(str, Enum):
    uploaded = "uploaded"
    accepted = "accepted"
    rejected = "rejected"
    needs_more = "needs_more"